# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import functools
import logging
import os
import re

_logger = logging.getLogger(__name__)

class KleeAnalyser(AnalyserBaseClass):
  def __init__(self, resultDict):
    super(KleeAnalyser, self).__init__(resultDict)
    assert 'backend_timeout' in self._resultDict

  @property
  def foundBug(self):
    if self.exitCode == 0:
      return False

    if self.ranOutOfTime:
      return False

    # Should we do more to inspect the bug type?
    if self.exitCode == 1:
      with open(self.logFile, 'r') as f:
        msgs = [
            # This regex vaguely matches an error message containing a source file
            # name and line number
            re.compile(r'^KLEE: ERROR:\s*.+\.(c|i|cpp|cxx):\d+:'),
               ]
        for line in f:
          for msgRegex in msgs:
            m = msgRegex.search(line)
            if m != None:
              return True
    return False

  @property
  def failed(self):
    if self.ranOutOfMemory:
      return True

    if self.ranOutOfTime:
      return False # Timeout is not a failure

    if self.exitCode == 0:
      return False

    if self.foundBug:
      return False

    # Should we use these? It can lead to weird scenarios because
    # we can have a failed klee_assume() call but later find a bug on
    # a different path.
    # Looks for certain failure messages
    #msgs = [ re.compile('Error: failed external call'),
    #         re.compile('invalid klee_assume call'),
    #         re.compile('ERROR:\s+unable to load symbol'),
    #         re.compile('ERROR:\s+Code generator does not support intrinsic function'),
    #       ]

    # We don't know what happened. Probably a failure worth investigating
    return True


  @property
  def hitHardTimeout(self):
    return self._resultDict['backend_timeout']

  # Override normal implementation
  @property
  @functools.lru_cache(maxsize=1)
  def ranOutOfTime(self):
    if self.hitHardTimeout:
      return True

    # Detect KLEE's soft timer
    with open(self.logFile, 'r') as f:
      r = re.compile(r'HaltTimer\s+invoked', flags=re.IGNORECASE)
      for line in f:
        m = r.search(line)
        if m != None:
          return True

    return False


  def getAnalysesDict(self):
    results = super(KleeAnalyser, self).getAnalysesDict()
    return results

def get():
  return KleeAnalyser
