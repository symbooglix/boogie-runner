# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import logging
import os
import re

_logger = logging.getLogger(__name__)

class GPUVerifyAnalyser(AnalyserBaseClass):
  def __init__(self, exitCode, logFile, useDocker, hitHardTimeout, **kargs):
    super(GPUVerifyAnalyser, self).__init__(exitCode, logFile, useDocker, **kargs)
    self.hitHardTimeout = hitHardTimeout

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
      _logger.warning('Failed to parse info from GPUVerify output, falling back on exit code')

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
      if self.raisedException:
        return None
      else:
        return True # bug report should been emitted.
    else:
      return None

  @property
  def failed(self):
    if self.hitHardTimeout:
      return False

    if self.exitCode != 0 and self.exitCode != 6:
      return True

    return self.raisedException

  # FIXME: Remove this, GPUVerify has been fixed so we can rely on exit codes
  @property
  def raisedException(self):
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
  def ranOutOfMemory(self):
    # FIXME: Find a way to detect this
    return None

def get():
  return GPUVerifyAnalyser
