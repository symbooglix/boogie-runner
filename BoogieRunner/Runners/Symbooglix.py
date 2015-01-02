# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. ResultType import ResultType
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
  def __init__(self, boogieProgram, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(SymbooglixRunner, self).__init__(boogieProgram, rc)

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

  def getResults(self):
    results = super(SymbooglixRunner, self).getResults()
    results['sbx_dir'] = self.outputDir

    # Interpret the ResultType to set
    resultType = ResultType.UNKNOWN

    if not self.hitHardTimeout:

      # Use Symbooglix exitCode
      if self.exitCode == 0:
        resultType = ResultType.NO_BUGS_NO_TIMEOUT
      elif self.exitCode == 1:
        resultType = ResultType.BUGS_NO_TIMEOUT
      elif self.exitCode == 2:
        resultType = ResultType.NO_BUGS_TIMEOUT
      elif self.exitCode == 3:
        resultType = ResultType.BUGS_TIMEOUT

    else:
      # hit hard timeout.
      # FIXME: Read symbooglix YAML file to determine
      # outcome
      _logger.error('FIXME: hard timeout was hit')


    results['result'] = resultType
    results['hit_hard_timeout'] = self.hitHardTimeout
    return results

  def run(self):

    # Build the command line
    cmdLine = [ self.toolPath ] + self.additionalArgs

    # symbooglix outputdir
    self.outputDir = os.path.join(self.workingDirectory, "symboolix-0")
    cmdLine.append('--output-dir={}'.format(self.outputDir))

    # Set implementation to enter
    cmdLine.append('--entry-points={}'.format(self.entryPoint))

    # Compute soft timeout and add as command line param
    softTimeout = self.maxTimeInSeconds - self.softTimeoutDiff
    assert softTimeout > 0
    cmdLine.append('--timeout={}'.format(softTimeout))

    # Add the source file as the last arg
    cmdLine.append(self.programPathArgument)

    self.exitCode = None
    self.hitHardTimeout = False
    try:
      self.exitCode = self.runTool(cmdLine, isDotNet=True)
    except psutil.TimeoutExpired as e:
      self.hitHardTimeout = True
      _logger.warning('Hard timeout hit')

def get():
  return SymbooglixRunner
