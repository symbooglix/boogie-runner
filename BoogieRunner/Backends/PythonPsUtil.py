# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . BackendBase import *
import logging
import pprint
import psutil
import threading
import time

_logger = logging.getLogger(__name__)

class PythonPsUtilBackendException(BackendException):
  pass

class PythonPsUtilBackend(BackendBaseClass):
  def __init__(self, hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, **kwargs):
    super().__init__(hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, **kwargs)
    memoryLimitTimePeriodKey = 'memory_limit_poll_time_period'
    if memoryLimitTimePeriodKey in kwargs:
      self.memoryLimitPollTimePeriodInSeconds = kwargs[memoryLimitTimePeriodKey]
      if memoryLimit == 0:
        raise PythonPsUtilBackendException('Cannot have "{}" specified with no memory limit'.format(
          memoryLimitTimePeriodKey))
    else:
      # default
      self.memoryLimitPollTimePeriodInSeconds = 0.5

    if not (isinstance(self.memoryLimitPollTimePeriodInSeconds, float) and
        self.memoryLimitPollTimePeriodInSeconds > 0.0 ):
      raise PythonPsUtilBackendException(
        '{} must be a float > 0.0'.format(memoryLimitTimePeriodKey))

    self._process = None
    self._eventObj = None

  @property
  def name(self):
    return "PythonPsUtil"

  def kill(self):
    if self._process != None:
      try:
        if self._process.is_running():
          self._terminateProcess(self._process, 0.0)
      except psutil.NoSuchProcess:
        pass

  def programPath(self):
    # We run directly on the host so nothing special here
    return self.hostProgramPath

  def run(self, cmdLine, logFilePath, envVars):
    self._outOfMemory = False

    # Set up the initial values of the environment variables.
    # Note we do not propagate the variables of the current environment.
    _logger.info('Running:\n{}\nwith env:{}'.format(
      pprint.pformat(cmdLine),
      pprint.pformat(envVars)))

    # Run the tool
    exitCode = None
    self._process = None
    startTime = time.perf_counter()
    pollThread = None
    self._outOfMemory = False
    outOfTime = False
    runTime = 0.0
    with open(logFilePath, 'w') as f:
      try:
        _logger.info('writing to log file {}'.format(logFilePath))
        preExecFn = None
        if self.stackLimit != None:
          preExecFn = self._setStacksize
          _logger.info('Using stacksize limit: {} KiB'.format(
          'unlimited' if self.stackLimit == 0 else self.stackLimit))
        self._process = psutil.Popen(cmdLine,
                                     cwd=self.workingDirectory,
                                     stdout=f,
                                     stderr=f,
                                     env=envVars,
                                     preexec_fn=preExecFn)

        if self.memoryLimit > 0:
          pollThread = self._memoryLimitPolling(self._process)

        _logger.info('Running with timeout of {} seconds'.format(self.timeLimit))
        exitCode = self._process.wait(timeout=self.timeLimit)
      except (psutil.TimeoutExpired) as e:
        outOfTime = True
        # Note the code in the finally block will sort out clean up
      finally:
        self.kill()

        # This is a sanity check to make sure that the memory polling thread exits
        # before this method exits
        if pollThread != None:
          if self._eventObj != None:
            self._eventObj.set() # Wake up polling thread if it's blocked on eventObj
          _logger.debug('Joining memory polling thread START')
          try:
            pollThread.join()
            _logger.debug('Joining memory polling thread FINISHED')
          except RuntimeError:
            _logger.error('RuntimeError waiting for memory polling thread to terminate')
        self._process = None

        endTime = time.perf_counter()
        runTime = endTime - startTime

    return BackendResult(exitCode, runTime, outOfTime, self._outOfMemory)
  def _setStacksize(self):
    """
      Designed to be called subprocess.POpen() after fork.
      It will set any limits as appropriate.
      Note do not try to use the _logger here are the file descriptors have been changed.
    """
    assert self.stackLimit != None
    assert isinstance(self.stackLimit, int)
    import resource
    if self.stackLimit == 0:
      resource.setrlimit(resource.RLIMIT_STACK, (resource.RLIM_INFINITY, resource.RLIM_INFINITY))
    else:
      resource.setrlimit(resource.RLIMIT_STACK, (self.stackLimit, self.stackLimit))

  def _getProcessMemoryUsageInMiB(self, process):
    # use Virtual memory size rather than resident set
    return process.memory_info()[1] / (2**20)

  def _terminateProcess(self, process, pause):
    assert isinstance(pause, float)
    assert pause >= 0.0
    # Gently terminate
    _logger.debug('Trying to terminate PID:{}'.format(process.pid))
    children = process.children(recursive=True)
    process.terminate()
    for child in children:
      try:
        _logger.debug('Trying to terminate child process PID:{}'.format(child.pid))
        child.terminate()
      except psutil.NoSuchProcess:
        pass

    # If requested give the process time to clean up after itself
    # if it is still running
    if self._processIsRunning(process) and pause > 0.0:
      time.sleep(pause)

    # Now aggresively kill
    _logger.info('Trying to kill PID:{}'.format(process.pid))
    children = process.children(recursive=True)
    process.kill()
    for child in children:
      try:
        _logger.info('Trying to kill child process PID:{}'.format(child.pid))
        child.kill()
      except psutil.NoSuchProcess:
        pass

  def _processIsRunning(self, process):
    return process.is_running() and not process.status() == psutil.STATUS_ZOMBIE

  def _memoryLimitPolling(self, process):
    """
      This function launches a new thread that will periodically
      poll the total memory usage of the tool that is being run.
      If it goes over the limit will kill it
    """
    assert self.memoryLimitPollTimePeriodInSeconds > 0
    assert self._outOfMemory == False

    # Other parts of the runner can can set on this to prevent this thread
    # from waiting on this Event object.
    self._eventObj = threading.Event()
    self._eventObj.clear()

    def threadBody():
      _logger.info('Launching memory limit polling thread for PID {} with polling time period of {} seconds'.format(
        process.pid, self.memoryLimitPollTimePeriodInSeconds))
      try:
        while self._processIsRunning(process):
          self._eventObj.wait(self.memoryLimitPollTimePeriodInSeconds)
          totalMemoryUsage = 0
          totalMemoryUsage += self._getProcessMemoryUsageInMiB(process)

          # The process might of forked so add the memory usage of its children too
          childCount = 0
          for childProc in process.children(recursive=True):
            try:
              totalMemoryUsage += self._getProcessMemoryUsageInMiB(childProc)
              childCount += 1
            except psutil.NoSuchProcess:
              _logger.warning('Child process disappeared whilst examining it\'s memory use')

          _logger.debug('Total memory usage in MiB:{}'.format(totalMemoryUsage))
          _logger.debug('Total number of children: {}'.format(childCount))

          if totalMemoryUsage > self.memoryLimit:
            _logger.warning('Memory limit reached (recorded {} MiB). Killing tool with PID {}'.format(totalMemoryUsage, process.pid))
            self._outOfMemory = True
            # Give the tool a chance to clean up after itself before aggressively killing it
            self._terminateProcess(process, pause=1.0)
            break
      except psutil.NoSuchProcess:
        _logger.warning('Main process no longer available')

    newThreadName = 'memory_poller-{}'.format(process.pid)
    thread = threading.Thread(target=threadBody, name=newThreadName, daemon=True)
    thread.start()
    return thread


def get():
  return PythonPsUtilBackend
