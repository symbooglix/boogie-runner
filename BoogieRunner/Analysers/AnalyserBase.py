# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import abc

class AnalyserBaseClass(metaclass=abc.ABCMeta):
  def __init__(self, resultDict):
    # Quick sanity checks
    assert isinstance(resultDict, dict)
    assert 'exit_code' in resultDict
    assert 'log_file' in resultDict
    # Make sure we work on a copy
    self._resultDict = resultDict.copy()

  @abc.abstractproperty
  def foundBug(self):
    """
      Return True if one or more bugs were found
      Return False if no bugs were found
      Return None if it could not be determined if bugs were found
    """
    pass

  @abc.abstractproperty
  def failed(self):
    """
      Return True if execution of this runner failed
      Return False if execution of this runner succeeded
    """
    pass

  @property
  def exitCode(self):
    return self._resultDict['exit_code']

  @property
  def logFile(self):
    return self._resultDict['log_file']

  def getAnalysesDict(self):
    """
      Returns a dictionary of the results of
      Analyser analyses. Subclasses should override
      this if they provide additional analyses.
    """
    results = self._resultDict
    results['bug_found'] = self.foundBug
    results['failed'] = self.failed

    return results
