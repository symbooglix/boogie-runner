# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import functools
import logging
import os
import re
import yaml

_logger = logging.getLogger(__name__)

class SymbooglixAnalyser(AnalyserBaseClass):
  def __init__(self, resultDict):
    super(SymbooglixAnalyser, self).__init__(resultDict)
    assert 'backend_timeout' in self._resultDict
    assert 'sbx_dir' in self._resultDict
    # FIXME: Remove this!
    assert '__soft_timeout' in self._resultDict
    assert 'total_time' in self._resultDict

  @property
  def foundBug(self):
    if self.hitHardTimeout:
      # FIXME: We need to examine the output to see what happened
      _logger.error('FIXME: Need to examine symbooglix\'s working dir')
      return None

    # Use Symbooglix exitCode:
    if self.exitCode == 2 or self.exitCode == 4:
      return True
    elif self.exitCode == 0 or self.exitCode == 3 or self.exitCode == 9 or self.exitCode == 10:
      # NO_ERRORS_NO_TIMEOUT_BUT_FOUND_SPECULATIVE_PATHS : 9
      # NO_ERRORS_NO_TIMEOUT_BUT_HIT_BOUND : 10
      return False
    else:
      return None

  @property
  def failed(self):
    if self.ranOutOfMemory:
      return True

    if self.ranOutOfTime:
      return False # Timeout is not a failure

    # NO_ERRORS_NO_TIMEOUT_BUT_FOUND_SPECULATIVE_PATHS : 9
    # NO_ERRORS_NO_TIMEOUT_BUT_HIT_BOUND : 10
    if self.exitCode ==9:
      # We don't want to hit speculative paths
      return True
    if self.exitCode == 10:
      return False

    # All exit codes above 4 indicate something went badly wrong
    return self.exitCode > 4 or self.exitCode == 1

  # Override normal implementation
  @property
  def ranOutOfTime(self):
    if self.hitHardTimeout:
      return True

    if self.exitCode == 3 or self.exitCode == 4:
      # NO_ERRORS_TIMEOUT,
      # ERRORS_TIMEOUT,
      return True

    # FIXME: This hack will waste space in the results. We should
    # find a better way to check this
    # Check if the soft timeout was hit
    if self._resultDict['total_time'] > self.softTimeout:
      return True

    return False

  @property
  def hitBound(self):
    return self.exitCode == 10

  @property
  def foundSpeculativePathsAndNoBug(self):
    return self.exitCode == 9

  @property
  def hitHardTimeout(self):
    return self._resultDict['backend_timeout']

  # FIXME: Remove this!
  @property
  def softTimeout(self):
    return self._resultDict['__soft_timeout']

  def getAnalysesDict(self):
    results = super(SymbooglixAnalyser, self).getAnalysesDict()
    results['bound_hit'] = self.hitBound
    results['speculative_paths_nb'] = self.foundSpeculativePathsAndNoBug
    results['instructions_executed'] = self.instructionsExecuted
    return results

  def _getSbxWorkDir(self):
    sbxDir = self._resultDict['sbx_dir']
    if not os.path.exists(sbxDir):
      _logger.error('{} does not exist'.format(sbxDir))
      return None
    return sbxDir

  @property
  def instructionsExecuted(self):
    executorInfo = self.getExecutorInfo()
    if executorInfo == None:
      return None

    try:
      return executorInfo['instructions_executed']
    except KeyError as e:
      _logger.error(str(e))
      return None

  @functools.lru_cache(maxsize=1)
  def getExecutorInfo(self):
    sbxDir = self._getSbxWorkDir()
    if sbxDir == None:
      return None

    executorYamlPath = os.path.join(sbxDir, 'executor_info.yml')
    if not os.path.exists(executorYamlPath):
      _logger.error('{} does not exist'.format(executorYamlPath))
      return None

    data = None
    try:
      with open(executorYamlPath, 'r') as f:
        data = yaml.load(f)
        return data
    except Exception as e:
      _logger.error(str(e))
      return None

def get():
  return SymbooglixAnalyser
