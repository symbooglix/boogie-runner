# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass, ResultType
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
  def __init__(self, boogieProgram, config):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(CorralRunner, self).__init__(boogieProgram, config)

  @property
  def name(self):
    return "corral"

  def getResults(self):
    results = super(CorralRunner, self).getResults()

    # Interpret exit code and contents of the log file
    resultType = ResultType.UNKNOWN
    timedOut = self.exitCode == None
    if timedOut:
      if self.foundBug():
        resultType = ResultType.BUGS_TIMEOUT
      else:
        resultType = ResultType.NO_BUGS_TIMEOUT
    else:
      if self.exitCode == 0:
        if self.foundBug():
          resultType = ResultType.BUGS_NO_TIMEOUT
        else:
          resultType = ResultType.NO_BUGS_NO_TIMEOUT
      else:
        _logger.error("Corral didn't exit properly")


    results['result'] = resultType
    return results

  def foundBug(self):
    """
    Opens log output and checks if a bug was found
    """
    if not os.path.exists(self.logFile):
      _logger.error('Could not find log file')
      # This isn't a bug but the fact that the log output
      # is missing is an issue which needs attention
      return True

    with open(self.logFile, 'r') as f:
      lines = [l.rstrip() for l in f.readlines()]

      # This is kind of a hack to detect if a bug was found
      # by Corral. Corral needs something better
      r = re.compile(r'Program has a potential bug: True bug')

      for line in lines:
        m = r.search(line)
        if m != None:
          return True

    return False

  def run(self):
    # We assume that Corral has no default timeout.
    # Looking at Corral's code "/timeLimit:" seems to
    # zero by default despite what the usage message says
    cmdLine = [self.toolPath,
               self.program,
               "/main:{}".format(self.entryPoint)
              ]

    cmdLine.extend(self.additionalArgs)

    self.exitCode = None
    try:
      self.exitCode = self.runTool(cmdLine, isDotNet=True)
    except psutil.TimeoutExpired as e:
      _logger.warning('Corral hit timeout')

def get():
  return CorralRunner
