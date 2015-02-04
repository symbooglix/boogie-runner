#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import os
import logging
import sys
import yaml
from br_util import FinalResultType, classifyResult

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper


def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--uncommon", action='store_true')
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  # Check that each yml file exists
  categorised = { }
  data = { }
  resultSetLabels = [ ]
  for f in pargs.result_ymls:
    if not os.path.exists(f):
      logging.error('YAML file {} does not exist'.format(f))
      return 1

    # Compute result set label
    resultSetLabel = os.path.basename(f)
    resultSetLabels.append(resultSetLabel)
    if resultSetLabel in data:
      logging.error('Can\'t use {} as label name because it is already used'.format(label))
      return 1

    data[resultSetLabel] = None # Will be filled with loaded YAML data

    # Initialise data
    categorised[resultSetLabel] = { 'correct': {}, 'incorrect': {} }
    for name, _ in FinalResultType.__members__.items():
      categorised[resultSetLabel]['correct'][name] = { 'raw':[], 'program_set': set() }
      categorised[resultSetLabel]['incorrect'][name] = { 'raw':[], 'program_set': set() }


  # Now load YAML
  length = 0
  for f in pargs.result_ymls:
    logging.info('Loading YAML file {}'.format(f))
    with open(f, 'r') as openFile:
      results = yaml.load(openFile, Loader=Loader)
    logging.info('Loading complete')
    assert isinstance(results, list)
    resultSetLabel = os.path.basename(f)
    data[resultSetLabel] = results
    length = len(results)

  # Check the lengths are the same
  for name, rList in data.items():
    if len(rList) != length:
      logging.error('There is a length mismatch for {}, expected {} entries but was'.format(name, length, len(rList)))
      return 1
    
  programToRawResultMap = { }
  # Put results into buckets based on labels
  for resultSetLabel in resultSetLabels:
    for r in data[resultSetLabel]:
      if not 'bug_found' in r:
        logging.error('Key "bug_found" not in result')
        return 1

      if not 'expected_correct' in r:
        logging.error('Key "expected_correct" not in result')
        return 1

      expectedCorrect = r['expected_correct']
      assert expectedCorrect != None

      
      rType = classifyResult(r)
      l = categorised[resultSetLabel][ 'correct' if expectedCorrect else 'incorrect'][rType.name]['raw']
      assert isinstance(l, list)
      l.append(r)

      programSet = categorised[resultSetLabel][ 'correct' if expectedCorrect else 'incorrect'][rType.name]['program_set']
      assert isinstance(programSet, set)
      programName = r['program']
      if programName in programSet:
        logging.error('The program {} was already in the set. This shouldn\'t happen'.format(programName))
        return 1
      programSet.add(programName)

      # Setup programToRawResultMap
      try:
        existingDict = programToRawResultMap[programName]
        existingDict[resultSetLabel] = r
      except KeyError:
        programToRawResultMap[programName] = { resultSetLabel:r }

  # Compute union (for count only) and intersection between result sets
  union = {}
  intersection = {}
  # Initialise empty sets
  for name, _ in FinalResultType.__members__.items():
    union[name] = { 'correct': set(), 'incorrect': set() }
    intersection[name] = { 'correct': None, 'incorrect': None }

  for name, _ in FinalResultType.__members__.items():
    for resultSetLabel in resultSetLabels:
      for benchmarkLabel in ['correct', 'incorrect']:
        logging.debug('Computing union for {} for benchmark label {} for result set {}'.format(name, benchmarkLabel, resultSetLabel))
        unionSet = union[name][benchmarkLabel]
        union[name][benchmarkLabel] = unionSet.union( categorised[resultSetLabel][benchmarkLabel][name]['program_set'])

        logging.debug('Computing intersection for {} for benchmark label {} for result set {}'.format(name, benchmarkLabel, resultSetLabel))
        intersectionSet = intersection[name][benchmarkLabel]
        if intersectionSet == None:
          # This set hasn't been initialised so make it be a copy of the current set of programs
          # We can't do what we do with unions because we'd intersect with the initially empty set
          intersection[name][benchmarkLabel] = categorised[resultSetLabel][benchmarkLabel][name]['program_set'].copy()
          assert isinstance(intersection[name][benchmarkLabel], set)
        else:
          intersection[name][benchmarkLabel] = intersectionSet.intersection( categorised[resultSetLabel][benchmarkLabel][name]['program_set'])

  # Show computed information
  uncommonResults = { }
  for name, _ in FinalResultType.__members__.items():
    uncommonResults[name] = { }
    for benchmarkLabel in ['correct', 'incorrect']:
      uncommonResults[name][benchmarkLabel] = set()

  for benchmarkLabel in ['correct', 'incorrect']:
    print("==={}===".format(benchmarkLabel))
    for name, _ in FinalResultType.__members__.items():
      # Get set sizes
      intersectionSize = len(intersection[name][benchmarkLabel])
      unionSize = len(union[name][benchmarkLabel])
      assert intersectionSize <= unionSize
      if unionSize > 0:
        percentage = 100 * (float(intersectionSize)/unionSize)
      else:
        percentage = 0

      uncommonResults[name][benchmarkLabel] = set()

      # Compute if any result set (i.e. from a tool) is a super set of the unioned benchmarks
      superSetResultSet = [ ]
      for resultSetLabel in resultSetLabels:
        if categorised[resultSetLabel][benchmarkLabel][name]['program_set'].issuperset(union[name][benchmarkLabel]):
          superSetResultSet.append(resultSetLabel)

      if len(superSetResultSet) == 0:
        # No result set is a super set of the unioned benchmarks which implies
        # there are uncommon results. Compute this and store it
        uncommonResults[name][benchmarkLabel] = union[name][benchmarkLabel].difference( intersection[name][benchmarkLabel])

      superSetString = "Result sets that are super sets of the unioned benchmarks {}".format(superSetResultSet)

      print("# of common results of type {}: {} out of {} ({:.2f}%)\n{}\n".format(name, intersectionSize, unionSize, percentage, superSetString))

  if pargs.uncommon:
    for benchmarkLabel in ['correct', 'incorrect']:
      print("==={}===".format(benchmarkLabel))
      for name, _ in FinalResultType.__members__.items():
        print("Size of uncommon results for {} {}: {}".format(benchmarkLabel, name, len(uncommonResults[name][benchmarkLabel])))
        if name == 'BUG_FOUND' or name == 'FULLY_EXPLORED':
          for program in uncommonResults[name][benchmarkLabel]:
            print("{}".format(program))

            for resultSetLabel in resultSetLabels:
              print("{} : {}".format(resultSetLabel, classifyResult(programToRawResultMap[program][resultSetLabel])))

            print("")

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
