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
    elif self.exitCode == 0 or self.exitCode == 3:
      return False
    else:
      return None

  @property
  def failed(self):
    if self.hitHardTimeout:
      return False # Timeout is not a failure

    # All exit codes above 4 indicate something went badly wrong
    return self.exitCode > 4 or self.exitCode == 1

  @property
  def ranOutOfMemory(self):
    return self.exitCode == 5

def get():
  return SymbooglixAnalyser
