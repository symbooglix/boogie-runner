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
import traceback
import threading
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
    self._memoryLimitHit = None
    self.exitCode = None

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

    # Handle making a copy of the input boogie program if necessary
    self._copyProgramToWorkingDirectory = False
    try:
      self._copyProgramToWorkingDirectory = rc['copy_program_to_working_directory']
    except KeyError:
      pass

    if not isinstance(self._copyProgramToWorkingDirectory, bool):
      raise RunnerBaseException('"copy_program_to_working_directory" should map to a boolean')

    if self._copyProgramToWorkingDirectory:
      # Make the copy now
      _logger.info('Copying input program to {}'.format(self.workingDirectory))
      shutil.copy(self.program, self.workingDirectory)


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
          _logger.info('Cache hit not checking if {} is in docker image {}'.format(
          self.toolPath, self.dockerImage))
          checkImg = False
        else:
          checkImg = True
      except KeyError:
        checkImg = True

      if checkImg:
        # check the tool exists inside the container
        _logger.info('Cache miss, checking if {} is in docker image {}'.format(
          self.toolPath, self.dockerImage))
        process = psutil.Popen(['docker','run','--net=none', '--rm', self.dockerImage, 'ls', self.toolPath])
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

      if self.maxMemoryInMB > 0:
        if 'memory_limit_enforcement' in rc:

          if self.useDocker:
            raise RunnerBaseException('Cannot use "memory_limit_enforcement" when using Docker')

          if not isinstance(rc['memory_limit_enforcement'], dict):
            raise RunnerBaseException('"memory_limit_enforcement" should map to a dictionary')

          mleDict = rc['memory_limit_enforcement']
          if not 'enforcer' in mleDict:
            raise RunnerBaseException('"enforcer" key expected in "memory_limit_enforcement" dictionary')

          if mleDict['enforcer'] != 'poll':
            raise NotImplementedError('{} enforcer not supported'.format(mleDict['enforcer']))

          self.useMemoryLimitPolling = True

          if not 'time_period' in mleDict:
            raise RunnerBaseException('"time_period" key expected in "memory_limit_enforcement" dictionary')
          self.memoryLimitPollTimePeriodInSeconds = mleDict['time_period']

          if self.memoryLimitPollTimePeriodInSeconds < 1:
            raise RunnerBaseException('"time_period" must be 1 or greater')

          assert isinstance(self.memoryLimitPollTimePeriodInSeconds, int)
        else:
          # Set sensible defaults
          self.useMemoryLimitPolling = True
          self.memoryLimitPollTimePeriodInSeconds = 5
      else:
        self.useMemoryLimitPolling = False
        self.memoryLimitPollTimePeriodInSeconds = 0

    except KeyError:
      _logger.info('"max_memory" not specified, assuming no tool memory limit')
      self.maxMemoryInMB = 0
      self.useMemoryLimitPolling = False
      self.memoryLimitPollTimePeriodInSeconds = 0

    if self.maxMemoryInMB < 0:
      raise RunnerBaseException('"max_memory" must be > 0')

    try:
      self.maxTimeInSeconds = rc['max_time']
    except KeyError:
      _logger.info('"max_time" not specified, assuming no tool timeout')
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
      _logger.info('"entry_point" not specified, assuming main is entry point')
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

      attrRegex = r'(?:\s*\{:\w+\s*([0-9]+|"[^"]+?")?\}\s*)*\s*'
      procNameRegex = r'(?P<proc>[a-zA-Z_$][a-zA-Z_$0-9]*)'
      fullRegex = r'procedure\s*' + attrRegex + r'\{:' + attribute + r'\s*\}' + attrRegex + procNameRegex + r'\('
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

  @abc.abstractmethod
  def GetNewAnalyser(self):
    pass

  @property
  def ranOutOfMemory(self):
    """
      Return True if the tool ran out of memory
      Return False if the tool did not run out of memory
      Return None if this could not be determined
    """
    if self.useDocker:
      _logger.error('FIXME: Detecting memory limit being hit is not implemented when using Docker')
      return None
    else:
      return self._memoryLimitHit

  def getResults(self):
    results = {}
    results['program'] = self.program
    results['total_time'] = self.time
    results['working_directory'] = self.workingDirectory
    results['exit_code'] = self.exitCode
    results['timeout_hit'] = timeoutHit = self.timeoutWasHit
    results['out_of_memory'] = self.ranOutOfMemory

    analyser = self.GetNewAnalyser()
    # Add the results of Analyser
    results.update(analyser.getAnalysesDict())
    assert 'bug_found' in results
    assert 'failed' in results

    # HACK:
    # FIXME: Pass this information to the Analysers so they can handle it
    if self.ranOutOfMemory:
      _logger.warning('Setting "failed" to true due to running out of memory')
      results['failed'] = True

    bugFound = results['bug_found']
    runFailed = results['failed']

    # FIXME: Remove this, the bug_found, timeout_hit and failed keys
    # describe this.
    # Keep this classification for legacy reasons.
    resultEnum = ResultType.UNKNOWN
    if (not runFailed) and bugFound != None:
      if bugFound:
        if timeoutHit:
          resultEnum = ResultType.BUGS_TIMEOUT
        else:
          resultEnum = ResultType.BUGS_NO_TIMEOUT
      else:
        if timeoutHit:
          resultEnum = ResultType.NO_BUGS_TIMEOUT
        else:
          resultEnum = ResultType.NO_BUGS_NO_TIMEOUT

    results['result'] = resultEnum.value # Record the numeric value
    return results

  @abc.abstractproperty
  def name(self):
    pass

  @property
  def programPathArgument(self):
    """
      This the argument to pass to the tool when running.
      This should be used instead of ``self.program`` because
      this property takes into account if docker is being used and
      whether or not we need to operate on a copy of the boogie program
    """
    progFilename = os.path.basename(self.program)
    if self._copyProgramToWorkingDirectory:
      if self.useDocker:
        return os.path.join(self.dockerWorkDirVolume, progFilename)
      else:
        return os.path.join(self.workingDirectory, progFilename)
    else:
      if self.useDocker:
        return os.path.join(self.dockerSourceVolume, progFilename)
      else:
        return self.program

  @property
  def dockerContainerName(self):
    return '{}-bg-{}-{}'.format(self.name, os.getpid(), self.uid)

  @property
  def dockerWorkDirVolume(self):
    # FIXME: We should make this settable from the config
    return '/mnt/'

  def runTool(self, cmdLine, isDotNet, envExtra = {}):
    finalCmdLine = []
    self._memoryLimitHit = False

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
      finalCmdLine.append('--volume={src}:{dest}:rw'.format(src=self.workingDirectory, dest=self.dockerWorkDirVolume))
      finalCmdLine.append('--workdir={}'.format(self.dockerWorkDirVolume))

      finalCmdLine.append('--name={}'.format(self.dockerContainerName))

    # Set up the initial values of the environment variables.
    # Note we do not propagate the variables of the current environment.
    env = {}
    env.update(self.toolEnvironmentVariables)
    env.update(envExtra) # envExtra takes presedence
    # Setup memory limits

    # Setup environment to enforce memory limit if using docker
    if self.maxMemoryInMB > 0 and self.useDocker:
      finalCmdLine.append('--memory={}m'.format(self.maxMemoryInMB))
      _logger.info('Enforcing memory limit ({} MiB) using Docker'.format(self.maxMemoryInMB))

    if self.useDocker:
      finalCmdLine.append('--net=none') # No network access should be needed
      finalCmdLine.append(self.dockerImage)

    if isDotNet and os.name == 'posix':
      finalCmdLine.append(self.monoExecutable)

    # Now add the arguments
    finalCmdLine.extend(cmdLine)

    _logger.info('Running:\n{}\nwith env:{}'.format(
      pprint.pformat(finalCmdLine),
      pprint.pformat(env)))

    # Run the tool
    exitCode = None
    process = None
    startTime = time.perf_counter()
    with open(self.logFile, 'w') as f:
      try:
        _logger.info('writing to log file {}'.format(self.logFile))
        process = psutil.Popen(finalCmdLine,
                                cwd=self.workingDirectory,
                                stdout=f,
                                stderr=f,
                                env=env)

        if self.useMemoryLimitPolling:
          _logger.info('Enforcing memory limit ({} MiB) using polling time period of {} seconds'.format(self.maxMemoryInMB, self.memoryLimitPollTimePeriodInSeconds))
          self._memoryLimitPolling(process)

        _logger.info('Running with timeout of {} seconds'.format(self.maxTimeInSeconds))
        exitCode = process.wait(timeout=self.maxTimeInSeconds)
      except (psutil.TimeoutExpired, KeyboardInterrupt) as e:
        self._timeoutHit = True
        self._terminateProcess(process)

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
        self.exitCode = exitCode

        if self._copyProgramToWorkingDirectory:
          toDelete=os.path.join(self.workingDirectory, os.path.basename(self.program))
          try:
            _logger.info('Removing copy of input program at "{}"'.format(toDelete))
            os.remove(toDelete)
          except Exception as e:
            _logger.error('Failed to delete copy of program at "{}"'.format(toDelete))
            _logger.debug(traceback.format_exc())
            pass

    return exitCode

  def _getProcessMemoryUsageInMB(self, process):
    # use Virtual memory size rather than resident set
    return process.memory_info()[1] / (2**20)

  def _terminateProcess(self, process):
    # Gently terminate
    _logger.info('Trying to terminate PID:{}'.format(process.pid))
    process.terminate()
    time.sleep(1)
    # Now aggresively kill
    _logger.info('Trying to kill PID:{}'.format(process.pid))
    process.kill()

  def _memoryLimitPolling(self, process):
    """
      This function launches a new thread that will periodically
      poll the total memory usage of the tool that is being run.
      If it goes over the limit will kill it
    """
    _logger.debug('Launching memory limit polling thread with polling time period of {} seconds'.format(self.memoryLimitPollTimePeriodInSeconds))
    assert self.memoryLimitPollTimePeriodInSeconds > 0

    def threadBody():
      _logger.info('Starting thread')
      try:
        while process.is_running():
          time.sleep(self.memoryLimitPollTimePeriodInSeconds)
          totalMemoryUsage = 0
          totalMemoryUsage += self._getProcessMemoryUsageInMB(process)

          # The process might of forked so add the memory usage of its children too
          childCount = 0
          try:
            for childProc in process.children(recursive=True):
              totalMemoryUsage += self._getProcessMemoryUsageInMB(childProc)
              childCount += 1
          except psutil.NoSuchProcess:
            _logger.warning('Child process disappeared whilst examining it\'s memory use')

          _logger.debug('Total memory usage in MiB:{}'.format(totalMemoryUsage))
          _logger.debug('Total number of children: {}'.format(childCount))

          if totalMemoryUsage > self.maxMemoryInMB:
            _logger.warning('Memory limit reached (recorded {} MiB). Killing tool'.format(totalMemoryUsage))
            self._memoryLimitHit = True
            self._terminateProcess(process)
            break
      except psutil.NoSuchProcess:
        _logger.warning('Main process no longer available')

    thread = threading.Thread(target=threadBody, name='memory_poller', daemon=True)
    thread.start()
    return thread
