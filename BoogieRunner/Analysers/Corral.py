# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import logging
import os
import re

_logger = logging.getLogger(__name__)

class CorralAnalyser(AnalyserBaseClass):
  def __init__(self, exitCode, logFile, useDocker, **kargs):
    super(CorralAnalyser, self).__init__(exitCode, logFile, useDocker, **kargs)

  @property
  def foundBug(self):
    if not os.path.exists(self.logFile):
      _logger.error('Could not find log file')
      # We don't know what happened
      return None

    with open(self.logFile, 'r') as f:
      # This is kind of a hack to detect if a bug was found
      # by Corral. Corral needs something better
      r = re.compile(r'Program has a potential bug: True bug')

      for line in f:
        m = r.search(line)
        if m != None:
          return True

    return False

  @property
  def failed(self):
    if self.exitCode == None:
      return False # Timeout is not failure

    return self.exitCode != 0

  @property
  def hitRecursionBound(self):
    """
    Opens log output and checks if recursion bound was hit
    """
    if not os.path.exists(self.logFile):
      _logginer.error('could not find log file')
      return None

    with open(self.logFile, 'r') as f:
      r = re.compile(r'Reached recursion bound of')
      for line in f:
        m = r.search(line)
        if m != None:
          return True

    return False

  @property
  def ranOutOfMemory(self):
    if not self.failed:
      return False

    if not os.path.exists(self.logFile):
      _logger.error('Could not find log file')
      # We don't know what happened
      return None

    with open(self.logFile, 'r') as f:
      # These are hacks to detect if we ran out of memory. They are mono specific

      gcError = re.compile(r'Error: Garbage collector could not allocate')

      """
        This is a hack to match lines like

        at (wrapper managed-to-native) object.__icall_wrapper_mono_gc_alloc_vector (intptr,intptr,intptr) <0xffffffff>

        OR

        at (wrapper managed-to-native) object.__icall_wrapper_mono_gc_alloc_string (intptr,intptr,int) <0xffffffff>
      """
      mightBeMonoStackTrace = False
      nativeCodeAllocFailureHint = re.compile(r'^\s*at\s+\(wrapper managed-to-native\)\s+object\..+mono_gc_alloc')
      for line in f:
        m = gcError.match(line)
        if m != None:
          _logger.info('Detected garbage collection error')
          return True

        if mightBeMonoStackTrace:
          m = nativeCodeAllocFailureHint.match(line)
          if m != None:
            _logger.info('Detected mono runtime crash that is probably an out of memory problem')
            return True

        if line.startswith('Stacktrace:'):
          # We might of hit the beginning of a mono stack trace
          mightBeMonoStackTrace = True

    return False

  def getAnalysesDict(self):
    results = super(CorralAnalyser, self).getAnalysesDict()
    results['recursion_bound_hit'] = self.hitRecursionBound
    return results

def get():
  return CorralAnalyser
