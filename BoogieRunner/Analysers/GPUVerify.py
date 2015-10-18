# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . AnalyserBase import AnalyserBaseClass
import logging
import os
import re

_logger = logging.getLogger(__name__)

class GPUVerifyAnalyser(AnalyserBaseClass):
  def __init__(self, resultDict):
    super(GPUVerifyAnalyser, self).__init__(resultDict)
    assert 'hit_hard_timeout' in self._resultDict

  @property
  def foundBug(self):
    if self.hitHardTimeout:
      return False

      # GPUVerify exit codes are taken from
      # GPUVerifyScript/error_codes.py
      # SUCCESS = 0
      # COMMAND_LINE_ERROR = 1
      # CLANG_ERROR = 2
      # OPT_ERROR = 3
      # BUGLE_ERROR = 4
      # GPUVERIFYVCGEN_ERROR = 5
      # NOT_ALL_VERIFIED = 6
      # TIMEOUT = 7
      # CTRL_C = 8
      # CONFIGURATION_ERROR = 9
      # JSON_ERROR = 10
      # BOOGIE_INTERNAL_ERROR = 11 # Internal failure of Boogie Driver or Cruncher
      # BOOGIE_OTHER_ERROR = 12 # Uncategorised failure of Boogie Driver or Cruncher
    if self.exitCode == 0 or self.exitCode == 7:
      return False
    elif self.exitCode == 6:
      return True # bug report should been emitted.
    else:
      return None

  @property
  def failed(self):
    if self.hitHardTimeout:
      return False

    if self.exitCode == 0 or self.exitCode == 6 or self.exitCode == 7:
      return False

    return True

  @property
  def hitHardTimeout(self):
    return self._resultDict['hit_hard_timeout']

def get():
  return GPUVerifyAnalyser
