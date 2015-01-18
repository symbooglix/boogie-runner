# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. ResultType import ResultType
import logging
import os
import psutil
import re
import sys
import yaml

_logger = logging.getLogger(__name__)

class GPUVerifyRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class GPUVerifyRunner(RunnerBaseClass):
  softTimeoutDiff = 5

  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(GPUVerifyRunner, self).__init__(boogieProgram, workingDirectory, rc)

    # Sanity checks
    # TODO

    if self.maxTimeInSeconds > 0 and (
       self.maxTimeInSeconds <= self.softTimeoutDiff):
      raise GPUVerifyRunnerException('Need larger timeout')

    if not self.toolPath.endswith('.py'):
      raise GPUVerifyRunnerException(
        'toolPath needs to be the GPUVerify python script')


  @property
  def name(self):
    return "gpuverify"

  @property
  def timeoutWasHit(self):
    if self.hitHardTimeout:
      return True
    else:
      if self.exitCode == 7:
        return True
      else:
        return False

  def getResults(self):
    results = super(GPUVerifyRunner, self).getResults()
    if not self.hitHardTimeout:
      results['exit_code'] = self.exitCode
    return results

  @property
  def failed(self):
    if self.hitHardTimeout:
      return False

    if self.exitCode != 0 and self.exitCode != 6:
      return True

    return self._raisedException()


  def _raisedException(self):
    # HACK: Look for uncaught exceptions in log output.
    if os.path.exists(self.logFile):
      with open(self.logFile, 'r') as f:
        r = re.compile(r'FATAL UNHANDLED EXCEPTION')
        for line in f:
          m = r.search(line)
          if m != None:
            _logger.error('GPUVerify raised an exception')
            return True

    return False

  @property
  def foundBug(self):
    if self.hitHardTimeout:
      return False

    # First try read the tool output and extract if we found a bug
    verifiedCount=0
    errorCount=0
    if os.path.exists(self.logFile):
      with open(self.logFile, 'r') as f:
        r = re.compile(r'GPUVerify kernel analyser finished with (\d+) verified, (\d+) error')
        for line in f:
          m = r.match(line)
          if m != None:
            verifiedCount = int(m.group(1))
            errorCount = int(m.group(2))
        _logger.info('Found {} verified, {} errors'.format(verifiedCount, errorCount))

      if errorCount > 0:
        return True
      elif verifiedCount > 0:
        return False

      # We couldn't parse out the information we wanted so fallback on the exit code
      _logging.warning('Failed to parse info from GPUVerify output, falling back on exit code')

      # GPUVerify exit codes are taken from
      # GPUVerifyScript/error_codes.py
      #
      #   SUCCESS = 0
      #   ...
      #   GPUVERIFYVCGEN_ERROR = 5
      #   BOOGIE_ERROR = 6
      #   TIMEOUT = 7
    if self.exitCode == 0 or self.exitCode == 7:
      return False
    elif self.exitCode == 6:
      # Workaround design flaw in GPUVerify. This exit code
      # can also be emitted if GPUVerify hits an exception
      if self._raisedException():
        return None
      else:
        return True # bug report should been emitted.
    else:
      return None

  def run(self):
    self.hitHardTimeout = False

    # Run using python interpreter
    cmdLine = [ sys.executable, self.toolPath ]

    # Set a soft timeout
    softTimeout = self.maxTimeInSeconds - self.softTimeoutDiff
    cmdLine.append('--timeout={}'.format(softTimeout))


    # Note we ignore self.entryPoint

    # GPUVerify needs PATH environment variable set
    env = {}
    path = os.getenv('PATH')
    if path == None:
      path = ""

    env['PATH'] = path

    # THIS IS A HACK
    # GPUVerify needs the local/group size to be passed
    # We're passing an already processed bpl file
    # so that information is already part of the Boogie
    # program
    # rather than trying to work out what was passed
    # just pass arbitary global and local size and hope
    # this doesn't break anything
    cmdLine.append('--local_size=2')
    cmdLine.append('--num_groups=2')

    cmdLine.extend(self.additionalArgs)

    # Add the boogie source file as last arg
    cmdLine.append(self.programPathArgument)

    # We assume that Boogie has no default timeout
    # so we force the timeout within python
    self.exitCode = None
    try:
      self.exitCode = self.runTool(cmdLine,
        isDotNet=False,
        envExtra=env)
    except psutil.TimeoutExpired as e:
      self.hitHardTimeout = True
      _logger.warning('GPUVerify hit hard timeout')

def get():
  return GPUVerifyRunner
