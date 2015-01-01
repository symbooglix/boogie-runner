# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import abc
import logging
import os
import pprint
import psutil
import re
import shutil
import time

_logger = logging.getLogger(__name__)

class RunnerBaseException(Exception):
  def __init__(self, msg):
    self.msg = msg

class ResultType:
  NO_BUGS_NO_TIMEOUT = 0
  BUGS_NO_TIMEOUT = 1
  NO_BUGS_TIMEOUT = 2
  BUGS_TIMEOUT = 3
  UNKNOWN = 4

class RunnerBaseClass(metaclass=abc.ABCMeta):
  staticCounter = 0
  _toolInDockerImageCache = {}

  def __init__(self, boogieProgram, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))

    # Unique ID (we assume this constructor is never called in parallel)
    self.uid = RunnerBaseClass.staticCounter
    RunnerBaseClass.staticCounter += 1

    if not os.path.isabs(boogieProgram):
      raise RunnerBaseException(
        'Boogie program ("{}")must be absolute path'.format(boogieProgram))

    if not os.path.exists(boogieProgram):
      raise RunnerBaseException(
        'Boogie program ("{}") does not exist'.format(boogieProgram))

    self.program = boogieProgram

    if not 'tool_path' in rc:
      raise RunnerBaseException('"tool_path" missing from "runner_config"')

    if not os.path.isabs(rc['tool_path']):
      raise RunnerBaseException('"tool_path" must be an absolute path')

    self.toolPath = rc['tool_path']

    # Check if docker will be used in this runner
    self.useDocker = 'docker' in rc

    self.dockerImage = None
    self.dockerVolume = None
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
        self.dockerVolume = dockerConfig['volume']
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

    removeWorkDirs = False
    try:
      removeWorkDirs = rc['remove_work_dirs']
      if not isinstance(removeWorkDirs, bool):
        raise RunnerBaseException('"remove_work_dirs" must be boolean')
    except KeyError:
      pass

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

    # Sanity checks
    if os.path.exists(self.workingDirectory):
      if not removeWorkDirs:
        raise RunnerBaseException(
          'workingDirectory "{}" already exists'.format(self.workingDirectory))
      else:
        _logger.warning(
          'Removing working directory "{}" and its contents'.format(self.workingDirectory))
        shutil.rmtree(self.workingDirectory)

    # Create the working directory
    os.mkdir(self.workingDirectory)

    self.logFile = os.path.join(self.workingDirectory, "log.txt")

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
  def workDirName(self):
    # We need to use the program name to handle the case where there are multiple
    # boogie programs in the same directory
    mangled = os.path.basename(self.program).replace(' ','.')
    return "{}.{}.br.d".format(self.name, mangled)

  @property
  def workingDirectory(self):
    return os.path.join(os.path.dirname(os.path.abspath(self.program)), self.workDirName)

  @abc.abstractmethod
  def run(self):
    pass

  def getResults(self):
    results = {}
    results['program'] = self.program
    results['total_time'] = self.time
    results['working_directory'] = self.workingDirectory

    # Sub classes should set this appropriately
    results['result'] = ResultType.UNKNOWN

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
      return os.path.join(self.dockerVolume, progFilename)

    return self.program

  def runTool(self, cmdLine, isDotNet, envExtra = {}):
    finalCmdLine = list(cmdLine)
    if isDotNet and os.name == 'posix':
      finalCmdLine = ['mono'] + finalCmdLine


    env = {}
    env.update(envExtra)
    # Setup environment to enforce memory limit
    if self.maxMemoryInMB > 0:
      if not isDotNet:
        raise NotImplementedError('Enforcing memory limit when not using mono')

      env['MONO_GC_PARAM'] = '-max-heap-size={}m'.format(self.maxMemoryInMB)

    _logger.debug('Running: {}\nwith env:{}'.format(
      pprint.pformat(finalCmdLine),
      pprint.pformat(env)))
    
    # Run the tool
    exitCode = None
    process = None
    startTime = time.perf_counter()
    with open(self.logFile, 'w') as f:
      try:
        process = psutil.Popen(finalCmdLine,
                                cwd=self.workingDirectory,
                                stdout=f,
                                stderr=f,
                                env=env)
        exitCode = process.wait(timeout=self.maxTimeInSeconds)
      except psutil.TimeoutExpired as e:
        # Gently terminate
        process.terminate()
        time.sleep(1)
        # Now aggresively kill
        process.kill()

        endTime = time.perf_counter()
        self.time = endTime - startTime

        raise e
      finally:
        endTime = time.perf_counter()
        self.time = endTime - startTime

    return exitCode
