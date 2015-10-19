# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. Analysers.GPUVerify import GPUVerifyAnalyser
import logging
import os
import psutil
import re
import sys
import yaml

_logger = logging.getLogger(__name__)

class GPUVerifyRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class GPUVerifyRunner(RunnerBaseClass):
  softTimeoutDiff = 5

  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(GPUVerifyRunner, self).__init__(boogieProgram, workingDirectory, rc)

    # Sanity checks
    # TODO

    self.softTimeout = self.maxTimeInSeconds
    if self.maxTimeInSeconds > 0:
      # We use GPUVerify's timeout function and enforce the
      # requested timeout and enforce a hard timeout slightly later
      self.maxTimeInSeconds = self.maxTimeInSeconds + self.softTimeoutDiff

    if not self.toolPath.endswith('.py'):
      raise GPUVerifyRunnerException(
        'toolPath needs to be the GPUVerify python script')

  @property
  def name(self):
    return "gpuverify"

  def _buildResultDict(self):
    results = super(GPUVerifyRunner, self)._buildResultDict()
    # TODO: Remove this. It's now redundant
    results['hit_hard_timeout'] = results['backend_timeout']
    return results

  def GetNewAnalyser(self, resultDict):
    return GPUVerifyAnalyser(resultDict)

  def run(self):
    # Run using python interpreter
    cmdLine = [ sys.executable, self.toolPath ]

    cmdLine.append('--timeout={}'.format(self.softTimeout))

    # Note we ignore self.entryPoint
    _logger.info('Ignoring entry point {}'.format(self.entryPoint))

    # GPUVerify needs PATH environment variable set
    env = {}
    path = os.getenv('PATH')
    if path == None:
      path = ""

    env['PATH'] = path

    cmdLine.extend(self.additionalArgs)

    # Add the boogie source file as last arg
    cmdLine.append(self.programPathArgument)

    backendResult = self.runTool(cmdLine,
      isDotNet=False,
      envExtra=env)
    if backendResult.outOfTime:
      _logger.warning('GPUVerify hit hard timeout')

def get():
  return GPUVerifyRunner
