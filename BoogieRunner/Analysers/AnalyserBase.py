# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import abc

class AnalyserBaseClass(metaclass=abc.ABCMeta):
  def __init__(self, exitCode, logFile, **kargs):
    self.exitCode = exitCode
    self.logFile = logFile

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

  def getAnalysesDict(self):
    """
      Returns a dictionary of the results of
      Analyser analyses. Subclasses should override
      this if they provide additional analyses.
    """
    results = {}
    results['bug_found'] = self.foundBug
    results['failed'] = self.failed
    return results
