# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. Analysers.Boogaloo import BoogalooAnalyser
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
    return "boogaloo"

  def GetNewAnalyser(self):
    return BoogalooAnalyser(self.exitCode, self.logFile)

  def run(self):
    cmdLine = [ ]

    cmdLine.append(self.toolPath)

    # Put boogaloo into execute or test mode
    cmdLine.append(self.boogalooMode)

    if self.boogalooMode != 'exec':
      _logger.warning('Cannot detect if bound is hit if not using "exec" mode')

    cmdLine.extend(self.additionalArgs)
    if self.entryPoint == None:
      raise BoogalooRunnerException('entry point not specified')

    cmdLine.append('--proc={}'.format(self.entryPoint))

    # Add the boogie source file as last arg
    cmdLine.append(self.programPathArgument)

    # We assume that Boogaloo has no default timeout
    # so we force the timeout within the backend
    backendResult = self.runTool(cmdLine, isDotNet=False)
    if backendResult.outOfTime:
      _logger.warning('Boogaloo hit hard timeout')

def get():
  return BoogalooRunner
