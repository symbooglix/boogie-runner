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
from .. import EntryPointFinder
from .. import BackendFactory

_logger = logging.getLogger(__name__)

class RunnerBaseException(Exception):
  def __init__(self, msg):
    self.msg = msg

class RunnerBaseClass(metaclass=abc.ABCMeta):
  staticCounter = 0

  def _checkBoogieProgram(self):
    if not os.path.isabs(self.program):
      raise RunnerBaseException(
        'Boogie program ("{}")must be absolute path'.format(self.program))

    if not os.path.exists(self.program):
      raise RunnerBaseException(
        'Boogie program ("{}") does not exist'.format(self.program))

  def _setupWorkingDirectory(self, workingDirectory):
    self.workingDirectory = workingDirectory
    if not os.path.isabs(self.workingDirectory):
      raise RunnerBaseException(
        'working directory "{}" must be an absolute path'.format(self.workingDirectory))

    if not os.path.exists(self.workingDirectory):
      raise RunnerBaseException(
        'working directory "{}" does not exist'.format(self.workingDirectory))

    if not os.path.isdir(self.workingDirectory):
      raise RunnerBaseException(
        'Specified working directory ("{}") is not a directory'.format(self.workingDirectory))

    # Check the directory is empty
    firstLevel = next(os.walk(self.workingDirectory, topdown=True))
    if len(firstLevel[1]) > 0 or len(firstLevel[2]) > 0:
      raise RunnerBaseException(
        'working directory "{}" is not empty'.format(self.workingDirectory))

  def _setupMaxMemory(self, rc):
    try:
      self.maxMemoryInMiB = rc['max_memory']
    except KeyError:
      _logger.info('"max_memory" not specified, assuming no tool memory limit')
      self.maxMemoryInMiB = 0

    if self.maxMemoryInMiB < 0:
      raise RunnerBaseException('"max_memory" must be > 0')

  def _setupMaxTime(self, rc):
    try:
      self._maxTimeInSeconds = rc['max_time']
    except KeyError:
      _logger.info('"max_time" not specified, assuming no tool timeout')
      self._maxTimeInSeconds = 0

    if self._maxTimeInSeconds < 0:
      raise RunnerBaseException('"max_time" must be > 0')

  # These two property decorators exist because GPUVerify and Symbooglix
  # runners need to modify the maxTimeInSeconds in their constructors.
  # Unfortunately the backend will have already been initialised with the
  # old time so we provide these methods to ensure the backend gets updated
  # too
  @property
  def maxTimeInSeconds(self):
    if self._backend == None:
      return self._maxTimeInSeconds
    else:
      return self._backend.timeLimit

  @maxTimeInSeconds.setter
  def maxTimeInSeconds(self, value):
    if not isinstance(value, int):
      raise RunnerBaseException('value must be an int')
    self._maxTimeInSeconds = value
    if self._backend != None:
      self._backend.timeLimit = value


  def _setupEntryPoint(self, rc):
    try:
      entryPoint = rc['entry_point']
      if isinstance(entryPoint,str):
        # Entry point specified directly
        self.entryPoint = entryPoint
      else:
        # find the entry point in the program
        self.entryPoint = self.findEntryPoint(entryPoint)

    except KeyError:
      _logger.warning('"entry_point" not specified, it is implementation defined what this runner will do')
      self.entryPoint = None

  def _setupProgramCopy(self, rc):
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

  def _setupAdditionalArgs(self, rc):
    self.additionalArgs = [ ]
    if 'additional_args' in rc:
      if not isinstance(rc['additional_args'],list):
        raise RunnerBaseException('"additional_args" should be a list')

      for arg in rc['additional_args']:
        if not isinstance(arg, str):
          raise RunnerBaseException('Found additional argument that is not a string')

        self.additionalArgs.append(arg)

  def _setupEnvironmentVariables(self, rc):
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

  def _setupMono(self, rc):
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

    self.monoArgs = [ ]
    try:
      self.monoArgs = rc['mono_args']
      if (not isinstance(self.monoArgs, list)) or len(self.monoArgs) == 0 or (not isinstance(self.monoArgs[0], str)):
        raise RunnerBaseException('"mono_args" must map to a non empty list of strings')
    except KeyError:
      pass

  def _setupStackSize(self, rc):
    try:
      self._stackSize = rc['stack_size']
      if isinstance(self._stackSize, str):
        if self._stackSize != 'unlimited':
          raise RunnerBaseException('If "stack_size" maps to a string it must be set to "unlimited"')
      elif isinstance(self._stackSize, int):
        if self._stackSize <= 0:
          raise RunnerBaseException('"stack_size" must be greater than 0')
      else:
        raise RunnerBaseException('"stack_size" has unexpected type')
    except KeyError:
      self._stackSize = None

  def _setupToolPath(self, rc):
    if not 'tool_path' in rc:
      raise RunnerBaseException('"tool_path" missing from "runner_config"')

    self.toolPath = os.path.expanduser(rc['tool_path'])
    if not os.path.isabs(self.toolPath):
      raise RunnerBaseException('"tool_path" must be an absolute path')

  def _setupBackend(self, rc):
    default="PythonPsUtil"
    if not 'backend' in rc:
      backendName = default
      _logger.warning('Backend not specified, using default backend "{}"'.format(default))
      backendSpecificOptions = {}
    else:
      backendDict = rc['backend']
      if not isinstance(backendDict, dict):
        raise RunnerBaseException('"backend" key must map to a dictionary')
      try:
        backendName = backendDict['name']
        if not isinstance(backendName, str):
          raise RunnerBaseException('backend "name" must be a string')
      except KeyError:
        raise RunnerBaseException('"name" key missing inside "backend"')

      # Backend specific options are optional
      backendSpecificOptions = backendDict.get('config', {})

    if not isinstance(backendSpecificOptions, dict):
      raise RunnerBaseException('"config" must map to a dictionary')

    # Check the keys of the backendSpecificOptions are strings
    for key in backendSpecificOptions.keys():
      if not isinstance(key, str):
        raise RunnerBaseException('The keys in "config" must be strings')

    self._backend = None
    backendClass = BackendFactory.getBackendClass(backendName)
    self._backend = backendClass(hostProgramPath=self._programPathOnHostToUse,
                                 workingDirectory=self.workingDirectory,
                                 timeLimit=self.maxTimeInSeconds,
                                 memoryLimit=self.maxMemoryInMiB,
                                 stackLimit=0 if self._stackSize == 'unlimited' else self._stackSize,
                                 **backendSpecificOptions)

    # Check the tool exists in the backend
    self._backend.checkToolExists(self.toolPath)

  def _readConfig(self, rc):
    if not isinstance(rc, dict):
      raise RunnerBaseException('Config passed to runner must be a dictionary')

    # Check for disallowed legacy config
    if 'docker' in rc:
      raise RunnerBaseException("'docker' is a legacy option which is no longer supported.")

    if 'memory_limit_enforcement' in rc:
      raise RunnerBaseException('"memory_limit_enforcement" is a legacy option which is no longer supported')

    self._setupToolPath(rc)
    self._setupProgramCopy(rc)
    self._setupMaxMemory(rc)
    self._setupMaxTime(rc)
    self._setupEntryPoint(rc)
    self._setupAdditionalArgs(rc)
    self._setupEnvironmentVariables(rc)
    self._setupMono(rc)
    self._setupStackSize(rc)

  @property
  def _programPathOnHostToUse(self):
    progFilename = os.path.basename(self.program)
    if self._copyProgramToWorkingDirectory:
      return os.path.join(self.workingDirectory, progFilename)
    else:
      return self.program

  # FIXME: Add a lock so instances cannot be created in parallel
  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))

    # Unique ID (we assume this constructor is never called in parallel)
    self.uid = RunnerBaseClass.staticCounter
    RunnerBaseClass.staticCounter += 1

    self._backendResult = None
    self.program = boogieProgram # FIXME: Hide this so if make copy we only expose that

    self._checkBoogieProgram()
    self._setupWorkingDirectory(workingDirectory)

    # FIXME: This is gross!
    # Create empty log file in it This should avoid
    # there being two instances of this class using the same working directory
    # (due to empty dir check) provided the instances are created sequentially.
    with open(self.logFile, 'w') as f:
      pass

    self._readConfig(rc)
    self._setupBackend(rc)

  def findEntryPoint(self, constraint):
    if not isinstance(constraint, dict):
      raise RunnerBaseException("Expected \"entry_point\" to be a dictionary")

    if not "use_bool_attribute" in constraint:
      raise RunnerBaseException("Expected \"use_bool_attribute\" under \"entry_point\"")

    attribute = constraint['use_bool_attribute']

    if (not isinstance(attribute,str)) or len(attribute) == 0:
      raise RunnerBaseException('"use_bool_attribute" must be a non empty string')

    entryPoint = EntryPointFinder.findEntryPointWithBooleanAttribute(
      attribute, self.program)

    if entryPoint == None:
      raise RunnerBaseException(
        'Failed to find entry point in "{}" with attribute "{}"'.format(self.program,
        attribute))

    _logger.debug('Found entry point "{}" in "{}"'.format(entryPoint, self.program))
    return entryPoint

  @property
  def logFile(self):
    return os.path.join(self.workingDirectory, 'log.txt')

  @abc.abstractmethod
  def run(self):
    pass

  # timeouts are a little different. An analyser needs
  # to determine if this happened so getResults() needs
  # to be called to determine this.
  #@property
  #def timeoutWasHit(self):

  @abc.abstractmethod
  def GetNewAnalyser(self, resultDict):
    pass

  @property
  def ranOutOfMemory(self):
    """
      Return True if the tool ran out of memory
      Return False if the tool did not run out of memory
      Return None if this could not be determined
    """
    return self._backendResult.outOfMemory

  @property
  def exitCode(self):
    return self._backendResult.exitCode

  @property
  def runTime(self):
    # Wallclock time
    return self._backendResult.runTime

  # Subclasses should override this and call it first
  # to populate the resultDict and then add to it as
  # necessary
  def _buildResultDict(self):
    results = {}
    results['program'] = self.program
    results['total_time'] = self.runTime
    results['working_directory'] = self.workingDirectory
    results['exit_code'] = self.exitCode
    #results['timeout_hit'] # The analyser now sets this
    results['out_of_memory'] = self.ranOutOfMemory
    results['log_file'] = self.logFile
    # This isn't the same as a timeout because the Analyser decides the
    # 'timeout_hit' field
    results['backend_timeout'] = self._backendResult.outOfTime
    results['user_cpu_time'] = self._backendResult.userCpuTime
    results['sys_cpu_time'] = self._backendResult.sysCpuTime
    return results

  def getResults(self):
    results = self._buildResultDict()

    # The anaylser will take a copy of the dictionary and
    # augment it with additional values
    analyser = self.GetNewAnalyser(results)
    newResults = analyser.getAnalysesDict()
    assert len(newResults) > len(results)
    assert 'bug_found' in newResults
    assert 'failed' in newResults
    assert 'timeout_hit' in newResults
    # Just check that one of the original fields is still there
    assert 'program' in newResults

    # Check that our current conventions are being enforced
    # Convention: If we ran_out_memory then that's a failure.
    # Is this really the right choice? We treat timeout
    # (exhaustion of time) as not a failure but out of memory
    # (exhausation of memory) as a failure.
    if self.ranOutOfMemory:
      assert newResults['failed'] == True

    return newResults

  @abc.abstractproperty
  def name(self):
    pass

  @property
  def programPathArgument(self):
    """
      This the argument to pass to the tool when running.
      This should be used instead of ``self.program`` because
      this property takes into account the backend being used.
    """
    return self._backend.programPath()

  @property
  def workingDirectoryInBackend(self):
    """
      This should be used if it is necessary to know the working
      directory path inside the environment of the backend
    """
    return self._backend.workingDirectoryInternal

  def kill(self, pause=0.0):
    """
    Subclasses need to override this if their
    run() method doesn't use runTool()
    """
    _logger.debug('Trying to kill {}'.format(self.name))
    self._backend.kill()

    if self._copyProgramToWorkingDirectory:
      toDelete=os.path.join(self.workingDirectory, os.path.basename(self.program))
      try:
        _logger.info('Removing copy of input program at "{}"'.format(toDelete))
        os.remove(toDelete)
      except Exception as e:
        _logger.error('Failed to delete copy of program at "{}"'.format(toDelete))
        _logger.debug(traceback.format_exc())
        pass

  def runTool(self, cmdLine, isDotNet, envExtra = {}):
    finalCmdLine = []
    self._memoryLimitHit = False

    if isDotNet and os.name == 'posix':
      finalCmdLine.append(self.monoExecutable)
      if len(self.monoArgs) > 0:
        finalCmdLine.extend(self.monoArgs)
    
    env = {}
    env.update(self.toolEnvironmentVariables)
    env.update(envExtra) # These take precendence

    # Now add the arguments
    finalCmdLine.extend(cmdLine)

    _logger.info('Running:\n{}\nwith env:{}'.format(
      pprint.pformat(finalCmdLine),
      pprint.pformat(env)))

    # Run the tool
    self._backendResult = self._backend.run(finalCmdLine, self.logFile, env)
    return self._backendResult
