# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. ResultType import ResultType
from .. Analysers.Symbooglix import SymbooglixAnalyser
import logging
import os
import psutil
import yaml

_logger = logging.getLogger(__name__)

class SymbooglixRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class SymbooglixRunner(RunnerBaseClass):
  softTimeoutDiff = 10
  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(SymbooglixRunner, self).__init__(boogieProgram, workingDirectory, rc)

    # Sanity checks

    # We handle timeout ourselves, don't let the user set it
    for arg in self.additionalArgs:
      if arg.startswith('--timeout='):
        raise SymbooglixRunnerException(
          '--timeout must not be specified')

    # If we have a timeout it needs to be more than softTimeoutDiff
    # seconds because we give symbooglix a soft timeout of
    # maxTimeInSeconds - softTimeoutDiff
    # We do this because symbooglix may take a while to complete
    # once it hits the softimeout.
    if self.maxTimeInSeconds > 0 and (
       self.maxTimeInSeconds <= self.softTimeoutDiff):
      raise SymbooglixRunnerException('Need larger timeout')

  @property
  def name(self):
    return "symbooglix"

  def GetNewAnalyser(self):
    return SymbooglixAnalyser(self.exitCode, self.logFile, self.hitHardTimeout)

  @property
  def timeoutWasHit(self):
    if not self.hitHardTimeout:
      return self.exitCode == 2 or self.exitCode == 3
    else:
      return True

  def getResults(self):
    results = super(SymbooglixRunner, self).getResults()
    results['sbx_dir'] = self.outputDir

    results['hit_hard_timeout'] = self.hitHardTimeout
    return results

  def run(self):
    # Build the command line
    cmdLine = [ self.toolPath ] + self.additionalArgs

    # symbooglix outputdir
    self.outputDir = os.path.join(self.workingDirectory, "sbx")
    cmdLine.append('--output-dir={}'.format(self.outputDir))

    # Set implementation to enter
    cmdLine.append('--entry-points={}'.format(self.entryPoint))

    # Compute soft timeout and add as command line param
    softTimeout = self.maxTimeInSeconds - self.softTimeoutDiff
    assert softTimeout > 0
    cmdLine.append('--timeout={}'.format(softTimeout))

    # Add the source file as the last arg
    cmdLine.append(self.programPathArgument)

    self.hitHardTimeout = False
    try:
      exitCode = self.runTool(cmdLine, isDotNet=True)
      assert exitCode == self.exitCode
    except psutil.TimeoutExpired as e:
      self.hitHardTimeout = True
      _logger.warning('Hard timeout hit')

def get():
  return SymbooglixRunner
