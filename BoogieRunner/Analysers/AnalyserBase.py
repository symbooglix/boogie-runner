# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import abc

class AnalyserBaseClass(metaclass=abc.ABCMeta):
  def __init__(self, exitCode, logFile, useDocker, **kargs):
    self.exitCode = exitCode
    self.logFile = logFile
    self.useDocker = useDocker

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

  @abc.abstractproperty
  def ranOutOfMemory(self):
    """
      Return True if the tool executed by the runner ran out of memory
      Return False if the tool executed by the Runner did not run out of memory
      Return None if this cannot be determined

      This is part of AnalyserBaseClass rather than a Runner class because we
      often have no nice way of determining whether or not a tool ran out of
      memory so often we are forced to parse the log file.
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
    results['out_of_memory'] = self.ranOutOfMemory
    return results
