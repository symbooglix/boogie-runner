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

    # Should we do more to inspect the bug type?
    if self.exitCode == 1:
      # Note eliminating self.failed case is important because
      # we don't want assume failures to be flagged as bugs.
      if not (self.failed or self.ranOutOfTime):
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
    return None

  @property
  def failed(self):
    if self.ranOutOfMemory:
      return True

    if self.ranOutOfTime:
      return False # Timeout is not a failure

    if self.exitCode == 0:
      return False

    # Looks for certain failure messages
    msgs = [ re.compile('Error: failed external call'),
             re.compile('invalid klee_assume call'),
           ]
    with open(self.logFile, 'r') as f:
      for line in f:
        for msgRegex in msgs:
          m = msgRegex.search(line)
          if m != None:
            return True

    # This exit code is also used when finding a bug or a timeout
    # occurs. We've eliminated the cases we want to treat as failure
    # for this exit code so the remaining cases aren't "failures"
    if self.exitCode == 1:
      return False

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
