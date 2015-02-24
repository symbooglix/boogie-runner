# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
Utility functions for analysis tools
"""
from enum import Enum, unique

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
  fileName = r['program']
  if r['bug_found'] == False and r['timeout_hit'] == False and r['failed'] == False:
    # might be fully explored
    if 'recursion_bound_hit' in r and r['recursion_bound_hit'] == True:
      # Legacy: Corral run hit recursion bound
      return FinalResultType.BOUND_HIT
    elif 'bound_hit' in r and r['bound_hit'] == True:
      # Tool (e.g. boogaloo) hit bound
      return FinalResultType.BOUND_HIT
    else:
      return FinalResultType.FULLY_EXPLORED
  elif r['bug_found'] == True:
    assert r['failed'] != True
    assert r['timeout_hit'] != True
    return FinalResultType.BUG_FOUND
  elif r['timeout_hit'] == True and (r['failed'] == False or r['failed'] == None):
    assert r['failed'] != None
    return FinalResultType.TIMED_OUT
  else:
    assert r['failed'] == True
    return FinalResultType.UNKNOWN

# Correct less label mapping stuff

class ValidateMappingFileException(Exception):
  pass

def validateMappingFile(mapping):
  if not isinstance(mapping, dict):
    raise ValidateMappingFileException("Top level datastructure must be"
      " dictionary")

  for key, value in mapping.items():
    if not isinstance(key, str):
      raise ValidateMappingFileException("Top level keys must be strings")

    if not isinstance(value, dict):
      raise ValidateMappingFileException("Top level key must map to dictionary")

    if not 'expected_correct' in value:
      raise ValidateMappingFileException("{}'s dict is missing"
      "'expected_correct' key".format(key))

    if not isinstance(value['expected_correct'], bool) and \
    value['expected_correct'] != None:
      raise ValidateMappingFileException("{}'s dict does not map"
        "'expected_correct' map to bool".format(key))

