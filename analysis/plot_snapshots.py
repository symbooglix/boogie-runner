#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import logging
import os
import pprint
import sys
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile
import matplotlib.pyplot as plt

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper


def main(args):
  resultTypes = [ r.name for r in list(FinalResultType)] # Get list of ResultTypes as strings
  defaultTypes = resultTypes

  # We clamp these to the max time to penalise them
  # as if they were a timeout
  resultTypesToClamp = [ FinalResultType.BOUND_HIT,
                         FinalResultType.OUT_OF_MEMORY,
                         FinalResultType.UNKNOWN]

  parser = argparse.ArgumentParser()
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("-v", "--verbose", action='store_true', help='Show detailed information about mismatch')
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  parser.add_argument('max_time', type=int, help='Maximum time in seconds, results timings will be clamped to this value')
  parser.add_argument('--ipython', action='store_true')
  parser.add_argument('--point-size', type=float, default=30.0, dest='point_size')
  parser.add_argument('-r', '--result-type', nargs='+', dest='result_type', choices=resultTypes, default=defaultTypes, help='Filter by FinalResultType')
  pargs = parser.parse_args(args)
  print(pargs)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if len(pargs.result_ymls) < 2:
    logger.error('Need at least two YAML files')

  # Create set of allowed result types
  allowedResultTypes = set()
  for rType in pargs.result_type:
    allowedResultTypes.add(FinalResultType[rType])

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
  for resultListName in resultListNames:
    for r in data[resultListName]:
      programName = r['program']
      try:
        existingDict = programToResultSetsMap[programName]
        existingDict[resultListName] = r
      except KeyError:
        programToResultSetsMap[programName] = { resultListName:r }

  # Check there are the same number of results for each program
  clampCount = 0
  skipCount = 0

  snapshotToTotalTimeMap = { }
  for resultListName in resultListNames:
    snapshotToTotalTimeMap[resultListName] = 0.0

  # Accumulate the total "effective" runtime of a snapshot
  for programName, resultListNameToRawResultMap  in programToResultSetsMap.items():
    if len(resultListNameToRawResultMap) != len(resultListNames):
      logging.error('For program {} there we only {} result lists but expected {}'.format(
        programName, len(resultListNameToRawResultMap), len(resultListNames)))
      logging.error(pprint.pformat(resultListNameToRawResultMap))
      return 1

    skipProgram = False
    for resultListName in resultListNames:
      result = resultListNameToRawResultMap[resultListName]
      rType = classifyResult(result)
      if not rType in allowedResultTypes:
        logging.warning('Skipping {}, disallowed result type {}'.format(programName, rType))
        skipProgram = True
        skipCount += 1
        break

    if skipProgram:
      continue

    # Clamp results if they are of a particular type
    didClamp = False
    for resultListName in resultListNames:
      result = resultListNameToRawResultMap[resultListName]
      rType = classifyResult(result)
      if rType in resultTypesToClamp or result['total_time'] > pargs.max_time:
        logging.info('Clamping result {} in {} with FinalResultType: {}'.format(
          programName,
          resultListName,
          rType))
        result['total_time'] = pargs.max_time
        result['clamped_due_to_result_type'] = True
        didClamp = True
        
      # Add to the total times
      currentTotal = snapshotToTotalTimeMap[resultListName]
      assert currentTotal >= 0.0
      currentTotal += resultListNameToRawResultMap[resultListName]['total_time']
      snapshotToTotalTimeMap[resultListName] = currentTotal

    if didClamp:
      clampCount += 1


  logging.info('Total # of programs (given as input): {}'.format(length))
  logging.info('# of skipped programs: {}'.format(skipCount))
  logging.info('# of clamped programs: {}'.format(clampCount))
  # TODO: This is work in progress
  # we need some way of estimating the error in these numbers. Remember Walter
  # Lewein "a measurement without uncertainty is meaningless!"
  print(pprint.pformat(snapshotToTotalTimeMap))
  # Arithmetic mean
  print(pprint.pformat({k: v/length for k,v in snapshotToTotalTimeMap.items()}))
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
