# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
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

  @property
  def foundBug(self):
    if not os.path.exists(self.logFile):
      _logger.error('log file is missing')
      return None

    # scan for known keywords to determine if any bugs were found
    errors = 0

    errorR = re.compile(r'Execution \d+:.+ failed')
    with open(self.logFile, 'r') as f:
      for line in f:
        matchE = errorR.search(line)
        if matchE != None:
          errors += 1

    _logger.debug('Found {} errors'.format(
      errors))

    return errors > 0

  @property
  def failed(self):
    if self.exitCode != None and self.exitCode !=0:
      # Boogaloo returns a non zero exit code if parser/type check errors occurred
      return True
    else:
      return False

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
    self.exitCode = None
    try:
      self.exitCode = self.runTool(cmdLine, isDotNet=False)
    except psutil.TimeoutExpired as e:
      _logger.warning('Boogaloo hit hard timeout')

def get():
  return BoogalooRunner
