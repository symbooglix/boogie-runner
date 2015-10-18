# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import logging
import os
import re

_logger = logging.getLogger(__name__)

class BoogieAnalyser(AnalyserBaseClass):
  @property
  def foundBug(self):
    if not os.path.exists(self.logFile):
      _logger.error('Could not find log file')
      # This isn't a bug but the fact that the log output
      # is missing is an issue which needs attention
      return None

    with open(self.logFile, 'r') as f:
      # This is kind of a hack to detect if a bug was found
      # by Boogie. Boogie needs something better
      r = re.compile(r'Boogie program verifier finished with (\d+) verified, (?P<errors>\d+) error(s)?')

      bugsFound = None
      for line in f:
        m = r.search(line)
        if m != None:
          numOfErrors = int(m.group('errors'))
          if numOfErrors > 0:
            bugsFound = True
          else:
            bugsFound = False

    if bugsFound == None:
      _logger.error("Could not read report from log!")

    return bugsFound

  @property
  def failed(self):
    if self.ranOutOfMemory:
      return True

    if self.exitCode == None:
      return False # Timeout is not a failure

    if self.exitCode != 0:
      return True

    if self.foundBug == None:
      # In the way foundBug() currently works
      # a parse error will show up as returning None
      return True

    return False

def get():
  return BoogieAnalyser
