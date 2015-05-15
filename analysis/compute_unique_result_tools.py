#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
Compute the number of times a tool was the only
tool to give a useful result.
"""
import argparse
import os
import pprint
import logging
import pprint
import sys
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("only_show", choices=['correct', 'incorrect', 'unknown'], help='The benchmarks with the expect result type to show')
  parser.add_argument("label_mapping", default=None, type=argparse.FileType('r'))
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')

  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  correctnessMapping = None
  logging.info('Loading correctness mapping file')
  correctnessMapping = yaml.load(pargs.label_mapping, Loader=Loader)
  validateMappingFile(correctnessMapping)

  # Check that each yml file exists
  data = { }
  resultListNames = [ ]
  uniqueResults = {}
  for f in pargs.result_ymls:
    if not os.path.exists(f):
      logging.error('YAML file {} does not exist'.format(f))
      return 1

    # Compute result set label
    resultListName = f
    resultListNames.append(resultListName)
    if resultListName in data:
      logging.error('Can\'t use {} as label name because it is already used'.format(resultListName))
      return 1

    data[resultListName] = None # Will be filled with loaded YAML data
    uniqueResults[resultListName] = [] # prepare

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
      logging.error('There is a length mismatch for {}, expected {} entries but was {}'.format(name, length, len(rList)))
      return 1

  programToRawResultMap = { }
  for resultListName in resultListNames:
    for r in data[resultListName]:
      # Setup programToRawResultMap
      programName = r['program']

      # Only add programs that we want
      if not programName in correctnessMapping:
        logging.error('{} is missing from correctness mapping'.format(programName))
        return 1
      expectedCorrect = correctnessMapping[programName]['expected_correct']
      assert expectedCorrect == None or isinstance(expectedCorrect, bool)

      skipBenchmark = False
      if pargs.only_show == 'incorrect':
        if expectedCorrect != False:
          skipBenchmark = True
      elif pargs.only_show == 'correct':
        if expectedCorrect != True:
          skipBenchmark = True
      elif pargs.only_show == 'unknown':
        if expectedCorrect != None:
          skipBenchmark = True
      else:
        assert False

      if skipBenchmark:
        logging.debug('Filtering out {} ({}) because we are only showing benchmarks labelled as {}'.format(programName, expectedCorrect, pargs.only_show))
        continue
      try:
        existingDict = programToRawResultMap[programName]
        existingDict[resultListName] = r
      except KeyError:
        programToRawResultMap[programName] = { resultListName:r }

  logging.info('Counting results expected to be "{}"'.format(pargs.only_show))
  # Now walk through each program and see if only a single gave a useful answer
  for programName, rawResultMap in programToRawResultMap.items():
    expectedCorrect = correctnessMapping[programName]['expected_correct']
    assert expectedCorrect == None or isinstance(expectedCorrect, bool)
    if pargs.only_show == 'incorrect':
      assert expectedCorrect == False 
    elif pargs.only_show == 'correct':
      assert expectedCorrect == True
    elif pargs.only_show == 'unknown':
      assert expectedCorrect == None
    else:
      assert False

    r , resultListName = getResultIfOnlySingleToolGaveUsefulResult( expectedCorrect,
                                            rawResultMap)

    if r != None:
      logging.info('{} was only tool to give result {} for {}'.format(
        resultListName, classifyResult(r), programName))
      uniqueResults[resultListName].append(r)
      logging.debug(pprint.pformat(rawResultMap))
    else:
      logging.debug('There was no unique tool for {}'.format(programName))

  # Now report numbers
  logging.info('Showing unique results where the expected correctness was {}'.format(pargs.only_show))
  for resultListName, listOfUniqueResults in uniqueResults.items():
    assert isinstance(listOfUniqueResults, list)
    logging.info('# of unique results for {} : {}'.format(resultListName, len(listOfUniqueResults)))
      
    
def getResultIfOnlySingleToolGaveUsefulResult(expectedCorrect, rawResultMap):
  desiredResultType = None
  if expectedCorrect == True:
    desiredResultType = FinalResultType.FULLY_EXPLORED
  elif expectedCorrect == False:
    desiredResultType = FinalResultType.BUG_FOUND
  else:
    raise Exception('Not supported')

  matchingResults = { }
  for resultListName, rawResult in rawResultMap.items():
    assert isinstance(resultListName, str)
    assert isinstance(rawResult, dict)
    rType = classifyResult(rawResult)
    if rType == desiredResultType:
      assert not resultListName in matchingResults
      matchingResults[resultListName] = rawResult

  if len(matchingResults) == 1:
    k, v = matchingResults.popitem()
    return (v, k)
  else:
    return (None, None)

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
