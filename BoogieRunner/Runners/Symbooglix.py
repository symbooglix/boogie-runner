# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
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
  softTimeoutDiff = 180 # Allow 3 minutes for file logging to finish
  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(SymbooglixRunner, self).__init__(boogieProgram, workingDirectory, rc)

    # Sanity checks

    # We handle timeout ourselves, don't let the user set it
    for arg in self.additionalArgs:
      if arg.startswith('--timeout='):
        raise SymbooglixRunnerException(
          '--timeout must not be specified')

    # Symbooglix will respect the timeout it was given and will not
    # be able to find anymore bugs after the timeout was hit, however
    # it needs to be allowed extra time to perform clean up because
    # it will log many files useful for debugging.
    self.softTimeout = self.maxTimeInSeconds
    self.maxTimeInSeconds = self.softTimeout + self.softTimeoutDiff
    assert self.maxTimeInSeconds >= self.softTimeout

  @property
  def name(self):
    return "symbooglix"

  def GetNewAnalyser(self):
    return SymbooglixAnalyser(self.exitCode, self.logFile, self.useDocker, self.hitHardTimeout)

  # FIXME: This belongs in the analyser
  # but would require that it be aware of the soft-timeout
  @property
  def timeoutWasHit(self):
    if self.hitHardTimeout:
      return True

    if self.exitCode == 3 or self.exitCode == 4:
      # NO_ERRORS_TIMEOUT,
      # ERRORS_TIMEOUT,
      return True

    # Check if the soft timeout was hit
    if self.time > self.softTimeout:
      return True

    return False

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

    if self.entryPoint == None:
      _logger.warning('Entry point not specified!')
    else:
      # Set implementation to enter
      cmdLine.append('--entry-points={}'.format(self.entryPoint))

    # Force soft timeout
    cmdLine.append('--timeout={}'.format(self.softTimeout))

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
