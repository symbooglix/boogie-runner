# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. Analysers.Boogaloo import BoogalooAnalyser
from .. ResultType import ResultType
import logging
import os
import psutil
import re
import yaml

_logger = logging.getLogger(__name__)

class BoogalooRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class BoogalooRunner(RunnerBaseClass):

  staticCounter = 0
  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))

    super(BoogalooRunner, self).__init__(boogieProgram, workingDirectory, rc)

    # Sanity checks
    # TODO

    try:
      self.boogalooMode = rc['mode']
    except KeyError:
      raise BoogalooRunnerException('"mode" key missing from config')

    if self.boogalooMode != 'test' and self.boogalooMode != 'exec':
      raise BoogalooRunnerException('"mode" key\'s value must be "test" or "exec"')


  @property
  def name(self):
    return "boogaloo" + ('-docker' if self.useDocker else '')

  def GetNewAnalyser(self):
    return BoogalooAnalyser(self.exitCode, self.logFile, self.useDocker)

  def run(self):
    cmdLine = [ ]

    cmdLine.append(self.toolPath)

    # Use Boogaloo in execute mode
    cmdLine.append(self.boogalooMode)

    cmdLine.extend(self.additionalArgs)
    cmdLine.append('--proc={}'.format(self.entryPoint))

    # Add the boogie source file as last arg
    cmdLine.append(self.programPathArgument)

    # We assume that Boogie has no default timeout
    # so we force the timeout within python
    try:
      exitCode = self.runTool(cmdLine, isDotNet=False)
      assert self.exitCode == exitCode
    except psutil.TimeoutExpired as e:
      _logger.warning('Boogaloo hit hard timeout')

def get():
  return BoogalooRunner
