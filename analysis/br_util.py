# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
Utility functions for analysis tools
"""
import logging
from enum import Enum, unique
import pprint

_logger = logging.getLogger(__name__)

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
    if r['failed'] == True:
      _logger.error(pprint.pformat(r))
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

class CombineResultsException(Exception):
  pass

class ComputeTimesException(Exception):
  pass

def _computeTimes(resultList, maxTime, resultTypesToGiveMaxTime):
  """
    resultList: list of raw results
    maxTime: the maximumTime to give result that are of a type in resultTypesToGiveMaxTime
    resultTypesToGiveMaxTime: a set of FinalResultTypes to treat as having executed for
    ``maxTime``. It is also the maximum time allowed for any result.

    returns a tuple (meanTime, stdDev)

    where meanTime is the arithmetic mean and stdDev is the estimation of the population
    standard deviation (Bessel corrected).
  """
  assert isinstance(resultList, list)
  assert isinstance(maxTime, float)
  assert isinstance(resultTypesToGiveMaxTime, set)
  assert maxTime > 0.0
  times = []
  for r in resultList:
    totalTime = r['total_time']
    resultType = classifyResult(r)
    if resultType in resultTypesToGiveMaxTime:
      totalTime = maxTime
    elif totalTime > maxTime:
      _logger.warning('Clamping time on result:\n{}'.format(pprint.pformat(r)))
      totalTime = maxTime
    assert totalTime > 0.0
    times.append(totalTime)

  assert len(resultList) == len(times)
  import statistics
  arithmeticMean = statistics.mean(times)
  if len(times) > 1:
    # Unbiased estimate of the population standard deviation
    # (i.e. Use's Bessel's correction)
    stdDev = statistics.stdev(times)
  else:
    # Not defined if we only have one measurement
    raise ComputeTimesException("Can't compute stddev from a single result")

  return (arithmeticMean, stdDev)

def combineResults(results, maxTime):
  """
    results: Should be a dictionary mapping the result list name to
    the raw result for a particular boogie program.

    maxTime: float. The time to use for results of type ``resultTypesToGiveMaxTime``.
             All times are also clamped to this value.

    Returns: cResult which is the combined result where the execution time is
    the arithmetic mean of the execution times of the results and a
    'total_time_stddev' field is added which is the standard deviation of the
    times (may be zero).

    It throws an exception if there is a bad result mismatch or a best result
    could not be found
  """
  assert isinstance(results, dict)
  assert len(results) > 1
  # Get the FinalResultType for each result
  resultTypeToListOfResults = { }
  for rType in FinalResultType:
    resultTypeToListOfResults[rType] = [ ]

  for resultListName, rawResult in results.items():
    resultType = classifyResult(rawResult)
    resultTypeToListOfResults[resultType].append(rawResult)

  #        FULLY_EXPLORED     BUG_FOUND (conflict)
  #                    \       /
  #                    BOUND_HIT
  #                    /   |   \
  #                   /    |    \
  #                  /     |     \
  #      OUT_OF_MEMORY TIMED_OUT UNKNOWN  (no conflict, take most common)
  #
  # Traverse the above partial order starting from the top.
  # We try to pick a best result type (i.e. FULLY_EXPLORED, BUG_FOUND or BOUND_HIT) if it exists
  # otherwise we pick the most common. This is giving a tool the "benefit of the doubt".
  #
  # For handling total_time all results are used to compute an arithmetic mean
  # standard deviation but for results of a type OUT_OF_MEMORY, TIMED_OUT or
  # UNKNOWN, their times are adjusted so that their times are maxTime.
  #
  # It is a partial order because FULLY_EXPLORED and BUG_FOUND cannot be ordered
  # and neither can OUT_OF_MEMORY, TIMED_OUT or UNKNOWN
  #
  # It is important this is a list because the order is important
  bestTypesOrdered = [FinalResultType.FULLY_EXPLORED,
                      FinalResultType.BUG_FOUND,
                      FinalResultType.BOUND_HIT]
  noBestTypes = set(FinalResultType).difference(set(bestTypesOrdered))
  copiedResult = None

  if len(resultTypeToListOfResults[FinalResultType.FULLY_EXPLORED]) > 0 and \
      len(resultTypeToListOfResults[FinalResultType.BUG_FOUND]) > 0:
    raise CombineResultsException("Conflicting results FULLY_EXPLORED and BUG_FOUND")

  # Try to pick the best
  for rType in bestTypesOrdered:
    if len(resultTypeToListOfResults[rType]) > 0:
      resultToCopy = resultTypeToListOfResults[rType][0]
      assert isinstance(resultToCopy, dict)
      copiedResult = resultToCopy.copy()
      break

  if copiedResult == None:
    # We couldn't pick a best so pick the most common out of the remaing
    # result types. If there is a tie the choice is arbitary
    assert all(map(lambda rType: len(resultTypeToListOfResults[rType]) == 0, bestTypesOrdered))
    largestList = [ ]
    for rType in noBestTypes:
      if len(resultTypeToListOfResults[rType]) > len(largestList):
        largestList = resultTypeToListOfResults[rType]

    assert len(largestList) > 0
    resultToCopy = largestList[0]
    assert isinstance(resultToCopy, dict)
    copiedResult = resultToCopy.copy()

  # Compute the total_time and stddev.
  listOfAllResults = []
  sortedResultItems = list(results.items())
  sortedResultItems.sort(key= lambda k: k[0]) # Make sure the order is deterministic by sorting by the result list filename
  for resultListName,r in sortedResultItems:
    assert isinstance(resultListName, str)
    assert isinstance(r, dict)
    listOfAllResults.append(r)
  assert isinstance(listOfAllResults, list)
  assert len(listOfAllResults) > 0
  meanTime, stdDev = _computeTimes(listOfAllResults, maxTime, noBestTypes)
  assert isinstance(meanTime, float)
  assert isinstance(stdDev, float)
  copiedResult['total_time'] = meanTime
  copiedResult['total_time_stddev'] = stdDev
  copiedResult['original_results'] = listOfAllResults

  return copiedResult

