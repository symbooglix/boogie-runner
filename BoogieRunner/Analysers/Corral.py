# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import logging
import os
import re

_logger = logging.getLogger(__name__)

class CorralAnalyser(AnalyserBaseClass):
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

  def getAnalysesDict(self):
    results = super(CorralAnalyser, self).getAnalysesDict()
    results['bound_hit'] = self.hitRecursionBound
    return results

def get():
  return CorralAnalyser
