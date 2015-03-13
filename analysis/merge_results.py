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
import os
import pprint
import sys
import traceback
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile, combineBestResults, CombineBestResultsException

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper


def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("-v", "--verbose", action='store_true', help='Show detailed information about mismatch')
  parser.add_argument("--stddev-threshold", dest='stddev_threshold',
    type=float, default=float("inf"),
    help="Emit warning about merged results with a total_time standard deviation of greater than "
    "the specified threshold")
  parser.add_argument("-i", "--stddev-ignore-timeouts", dest="stddev_ignore_timeouts",
    action='store_true', default=False, help="If set when warning about stddev threshold being "
    " exceeded suppress that warning if the merged result is a timeout")
  parser.add_argument("-o", "--output", required=True, help='Output result YAML file')
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if len(pargs.result_ymls) < 2:
    logger.error('Need to at least 2 YAML files')

  if os.path.exists(pargs.output):
    logging.error('Refusing to overwrite {}'.format(pargs.output))
    return 1

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
  for programName, resultListNameToRawResultMap  in programToResultSetsMap.items():
    if len(resultListNameToRawResultMap) != len(resultListNames):
      logging.error('For program {} there we only {} result lists but expected {}'.format(
        programName, len(resultListNameToRawResultMap), len(resultListNames)))
      logging.error(pprint.pformat(resultListNameToRawResultMap))
      return 1

    # Compute the combined results
    try:
      resultListsUsed, combinedResult = combineBestResults(resultListNameToRawResultMap)
    except CombineBestResultsException as e:
      logging.error('Error for program: {}'.format(programName))
      logging.error(traceback.format_exc())
      return 1
    combinedResultClassification = classifyResult(combinedResult)
    logging.debug('Combined result for {} is {}. Used {}'.format(programName,
      combinedResultClassification,
      pprint.pformat(resultListsUsed)))
    logging.debug(pprint.pformat(combinedResult))

    # Perform a check on the size of the standard deviation
    if combinedResult['total_time_stddev'] == None:
      logging.warning('stddev was None which means only result could be used')
      logging.warning('{} classified as {}'.format(programName, combinedResultClassification))
      logging.warning(pprint.pformat(combinedResult))
      logging.warning('')
    elif combinedResult['total_time_stddev'] > pargs.stddev_threshold:
      if not (pargs.stddev_ignore_timeouts and
      combinedResultClassification == FinalResultType.TIMED_OUT):
        logging.warning('Detected combined result with a stddev over threshold')
        logging.warning('{} classified as {}'.format(programName, combinedResultClassification))
        logging.warning(pprint.pformat(combinedResult))
        logging.warning('')

    combinedResultsList.append(combinedResult)

  logging.info('Writing combined results to {}'.format(pargs.output))
  logging.info('# of results:{}'.format(len(combinedResultsList)))
  with open(pargs.output, 'w') as f:
    yamlString = yaml.dump(combinedResultsList, Dumper=Dumper,
        default_flow_style=False)
    f.write(yamlString)
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
