# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
Utility functions for analysis tools
"""
from enum import Enum, unique
import os
import logging

@unique
class FinalResultType(Enum):
  FULLY_EXPLORED = 0
  BOUND_HIT = 1
  BUG_FOUND = 2
  TIMED_OUT = 3
  UNKNOWN = 4


def classifyResult(r):
  """
  Classify result returning a FinalResultType enum
  """
  assert isinstance(r, dict)
  fileName = os.path.basename(r['program'])
  if r['bug_found'] == False and r['timeout_hit'] == False and r['failed'] == False:
    # might be fully explored
    if 'recursion_bound_hit' in r and r['recursion_bound_hit'] == True:
      # Corral run hit recursion bound
      logging.debug('Classified {} as hit bound'.format(fileName))
      return FinalResultType.BOUND_HIT
    else:
      logging.debug('Classified {} as fully explored'.format(fileName))
      return FinalResultType.FULLY_EXPLORED
  elif r['bug_found'] == True:
    assert r['failed'] != True
    assert r['timeout_hit'] != True
    logging.debug('Classified {} as bug found'.format(fileName))
    return FinalResultType.BUG_FOUND
  elif r['timeout_hit'] == True and (r['failed'] == False or r['failed'] == None):
    assert r['failed'] != None
    logging.debug('Classified {} as timeout'.format(fileName))
    return FinalResultType.TIMED_OUT
  else:
    assert r['failed'] == True
    logging.debug('Classified {} as unknown'.format(fileName))
    return FinalResultType.UNKNOWN
