# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import abc
import logging
import os
import pprint
import psutil
import re
import shutil
import sys
import time
from .. ResultType import ResultType

_logger = logging.getLogger(__name__)

class RunnerBaseException(Exception):
  def __init__(self, msg):
    self.msg = msg

class RunnerBaseClass(metaclass=abc.ABCMeta):
  staticCounter = 0
  _toolInDockerImageCache = {}

  # FIXME: Add a lock so instances cannot be created in parallel
  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))

    # Unique ID (we assume this constructor is never called in parallel)
    self.uid = RunnerBaseClass.staticCounter
    RunnerBaseClass.staticCounter += 1

    self._timeoutHit = False

    if not os.path.isabs(boogieProgram):
      raise RunnerBaseException(
        'Boogie program ("{}")must be absolute path'.format(boogieProgram))

    if not os.path.exists(boogieProgram):
      raise RunnerBaseException(
        'Boogie program ("{}") does not exist'.format(boogieProgram))

    self.program = boogieProgram

    # Check working directory
    if not os.path.isabs(workingDirectory):
      raise RunnerBaseException(
        'working directory "{}" must be an absolute path'.format(workingDirectory))

    if not os.path.exists(workingDirectory):
      raise RunnerBaseException(
        'working directory "{}" does not exist'.format(workingDirectory))

    if not os.path.isdir(workingDirectory):
      raise RunnerBaseException(
        'Specified working directory ("{}") is not a directory'.format(workingDirectory))

    # Check the directory is empty
    firstLevel = next(os.walk(workingDirectory, topdown=True))
    if len(firstLevel[1]) > 0 or len(firstLevel[2]) > 0:
      raise RunnerBaseException(
        'working directory "{}" is not empty'.format(workingDirectory))

    # Set working directory and create empty log file in it This should avoid
    # there being two instances of this class using the same working directory
    # (due to empty dir check) provided the instances are created sequentially.
    self.workingDirectory = workingDirectory
    with open(self.logFile, 'w') as f:
      pass

    if not isinstance(rc, dict):
      raise RunnerBaseException('Config passed to runner must be a dictionary')

    if not 'tool_path' in rc:
      raise RunnerBaseException('"tool_path" missing from "runner_config"')

    self.toolPath = os.path.expanduser(rc['tool_path'])
    if not os.path.isabs(self.toolPath):
      raise RunnerBaseException('"tool_path" must be an absolute path')


    # Check if docker will be used in this runner
    self.useDocker = 'docker' in rc

    self.dockerImage = None
    self.dockerSourceVolume = None
    if self.useDocker:
      # Check that the docker image is specified correctly
      _logger.info('Using docker')

      dockerConfig = rc['docker']
      if not isinstance(dockerConfig, dict):
        raise BoogalooRunnerException('"docker" key must map to a dictionary')

      if not 'image' in dockerConfig:
        raise BoogalooRunner('"image" missing from docker config')

      self.dockerImage = dockerConfig['image']

      if not isinstance(self.dockerImage, str):
        raise BoogalooRunnerException(
          '"image" must be a string that is a valid docker image name')

      if len(self.dockerImage) == 0:
        raise BoogalooRunnerException('"image" cannot be an empty string')

      # Get the docker volume location (inside the container)
      try:
        self.dockerSourceVolume = dockerConfig['volume']
      except KeyError:
        raise BoogalooRunnerException('"volume" not specified for docker container')

      checkImg = False
      try:
        # Try the cache first
        if self.toolPath in RunnerBaseClass._toolInDockerImageCache[self.dockerImage]:
          checkImg = False
          _logger.debug('Cache hit not checking if {} is in docker image {}'.format(
          self.toolPath, self.dockerImage))
          checkImg = False
        else:
          checkImg = True
      except KeyError:
        checkImg = True

      if checkImg:
        # check the tool exists inside the container
        _logger.debug('Cache miss, checking if {} is in docker image {}'.format(
          self.toolPath, self.dockerImage))
        process = psutil.Popen(['docker','run','--rm', self.dockerImage, 'ls', self.toolPath])
        exitCode = process.wait()
        if exitCode != 0:
          raise RunnerBaseException('"{}" (tool_path) does not exist inside container'.format(
            self.toolPath))

        toolsInDockerImage = None
        try:
          toolsInDockerImage = RunnerBaseClass._toolInDockerImageCache[self.dockerImage]
        except KeyError:
          toolsInDockerImage = set()
          RunnerBaseClass._toolInDockerImageCache[self.dockerImage] = toolsInDockerImage

        toolsInDockerImage.add(self.toolPath)

    else:
      # check the tool exists in the current filesystem
      if not os.path.exists(self.toolPath):
        raise RunnerBaseException('tool_path set to "{}", but it does not exist'.format(self.toolPath))

    try:
      self.maxMemoryInMB = rc['max_memory']
    except KeyError:
      logging.info('"max_memory" not specified, assuming no tool memory limit')
      self.maxMemoryInMB = 0

    if self.maxMemoryInMB < 0:
      raise RunnerBaseException('"max_memory" must be > 0')

    try:
      self.maxTimeInSeconds = rc['max_time']
    except KeyError:
      logging.info('"max_time" not specified, assuming no tool timeout')
      self.maxTimeInSeconds = 0

    if self.maxTimeInSeconds < 0:
      raise RunnerBaseException('"max_time" must be > 0')

    try:
      entryPoint = rc['entry_point']
      if isinstance(entryPoint,str):
        # Entry point specified directly
        self.entryPoint = entryPoint
      else:
        # find the entry point in the program
        self.entryPoint = self.findEntryPoint(entryPoint)

    except KeyError:
      logging.info('"entry_point" not specified, assuming main is entry point')
      self.entryPoint = 'main'

    self.additionalArgs = [ ]
    if 'additional_args' in rc:
      if not isinstance(rc['additional_args'],list):
        raise RunnerBaseException('"additional_args" should be a list')

      for arg in rc['additional_args']:
        if not isinstance(arg, str):
          raise RunnerBaseException('Found additional argument that is not a string')

        self.additionalArgs.append(arg)

    # Set environment variables
    self.toolEnvironmentVariables = {}
    if 'env' in rc:
      if not isinstance(rc['env'],dict):
        raise RunnerBaseException('"env" must map to a dictionary')

      # Go through each key, value pair making sure they are the right type
      for key, value in rc['env'].items():
        if not isinstance(key, str):
          raise RunnerBaseException('key "{}" must be a string'.format(key))

        if not isinstance(value, str):
          raise RunnerBaseException('Value for key "{}" must be a string'.format(key))

        self.toolEnvironmentVariables[key] = value

    # Set path to mono if specified
    self.monoExecutable = "mono"
    try:
      self.monoExecutable = rc['mono_path']
      if not isinstance(self.monoExecutable, str):
        raise RunnerBaseException('"mono_path" must map to a string')

      # Allow ~ to be used in config by expanding it to full absolute path
      self.monoExecutable = os.path.expanduser(self.monoExecutable)

      if not os.path.isabs(self.monoExecutable):
        raise RunnerBaseException('"mono_path" does not map to a path that is absolute ({})'.format(self.monoExecutable))
      if not os.path.exists(self.monoExecutable):
        # FIXME: we probably don't want to do this check if using docker.
        raise RunnerBaseException('"mono_path" does not map to a path that exists ({})'.format(self.monoExecutable))
    except KeyError:
      pass

    # Note we just use "mono" if it is not specified. We don't check if mono is available in
    # PATH because
    # * When running natively PATH is not propagated into the running environment of the tool
    # * We might be running inside a Docker container

  def findEntryPoint(self, constraint):
    if not isinstance(constraint, dict):
      raise RunnerBaseException("Expected \"entry_point\" to be a dictionary")

    if not "use_bool_attribute" in constraint:
      raise RunnerBaseException("Expected \"use_bool_attribute\" under \"entry_point\"")

    attribute = constraint['use_bool_attribute']

    if (not isinstance(attribute,str)) or len(attribute) == 0:
      raise RunnerBaseException('"use_bool_attribute" must be a non empty string')

    entryPoint = None
    # Scan the Boogie program source code for the boolean attribute we want to match
    # The first procedure found with the attribute is returned
    with open(self.program) as f:
      lines = f.readlines()

      attrRegex = r'(?:\s*\{:\w+\s*\}\s*)*\s*'
      fullRegex = r'procedure\s*' + attrRegex + r'\{:' + attribute + r'\s*\}' + attrRegex + r'(?P<proc>\w+)\('
      r = re.compile(fullRegex)

      for line in [ l.rstrip() for l in lines]:
        m = r.match(line)
        #_logger.debug('Trying to match line \"{}\"'.format(line))
        if m != None:
          entryPoint = m.group('proc')
          break

    if entryPoint == None:
      raise RunnerBaseException(
        'Failed to find entry point in "{}" with attribute "{}"'.format(self.program, attribute))

    _logger.debug('Found entry point "{}" in "{}"'.format(entryPoint, self.program))
    return entryPoint

  @property
  def logFile(self):
    return os.path.join(self.workingDirectory, 'log.txt')

  @abc.abstractmethod
  def run(self):
    pass

  @property
  def timeoutWasHit(self):
    return self._timeoutHit

  @abc.abstractproperty
  def foundBug(self):
    """
      Return True if one or more bugs were found
      Return False if no bugs were found
      Return None if it could not be determined if bugs were found
    """
    pass

  def getResults(self):
    results = {}
    results['program'] = self.program
    results['total_time'] = self.time
    results['working_directory'] = self.workingDirectory

    # Sub classes should set this appropriately
    results['result'] = ResultType.UNKNOWN.value

    results['bug_found'] = self.foundBug
    results['timeout_hit'] = self.timeoutWasHit

    return results

  @abc.abstractproperty
  def name(self):
    pass

  @property
  def programPathArgument(self):
    """
      This the argument to pass to the tool when running.
      This should be used instead of ``self.program`` because
      this property takes into account if docker is being used
    """
    if self.useDocker:
      progFilename = os.path.basename(self.program)
      return os.path.join(self.dockerSourceVolume, progFilename)

    return self.program

  @property
  def dockerContainerName(self):
    return '{}-bg-{}-{}'.format(self.name, os.getpid(), self.uid)

  def runTool(self, cmdLine, isDotNet, envExtra = {}):
    finalCmdLine = []

    containerName=""
    if self.useDocker:
      finalCmdLine.extend(['docker', 'run', '--rm'])

      # Specifying tty prevents buffering of boogaloo's output
      finalCmdLine.append('--tty')

      # Setup the volume to mount the directory containing boogie program
      # we do this as as read-only volume
      volumeSrc = os.path.dirname(self.program)
      finalCmdLine.append('--volume={src}:{dest}:ro'.format(
        src=volumeSrc, dest=self.dockerSourceVolume))


      # Setup working directory inside the container (this is writable)
      # FIXME: We should make this settable from the config
      containerWorkDir = '/mnt/'
      finalCmdLine.append('--volume={src}:{dest}:rw'.format(src=self.workingDirectory, dest=containerWorkDir))
      finalCmdLine.append('--workdir={}'.format(containerWorkDir))

      finalCmdLine.append('--name={}'.format(self.dockerContainerName))

    # Set up the initial values of the environment variables.
    # Note we do not propagate the variables of the current environment.
    env = {}
    env.update(self.toolEnvironmentVariables)
    env.update(envExtra) # envExtra takes presedence
    # Setup memory limits

    # Setup environment to enforce memory limit
    useRlimit = False
    useUlimitHack = False
    useShell = False
    if self.maxMemoryInMB > 0:
      if self.useDocker:
        # Use docker to enforce the memory limit
        finalCmdLine.append('--memory={}m'.format(self.maxMemoryInMB))
      else:
        if isDotNet:
          env['MONO_GC_PARAM'] = '-max-heap-size={}m'.format(self.maxMemoryInMB)
        else:
          if sys.platform == 'linux':
            if getattr(psutil.Process, 'rlimit', None) == None:
              # Older kernels don't support rlimit
              useUlimitHack = True
              _logger.warning('Linux is being used but rlimit support was not found. You should upgrade your kernel!')
            else:
              useRlimit = True
          else:
            raise NotImplementedError(
              'Enforcing memory limit not supported (when not using docker or mono) when not using Linux')

    if self.useDocker:
      finalCmdLine.append(self.dockerImage)

    if isDotNet and os.name == 'posix':
      finalCmdLine.append(self.monoExecutable)

    # Now add the arguments
    finalCmdLine.extend(cmdLine)

    if useUlimitHack:
      _logger.warning('Using ulimit HACK')
      maxMemoryInKiB = self.maxMemoryInMB * 1024
      finalCmdLine = ['ulimit', '-SHv', str(maxMemoryInKiB), '&&'] + finalCmdLine
      # Use a string instead when invoking the shell directly
      finalCmdLine = ' '.join(finalCmdLine)
      assert isinstance(finalCmdLine, str)
      useShell = True

    _logger.debug('Running:\n{}\nwith env:{}'.format(
      pprint.pformat(finalCmdLine),
      pprint.pformat(env)))

    # Run the tool
    exitCode = None
    process = None
    startTime = time.perf_counter()
    with open(self.logFile, 'w') as f:
      try:
        _logger.debug('writing to log file {}'.format(self.logFile))
        if useShell:
          _logger.warning('Using shell instead of invoking tool directly!')
        process = psutil.Popen(finalCmdLine,
                                cwd=self.workingDirectory,
                                stdout=f,
                                stderr=f,
                                env=env,
                                shell=useShell)

        if useRlimit:
          numBytes = self.maxMemoryInMB * (2**20)
          _logger.debug('Using rlimit() to limit memory usage to {} MiB ({} bytes)'.format(
            self.maxMemoryInMB, numBytes))
          process.rlimit(psutil.RLIMIT_AS, (numBytes, numBytes))

        exitCode = process.wait(timeout=self.maxTimeInSeconds)
      except (psutil.TimeoutExpired, KeyboardInterrupt) as e:
        self._timeoutHit = True
        _logger.debug('Trying to terminate')
        # Gently terminate
        process.terminate()
        time.sleep(1)
        # Now aggresively kill
        _logger.debug('Trying to kill')
        process.kill()

        endTime = time.perf_counter()
        self.time = endTime - startTime

        if self.useDocker:
          # The container will carry on running so we need to kill it
          _logger.info('Trying to kill container {}'.format(self.dockerContainerName))
          process = psutil.Popen(['docker', 'kill', self.dockerContainerName])
          process.wait()

          # We also may need to manually remove the container
          _logger.info('Trying to remove container {}'.format(self.dockerContainerName))
          process = psutil.Popen(['docker', 'rm', self.dockerContainerName])
          process.wait()

        raise e
      finally:
        endTime = time.perf_counter()
        self.time = endTime - startTime

    return exitCode
