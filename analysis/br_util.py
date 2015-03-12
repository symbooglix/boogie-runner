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
  OUT_OF_MEMORY = 4
  UNKNOWN = 5


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
  elif r['out_of_memory'] == True:
    # FIXME: When out_of_memory occurs failed might be set to true which is
    # confusing
    assert r['failed'] != None
    return FinalResultType.OUT_OF_MEMORY
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
        "'expected_correct' map to bool or None".format(key))

class MergeCorrectnessLabelException(Exception):
  pass

def mergeCorrectnessLabel(resultList, correctnessMapping):
  assert isinstance(resultList, list)
  assert isinstance(correctnessMapping, dict)

  for r in resultList:
    assert isinstance(r, dict)
    assert 'program' in r
    correctnessLabel = None
    programName = r['program']
    try:
      correctnessLabel = correctnessMapping[programName]['expected_correct']
      r['expected_correct'] = correctnessLabel
    except KeyError:
      raise MergeCorrectnessLabelException('"expected_correct" missing from result with program name "{}"'.format(programName))

  return resultList

class PickBestResultException(Exception):
  pass

def _returnFastest(results, resultListNamesToConsider):
  assert isinstance(results, dict)
  assert isinstance(resultListNamesToConsider, set)
  resultsToConsider = {k:v for k,v in results.items() if k in resultListNamesToConsider}
  assert len(resultsToConsider) > 0
  bestResultPair = min(resultsToConsider.items(), key=lambda pair: pair[1]['total_time'])
  return bestResultPair[0]

def pickBestResult(results):
  """
    results: Should be a dictionary mapping the result list name to
    the raw result for a particular boogie program.

    Returns: the result list name (the key for the ``results`` dictionary)
    that is considered the best if it exists.

    It throws an exception if there is a bad result mismatch or a best result
    could not be found
  """
  assert isinstance(results, dict)
  assert len(results) > 1
  # Get the FinalResultType for each result
  resultTypeToResultListName = { }
  for rType in FinalResultType:
    resultTypeToResultListName[rType] = set()

  for resultListName, rawResult in results.items():
    resultType = classifyResult(rawResult)
    resultTypeToResultListName[resultType].add(resultListName)

  #        FULLY_EXPLORED     BUG_FOUND
  #                    \       /
  #                    BOUND_HIT
  #                        |
  #                    TIMED_OUT
  #                        |
  #                  OUT_OF_MEMORY
  #                        |
  #                     UNKNOWN
  # Traverse our partial order starting from the best and picking
  # the first thing we find.
  # If there is more than one result of a resultType (e.g. two results
  # that are marked as fully explored) we pick the result with the shortest
  # execution time.
  #
  # It is a partial order because FULLY_EXPLORED and BUG_FOUND cannot be ordered
  #
  # FIXME: I'm not sure if TIMED_OUT and OUT_OF_MEMORY should be ordered in the
  # way they are here.
  
  if len(resultTypeToResultListName[FinalResultType.FULLY_EXPLORED]) > 0 and \
      len(resultTypeToResultListName[FinalResultType.BUG_FOUND]) > 0:
    raise PickBestResultException("Conflicting results FULLY_EXPLORED and BUG_FOUND")

  fullyExploredListNames = resultTypeToResultListName[FinalResultType.FULLY_EXPLORED]
  if len(fullyExploredListNames) > 0:
    return _returnFastest(results, fullyExploredListNames)

  bugFoundListNames = resultTypeToResultListName[FinalResultType.BUG_FOUND]
  if len(bugFoundListNames) > 0:
    return _returnFastest(results, bugFoundListNames)

  boundHitListNames = resultTypeToResultListName[FinalResultType.BOUND_HIT]
  if len(boundHitListNames) > 0:
    return _returnFastest(results, boundHitListNames)

  timeoutListNames = resultTypeToResultListName[FinalResultType.TIMED_OUT]
  if len(timeoutListNames) > 0:
    return _returnFastest(results, timeoutListNames)

  outOfMemoryListNames = resultTypeToResultListName[FinalResultType.OUT_OF_MEMORY]
  if len(outOfMemoryListNames) > 0:
    return _returnFastest(results, outOfMemoryListNames)

  unknownListNames = resultTypeToResultListName[FinalResultType.UNKNOWN]
  if len(unknownListNames) > 0:
    return _returnFastest(results, unknownListNames)

  raise PickBestResultException("Couldn't pick a best result")
