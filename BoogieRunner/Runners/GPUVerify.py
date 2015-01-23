# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. ResultType import ResultType
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

    if self.maxTimeInSeconds > 0 and (
       self.maxTimeInSeconds <= self.softTimeoutDiff):
      raise GPUVerifyRunnerException('Need larger timeout')

    if not self.toolPath.endswith('.py'):
      raise GPUVerifyRunnerException(
        'toolPath needs to be the GPUVerify python script')

  @property
  def name(self):
    return "gpuverify"

  @property
  def timeoutWasHit(self):
    if self.hitHardTimeout:
      return True
    else:
      if self.exitCode == 7:
        return True
      else:
        return False

  def getResults(self):
    results = super(GPUVerifyRunner, self).getResults()
    results['hit_hard_timeout'] = self.hitHardTimeout
    return results

  def GetNewAnalyser(self):
    return GPUVerifyAnalyser(self.exitCode, self.logFile, self.hitHardTimeout)

  def run(self):
    self.hitHardTimeout = False

    # Run using python interpreter
    cmdLine = [ sys.executable, self.toolPath ]

    # Set a soft timeout
    softTimeout = self.maxTimeInSeconds - self.softTimeoutDiff
    cmdLine.append('--timeout={}'.format(softTimeout))


    # Note we ignore self.entryPoint

    # GPUVerify needs PATH environment variable set
    env = {}
    path = os.getenv('PATH')
    if path == None:
      path = ""

    env['PATH'] = path

    # THIS IS A HACK
    # GPUVerify needs the local/group size to be passed
    # We're passing an already processed bpl file
    # so that information is already part of the Boogie
    # program
    # rather than trying to work out what was passed
    # just pass arbitary global and local size and hope
    # this doesn't break anything
    cmdLine.append('--local_size=2')
    cmdLine.append('--num_groups=2')

    cmdLine.extend(self.additionalArgs)

    # Add the boogie source file as last arg
    cmdLine.append(self.programPathArgument)

    try:
      exitCode = self.runTool(cmdLine,
        isDotNet=False,
        envExtra=env)
      assert self.exitCode == exitCode
    except psutil.TimeoutExpired as e:
      self.hitHardTimeout = True
      _logger.warning('GPUVerify hit hard timeout')

def get():
  return GPUVerifyRunner
