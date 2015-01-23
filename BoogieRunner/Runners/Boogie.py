# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. ResultType import ResultType
from .. Analysers.Boogie import BoogieAnalyser
import logging
import os
import psutil
import re
import yaml

_logger = logging.getLogger(__name__)

class BoogieRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class BoogieRunner(RunnerBaseClass):
  def __init__(self, boogieProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(BoogieRunner, self).__init__(boogieProgram, workingDirectory, rc)

  @property
  def name(self):
    return "boogie"

  def GetNewAnalyser(self):
    return BoogieAnalyser(self.exitCode, self.logFile, self.useDocker)

  def run(self):
    cmdLine = [self.toolPath,
               "/proc:{}".format(self.entryPoint),
              ]
    cmdLine.extend(self.additionalArgs)
    cmdLine.append(self.programPathArgument)

    # We assume that Boogie has no default timeout
    # so we force the timeout within python
    try:
      exitCode = self.runTool(cmdLine, isDotNet=True)
      assert exitCode == self.exitCode
    except psutil.TimeoutExpired as e:
      _logger.warning('Boogie hit timeout')

def get():
  return BoogieRunner
