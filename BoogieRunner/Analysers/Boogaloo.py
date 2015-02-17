# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import logging
import os
import re

_logger = logging.getLogger(__name__)

class BoogalooAnalyser(AnalyserBaseClass):
  def __init__(self, exitCode, logFile, useDocker, **kargs):
    super(BoogalooAnalyser, self).__init__(exitCode, logFile, useDocker, **kargs)

  @property
  def foundBug(self):
    if not os.path.exists(self.logFile):
      _logger.error('log file is missing')
      return None

    # scan for known keywords to determine if any bugs were found
    errors = 0

    errorR = re.compile(r'Execution \d+:.+ failed', flags= re.MULTILINE | re.DOTALL)
    _logger.debug('Opening {}'.format(self.logFile))
    with open(self.logFile, 'r') as f:
      # Unfortunately boogaloo errors might spread over multiple lines
      # so we need to read the whole log into memory and then do a search
      #
      # We presume each line has the line seperator on the end already
      # so we can use an empty string as the seperator.
      lines = ''.join(f.readlines())
      matchE = errorR.match(lines)
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

def get():
  return BoogalooAnalyser
