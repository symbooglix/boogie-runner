#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
This script takes two or more result files which
are each intended to be a run on the same benchmark
suite of the same tool and then combines the
results for each benchmark (determined by the
``combineBestResults`` function)
"""
import argparse
import logging
import math
import os
import pprint
import sys
import traceback
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile, combineResults, CombineResultsException, ComputeTimesException

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper


def main(args):
  resultTypes = [ r.name for r in list(FinalResultType)] # Get list of ResultTypes as strings

  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("-v", "--verbose", action='store_true', help='Show detailed information about mismatch')
  parser.add_argument("--stddev-abs-threshold", dest='stddev_abs_threshold',
    type=float, default=float("inf"),
    help="Emit warning about merged results with a absolute stddev greater than "
    "the specified threshold. Default %(default)s")
  parser.add_argument("--stddev-rel-threshold", dest='stddev_rel_threshold',
    type=float, default=float("inf"),
    help="Emit warning about merged results with a relative stddev greater than "
    "the specified threshold. Default %(default)s")
  parser.add_argument("-i", "--stddev-ignore-types", dest="stddev_ignore_types",
    nargs='+', default=[], help="If set when warning about stddev threshold being "
    " exceeded suppress that warning if the merged result is one of the speicifed types."
    " Default is to not to supress any types",
    choices=resultTypes)
  parser.add_argument("-o", "--output", required=True, help='Output result YAML file')
  parser.add_argument("max_time", type=float, help='max time to give benchmarks')
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if len(pargs.result_ymls) < 2:
    logger.error('Need to at least 2 YAML files')

  if os.path.exists(pargs.output):
    logging.error('Refusing to overwrite {}'.format(pargs.output))
    return 1

  if pargs.max_time <= 0.0:
    logging.error('max_time must be greater than zero')
    return 1

  # Create set of allowed result types
  resultTypesWithExceedStdDevToIgnore = set()
  for rType in pargs.stddev_ignore_types:
    resultTypesWithExceedStdDevToIgnore.add(FinalResultType[rType])

  # Check that each yml file exists
  data = { }
  resultListNames = [ ]
  for f in pargs.result_ymls:
    if not os.path.exists(f):
      logging.error('YAML file {} does not exist'.format(f))
      return 1

    # Compute result set name
    resultListName = f
    resultListNames.append(resultListName)
    if resultListName in data:
      logging.error('Can\'t use {} as label name because it is already used'.format(resultListName))
      return 1

    data[resultListName] = None # Will be filled with loaded YAML data

  # Now load YAML
  length = 0
  for f in pargs.result_ymls:
    logging.info('Loading YAML file {}'.format(f))
    with open(f, 'r') as openFile:
      results = yaml.load(openFile, Loader=Loader)
    logging.info('Loading complete')
    assert isinstance(results, list)
    resultListName = f
    data[resultListName] = results
    length = len(results)

  # Check the lengths are the same
  for name, rList in data.items():
    if len(rList) != length:
      logging.error('There is a length mismatch for {}, expected {} entries but was'.format(name, length, len(rList)))
      return 1

  programToResultSetsMap = { }
  combinedResultsList = [ ]
  for resultListName in resultListNames:
    for r in data[resultListName]:
      programName = r['program']
      try:
        existingDict = programToResultSetsMap[programName]
        existingDict[resultListName] = r
      except KeyError:
        programToResultSetsMap[programName] = { resultListName:r }

  # Check there are the same number of results for each program
  mismatchCount = 0
  thresholdExceededCount = 0
  largestStdDev = 0.0
  for programName, resultListNameToRawResultMap  in programToResultSetsMap.items():
    if len(resultListNameToRawResultMap) != len(resultListNames):
      logging.error('For program {} there we only {} result lists but expected {}'.format(
        programName, len(resultListNameToRawResultMap), len(resultListNames)))
      logging.error(pprint.pformat(resultListNameToRawResultMap))
      return 1

    # Compute the combined results
    try:
      combinedResult = combineResults(resultListNameToRawResultMap, pargs.max_time)
    except (CombineResultsException, ComputeTimesException) as e:
      logging.error('Error for program: {}'.format(programName))
      logging.error(traceback.format_exc())
      return 1
    combinedResultClassification = classifyResult(combinedResult)
    logging.debug('Combined result for {} is {}.'.format(programName,
      combinedResultClassification))
    logging.debug(pprint.pformat(combinedResult))

    if combinedResult['total_time_stddev'] > largestStdDev:
      largestStdDev = combinedResult['total_time_stddev']

    # Perform a check on the size of the standard deviation
    thresholdExceeded = False
    relStdDev = combinedResult['total_time_stddev'] / combinedResult['total_time']
    if (math.isinf(pargs.stddev_rel_threshold) and
        combinedResult['total_time_stddev'] > pargs.stddev_abs_threshold):
      # Only relative threshold specified
      thresholdExceeded = True
    elif (math.isinf(pargs.stddev_abs_threshold) and
        relStdDev > pargs.stddev_rel_threshold):
      # Only absolute threshold specified
      thresholdExceeded = True
    elif ((not (math.isinf(pargs.stddev_rel_threshold) or math.isinf(pargs.stddev_abs_threshold)))
          and combinedResult['total_time_stddev'] > pargs.stddev_abs_threshold and
          relStdDev > pargs.stddev_rel_threshold):
      # Use both relative and absolute thresholds
      thresholdExceeded = True

    if thresholdExceeded:
      if not combinedResultClassification in resultTypesWithExceedStdDevToIgnore:
        thresholdExceededCount +=1
        logging.warning('Detected combined result with a stddev over threshold')
        logging.warning('{} classified as {}'.format(programName, combinedResultClassification))
        logging.warning(pprint.pformat(combinedResult))
        logging.warning('\n')

    combinedResultsList.append(combinedResult)

  logging.info('# of results:{}'.format(len(combinedResultsList)))
  logging.info('# of stddev thresold exceeded:{} ({:.2f}%)'.format(
    thresholdExceededCount, 100*(float(thresholdExceededCount))/len(combinedResultsList)))
  logging.info('Largest reported stddev: {}'.format((largestStdDev)))
  logging.info('Writing combined results to {}'.format(pargs.output))
  with open(pargs.output, 'w') as f:
    yamlString = yaml.dump(combinedResultsList, Dumper=Dumper,
        default_flow_style=False)
    f.write(yamlString)
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
