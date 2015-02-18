# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. Analysers.Corral import CorralAnalyser
import logging
import os
import psutil
import re
import yaml

_logger = logging.getLogger(__name__)

class CorralRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class CorralRunner(RunnerBaseClass):
  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(CorralRunner, self).__init__(boogieProgram, workingDirectory, rc)

  @property
  def name(self):
    return "corral"

  def GetNewAnalyser(self):
    return CorralAnalyser(self.exitCode, self.logFile, self.useDocker)

  def run(self):
    # We assume that Corral has no default timeout.
    # Looking at Corral's code "/timeLimit:" seems to be
    # zero by default despite what the usage message says
    cmdLine = [self.toolPath,
               self.programPathArgument,
               "/main:{}".format(self.entryPoint)
              ]

    cmdLine.extend(self.additionalArgs)

    try:
      exitCode = self.runTool(cmdLine, isDotNet=True)
      assert self.exitCode == exitCode
    except psutil.TimeoutExpired as e:
      _logger.warning('Corral hit timeout')

def get():
  return CorralRunner
