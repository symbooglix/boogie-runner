# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import logging
import os
import re

_logger = logging.getLogger(__name__)

class SymbooglixAnalyser(AnalyserBaseClass):
  def __init__(self, exitCode, logFile, useDocker, hitHardTimeout, **kargs):
    super(SymbooglixAnalyser, self).__init__(exitCode, logFile, useDocker, **kargs)
    self.hitHardTimeout = hitHardTimeout

  @property
  def foundBug(self):
    if self.hitHardTimeout:
      # FIXME: We need to examine the output to see what happened
      _logger.error('FIXME: Need to examine symbooglix\'s working dir')
      return None

    # Use Symbooglix exitCode:
    if self.exitCode == 2 or self.exitCode == 4:
      return True
    elif self.exitCode == 0 or self.exitCode == 3 or self.exitCode == 9 or self.exitCode == 10:
      # NO_ERRORS_NO_TIMEOUT_BUT_FOUND_SPECULATIVE_PATHS : 9
      # NO_ERRORS_NO_TIMEOUT_BUT_HIT_BOUND : 10
      return False
    else:
      return None

  @property
  def failed(self):
    if self.hitHardTimeout:
      return False # Timeout is not a failure

    # We do not consider 9 or 10 exit codes as failure
    # NO_ERRORS_NO_TIMEOUT_BUT_FOUND_SPECULATIVE_PATHS : 9
    # NO_ERRORS_NO_TIMEOUT_BUT_HIT_BOUND : 10
    if self.exitCode == 9 or self.exitCode == 10:
      return False

    # All exit codes above 4 indicate something went badly wrong
    return self.exitCode > 4 or self.exitCode == 1

  @property
  def hitBound(self):
    # Finding a speculative path isn't quite the same as hitting
    # a bound but it certainly isn't fullying exploring the program
    # or finding a bug
    return self.exitCode == 10 or self.foundSpeculativePathsAndNoBug

  @property
  def foundSpeculativePathsAndNoBug(self):
    return self.exitCode == 9

  def getAnalysesDict(self):
    results = super(SymbooglixAnalyser, self).getAnalysesDict()
    results['bound_hit'] = self.hitBound
    results['speculative_paths_nb'] = self.foundSpeculativePathsAndNoBug
    return results

def get():
  return SymbooglixAnalyser
