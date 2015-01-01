# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass, ResultType
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

  def __init__(self, boogieProgram, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(GPUVerifyRunner, self).__init__(boogieProgram, rc)

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

  def getResults(self):
    results = super(GPUVerifyRunner, self).getResults()

    # Interpret exit code
    resultType = ResultType.UNKNOWN
    timedOut = self.exitCode == None
    if timedOut:
        # GPUVerify won't of reported anything
        # if it hard timed out
        resultType = ResultType.NO_BUGS_TIMEOUT
    else:
      # GPUVerify exit codes are taken from
      # GPUVerifyScript/error_codes.py
      #
      #   SUCCESS = 0
      #   ...
      #   GPUVERIFYVCGEN_ERROR = 5
      #   BOOGIE_ERROR = 6
      #   TIMEOUT = 7

      if self.exitCode == 0:
        resultType = ResultType.NO_BUGS_NO_TIMEOUT
      elif self.exitCode == 7:
        # Soft timeout. GPUVerify won't of reported anything
        resultType = ResultType.NO_BUGS_NO_TIMEOUT
      elif self.exitCode == 6:
        resultType = ResultType.BUGS_NO_TIMEOUT
      else:
        _logger.error("GPUVerify had unrecognised exit code")

      results['exitCode'] = self.exitCode


    results['result'] = resultType
    return results

  def run(self):
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
    cmdLine.append(self.program)

    # We assume that Boogie has no default timeout
    # so we force the timeout within python
    self.exitCode = None
    try:
      self.exitCode = self.runTool(cmdLine,
        isDotNet=False,
        envExtra=env)
    except psutil.TimeoutExpired as e:
      _logger.warning('GPUVerify hit hard timeout')

def get():
  return GPUVerifyRunner
