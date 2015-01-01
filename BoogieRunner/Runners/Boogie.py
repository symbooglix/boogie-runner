# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass, ResultType
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
  def __init__(self, boogieProgram, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))
    super(BoogieRunner, self).__init__(boogieProgram, rc)

  @property
  def name(self):
    return "boogie"

  def getResults(self):
    results = super(BoogieRunner, self).getResults()

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
        _logger.error("Boogie didn't exit properly")


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
      r = re.compile(r'Boogie program verifier finished with (\d+) verified, (?P<errors>\d+) error(s)?')

      bugsFound = None
      for line in lines:
        m = r.search(line)
        if m != None:
          numOfErrors = int(m.group('errors'))
          if numOfErrors > 0:
            bugsFound = True
          else:
            bugsFound = False

    if bugsFound == None:
      _logger.error("Could not read report from log!")
      # This is not really a bug in the Boogie program
      # but something went really wrong here
      bugsFound = True

    return bugsFound

  def run(self):
    cmdLine = [self.toolPath,
               "/proc:{}".format(self.entryPoint),
              ]
    cmdLine.extend(self.additionalArgs)
    cmdLine.append(self.program)

    # We assume that Boogie has no default timeout
    # so we force the timeout within python
    self.exitCode = None
    try:
      self.exitCode = self.runTool(cmdLine, isDotNet=True)
    except psutil.TimeoutExpired as e:
      _logger.warning('Boogie hit timeout')

def get():
  return BoogieRunner
