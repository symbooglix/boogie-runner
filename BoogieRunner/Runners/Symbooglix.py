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

    self.sbxDirName = "sbx"

  @property
  def name(self):
    return "symbooglix"

  def GetNewAnalyser(self, resultDict):
    return SymbooglixAnalyser(resultDict)

  def _buildResultDict(self):
    results = super(SymbooglixRunner, self)._buildResultDict()
    results['sbx_dir'] = self.outputDirOnHost
    # TODO: Remove this. It's redundant
    results['hit_hard_timeout'] = results['backend_timeout']
    # FIXME: This is wasteful
    results['__soft_timeout'] = self.softTimeout
    return results

  def run(self):
    # Build the command line
    cmdLine = [ self.toolPath ] + self.additionalArgs

    # symbooglix outputdir
    self.outputDirInBackend = os.path.join(self.workingDirectoryInBackend, self.sbxDirName)
    self.outputDirOnHost = os.path.join(self.workingDirectory, self.sbxDirName)
    cmdLine.append('--output-dir={}'.format(self.outputDirInBackend))

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
    backendResult = self.runTool(cmdLine, isDotNet=True)
    if backendResult.outOfTime:
      self.hitHardTimeout = True
      _logger.warning('Hard timeout hit')

def get():
  return SymbooglixRunner
