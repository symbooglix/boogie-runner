#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
This script takes two or more result files which
are each intended to be a run on the same benchmark
suite of the same tool and then picks the "best"
result for each benchmark (determined by the
``pickBestResult`` function)
"""
import argparse
import logging
import os
import pprint
import sys
import traceback
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile, pickBestResult, PickBestResultException

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
  bestResultList = [ ]
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

    # Now determine which result out of result lists is the "best" for
    # this particular ``programName``
    try:
      bestResultName = pickBestResult(resultListNameToRawResultMap)
    except PickBestResultException as e:
      logging.error('Error for program: {}'.format(programName))
      logging.error(traceback.format_exc())
      return 1
    bestResult = resultListNameToRawResultMap[bestResultName]
    bestResult['from_result'] = bestResultName
    bestResultClassification = classifyResult(bestResult)
    logging.debug('For {} picked {} [{}]'.format(programName,
      bestResultName,
      bestResultClassification))
    logging.debug(pprint.pformat(bestResult))
    bestResultList.append(bestResult)

  logging.info('Writing best results to {}'.format(pargs.output))
  logging.info('# of results:{}'.format(len(bestResultList)))
  with open(pargs.output, 'w') as f:
    yamlString = yaml.dump(bestResultList, Dumper=Dumper,
        default_flow_style=False)
    f.write(yamlString)
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
