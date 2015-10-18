# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . BackendBase import *
import logging
import os
import pprint
import time
import psutil
import threading
import requests.exceptions
_logger = logging.getLogger(__name__)

class DockerBackendException(BackendException):
  pass

try:
  import docker
except ImportError:
  raise DockerBackendException('Could not import docker module from docker-py')

class DockerBackend(BackendBaseClass):
  def __init__(self, hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, **kwargs):
    super().__init__(hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, **kwargs)
    self._container = None
    self._workDirInsideContainer='/mnt/'
    self._skipToolExistsCheck = False
    self._userToUseInsideContainer = None
    self._killLock = threading.Lock()
    # handle required options
    if not 'image' in kwargs:
      raise DockerBackendException('"image" but be specified')
    self._dockerImageName = kwargs['image']
    if not (isinstance(self._dockerImageName, str) and len(self._dockerImageName) > 0):
      raise DockerBackendException('"image" must to a non empty string')

    # Pretend user default is $USER
    if not 'user' in kwargs:
      kwargs['user'] = '$HOST_USER'

    requiredOptions= ['image']
    # handle other options
    for key, value in kwargs.items():
      if key in requiredOptions:
        continue
      if key == 'skip_tool_check':
        self._skipToolExistsCheck = value
        if not isinstance(self._skipToolExistsCheck, bool):
          raise DockerBackendException('"skip_tool_check" must map to a bool')
        continue
      if key == 'image_work_dir':
        self._workDirInsideContainer = value
        if not (isinstance(self._workDirInsideContainer, str) and len(self._workDirInsideContainer) > 0):
          raise DockerBackendException('"image_work_dir" must be a non empty string')
        if not os.path.isabs(value):
          raise DockerBackendException('"image_work_dir" must be an absolute path')
        continue
      if key == 'user':
        if not (isinstance(value, str) or isinstance(value, int) or value == None):
          raise DockerBackendException('"user" must be integer or a string')
        if value == None:
          self._userToUseInsideContainer = None
        elif isinstance(value, int):
          if value < 0:
            raise DockerBackendException('"user" specified as an integer must be >= 0')
          self._userToUseInsideContainer = value
        else:
          # The choice of $ is deliberate because it is not a valid character in a username
          if value == "$HOST_USER":
            self._userToUseInsideContainer = "{}:{}".format(os.getuid(), os.getgid())
          else:
            import re
            if re.match(r'[a-z_][a-z0-9_-]*[$]?', value) == None:
              raise DockerBackendException('"{}" is not a valid username'.format(value))
            self._userToUseInsideContainer = value
        continue
      # Not recognised option
      raise DockerBackendException('"{}" key is not a recognised option'.format(key))

    # Initialise the docker client
    try:
      self._dc = docker.Client()
      self._dc.ping()
    except Exception as e:
      _logger.error('Failed to connect to the Docker daemon')
      _logger.error(e)
      raise DockerBackendException('Failed to connect to the Docker daemon')

    images = self._dc.images()
    assert isinstance(images, list)
    images = list(filter(lambda i: self._dockerImageName in i['RepoTags'], images))
    if len(images) == 0:
      msg='Could not find docker image with name "{}"'.format(self._dockerImageName)
      raise DockerBackendException(msg)
    else:
      if len(images) > 1:
        msg='Found multiple docker images:\n{}'.format(pprint.pformat(images))
        _logger.error(msg)
        raise DockerBackendException(msg)
      self._dockerImage = images[0]
      _logger.debug('Found Docker image:\n{}'.format(pprint.pformat(self._dockerImage)))

  @property
  def name(self):
    return "Docker"

  def run(self, cmdLine, logFilePath, envVars):
    self._logFilePath=logFilePath
    self._outOfMemory = False
    outOfTime=False
    ulimits = []
    if self.stackLimit != None:
      # FIXME: Setting stack size in Docker seems broken right now.
      # See: https://github.com/docker/docker/issues/13521
      _logger.warning("Setting stack size is probably broken. If you get crashes don't set it!")
      stackLimitInBytes=0
      if self.stackLimit == 0:
        # Work out the maximum memory size, docker doesn't support "unlimited" right now
        _logger.warning("Trying to emulate unlimited stack. Docker doesn't support setting it")
        if self.memoryLimit > 0:
          # If a memory limit is set just set the stack size to the maximum we allow
          # self.memoryLimit is in MiB, convert to bytes
          stackLimitInBytes = self.memoryLimit * (2**20)
        else:
          # No memory limit is set. Just use the amount of memory on system as an
          # upper bound
          stackLimitInBytes = psutil.virtual_memory().total + psutil.swap_memory().total
      elif self.stackLimit > 0:
        stackLimitInBytes=self.stackLimit * 1024
      # I'm assuming the stack limit is set in bytes here. I don't actually know if
      # this is the case.
      ulimits.append(docker.utils.Ulimit(name='stack',
        soft=stackLimitInBytes,
        hard=stackLimitInBytes))
      _logger.info('Setting stack size limit to {} bytes'.format(stackLimitInBytes))

    extraHostCfgArgs = {}
    if len(ulimits) > 0:
      extraHostCfgArgs['ulimits'] = ulimits

    # Declare the volumes
    programPathInsideContainer=self.programPath()
    bindings={
      self.workingDirectory: {'bind':self.workingDirectoryInternal, 'ro': False},
      self.hostProgramPath: {'bind':programPathInsideContainer, 'ro':True},
    }
    _logger.debug('Declaring bindings:\n{}'.format(pprint.pformat(bindings)))


    extraContainerArgs={}

    if self.memoryLimit > 0:
      # http://docs.docker.com/reference/run/#memory-constraints
      #
      # memory=L<inf, memory-swap=S<inf, L<=S
      # (specify both memory and memory-swap) The container is not allowed to use more than L bytes of memory, swap *plus* memory usage is limited by S.
      extraHostCfgArgs['mem_limit']='{}m'.format(self.memoryLimit)
      extraHostCfgArgs['memswap_limit']='{}m'.format(self.memoryLimit)
      _logger.info('Setting memory limit to {} MiB'.format(self.memoryLimit))

    if self._userToUseInsideContainer != None:
      extraContainerArgs['user'] = self._userToUseInsideContainer
      _logger.info('Using user "{}" inside container'.format(self._userToUseInsideContainer))

    hostCfg = self._dc.create_host_config(
      binds=bindings,
      privileged=False,
      network_mode=None,
      **extraHostCfgArgs
    )
    # Finally create the container
    self._container=self._dc.create_container(
      image=self._dockerImage['Id'],
      command=cmdLine,
      environment=envVars,
      working_dir=self.workingDirectoryInternal,
      volumes=list(bindings.keys()),
      host_config=hostCfg,
      **extraContainerArgs
    )
    _logger.debug('Created container:\n{}'.format(pprint.pformat(self._container['Id'])))
    if self._container['Warnings'] != None:
      _logger.warning('Warnings emitted when creating container:{}'.format(
        self._container['Warnings']))

    exitCode=None
    startTime=time.perf_counter()
    self._endTime=0
    try:
      self._dc.start(container=self._container['Id'])
      timeoutArg = { }
      if self.timeLimit > 0:
        timeoutArg['timeout']=self.timeLimit
        _logger.info('Using timeout {} seconds'.format(self.timeLimit))
      exitCode = self._dc.wait(container=self._container['Id'], **timeoutArg)
      if exitCode == -1:
        # FIXME: Does this even happen? Docker-py's documentation is unclear.
        outOfTime = True
        _logger.info('Timeout occurred')
        exitCode=None
    except requests.exceptions.ReadTimeout as e:
      _logger.info('Timeout occurred')
      outOfTime = True
    finally:
      self.kill()

    runTime= self._endTime - startTime
    return BackendResult(exitCode=exitCode, runTime=runTime, oot=outOfTime, oom=self._outOfMemory)

  def kill(self):
    try:
      self._killLock.acquire()
      self._endTime=time.perf_counter()
      if self._container != None:
        _logger.info('Stopping container:{}'.format(self._container['Id']))
        try:
          self._dc.kill(self._container['Id'])
        except docker.errors.APIError as e:
          _logger.error('Failed to kill container:"{}".\n{}'.format(self._container['Id'], str(e)))

        # Write logs to file (note we get binary in Python 3, not sure about Python 2)
        with open(self._logFilePath, 'wb') as f:
          logData = self._dc.logs(container=self._container['Id'],
              stdout=True, stderr=True, timestamps=False,
              tail='all', stream=False)
          _logger.info('Writing log to {}'.format(self._logFilePath))
          f.write(logData)

        # Record if OOM occurred
        containerInfo = self._dc.inspect_container(container=self._container['Id'])
        self._outOfMemory = containerInfo['State']['OOMKilled']
        assert isinstance(self._outOfMemory, bool)

        _logger.info('Destroying container:{}'.format(self._container['Id']))
        self._dc.remove_container(container=self._container['Id'], force=True)
        self._container = None
    finally:
      self._dc.close() # Try to avoid hitting file limit closing the client session when we're done
      self._killLock.release()


  def programPath(self):
    return '/tmp/{}'.format(os.path.basename(self.hostProgramPath))

  def checkToolExists(self, toolPath):
    if self._skipToolExistsCheck:
      _logger.info('Skipping tool check')
      return
    assert os.path.isabs(toolPath)
    # HACK: Is there a better way to do this?
    _logger.debug('Checking tool "{}" exists in image'.format(toolPath))
    tempContainer=self._dc.create_container(image=self._dockerImage['Id'],
      command=['ls', toolPath])
    _logger.debug('Created temporary container: {}'.format(tempContainer['Id']))
    self._dc.start(container=tempContainer['Id'])
    exitCode=self._dc.wait(container=tempContainer['Id'])
    self._dc.remove_container(container=tempContainer['Id'], force=True)
    if exitCode != 0:
      raise DockerBackendException('Tool "{}" does not exist in Docker image'.format(toolPath))

  @property
  def workingDirectoryInternal(self):
    # Return the path to the working directory that will be used inside the container
    return self._workDirInsideContainer

def get():
  return DockerBackend
