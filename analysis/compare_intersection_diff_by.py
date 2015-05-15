#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import os
import pprint
import logging
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
  parser.add_argument("-s", "--proper-supersets", dest='proper_supersets', action='store_true', help='show information about results in supersets')
  parser.add_argument("-e", "--label-mapping", default=None, type=argparse.FileType('r'), dest="label_mapping",
    help="Group by expected result type from a mapping file")
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  parser.add_argument('--rank-intersection', dest='rank_intersection', action='store_true', default=False)
  parser.add_argument('--only-in', dest='only_in', action='store_true', default=False)

  extraOutputGroup = parser.add_mutually_exclusive_group()
  extraOutputGroup.add_argument("--uncommon", action='store_true')
  extraOutputGroup.add_argument("--common", action='store_true')

  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  correctnessMapping = None
  if pargs.label_mapping != None:
    logging.info('Loading correctness mapping file')
    correctnessMapping = yaml.load(pargs.label_mapping, Loader=Loader)
    validateMappingFile(correctnessMapping)
    benchmarkLabels = ['correct', 'incorrect', 'unknown']
    def labelFieldToString(expected_correct):
      if expected_correct:
        return 'correct'
      elif expected_correct == False:
        return 'incorrect'
      elif expected_correct == None:
        return 'unknown'
      else:
        raise Exception('"expected_correct" must be None or boolean')
  else:
    benchmarkLabels = ['all']

  # Check that each yml file exists
  categorised = { }
  data = { }
  onlyIn = { }
  resultListNames = [ ]
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

    # Initialise data
    categorised[resultListName] = {}
    onlyIn[resultListName] = {}
    for benchmarkLabel in benchmarkLabels:
      categorised[resultListName][benchmarkLabel] = {}
      onlyIn[resultListName][benchmarkLabel] = {}
      for name, _ in FinalResultType.__members__.items():
        categorised[resultListName][benchmarkLabel][name] = { 'raw':[], 'program_set': set() }
        onlyIn[resultListName][benchmarkLabel][name] = None

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
  # Put results into buckets based on labels
  for resultListName in resultListNames:
    for r in data[resultListName]:
      if not 'bug_found' in r:
        logging.error('Key "bug_found" not in result')
        return 1

      if pargs.label_mapping != None:
        expectedCorrect = correctnessMapping[ r['program'] ]['expected_correct']
        assert expectedCorrect == None or isinstance(expectedCorrect, bool)
        benchmarkLabel = labelFieldToString(expectedCorrect)
      else:
        benchmarkLabel = 'all'

      rType = classifyResult(r)
      l = categorised[resultListName][benchmarkLabel][rType.name]['raw']
      assert isinstance(l, list)
      l.append(r)

      programSet = categorised[resultListName][benchmarkLabel][rType.name]['program_set']
      assert isinstance(programSet, set)
      programName = r['program']
      if programName in programSet:
        logging.error('The program {} was already in the set. This shouldn\'t happen'.format(programName))
        return 1
      programSet.add(programName)

      # Setup programToRawResultMap
      try:
        existingDict = programToRawResultMap[programName]
        existingDict[resultListName] = r
      except KeyError:
        programToRawResultMap[programName] = { resultListName:r }


  # Compute union (for count only) and intersection between result sets
  union = {}
  intersection = {}
  # Initialise empty sets
  for name, _ in FinalResultType.__members__.items():
    union[name] = { }
    intersection[name] = { }
    for benchmarkLabel in benchmarkLabels:
      union[name][benchmarkLabel] = set()
      intersection[name][benchmarkLabel] = None

  for name, _ in FinalResultType.__members__.items():
    for resultListName in resultListNames:
      for benchmarkLabel in benchmarkLabels:
        logging.debug('Computing union for {} for benchmark label {} for result set {}'.format(name, benchmarkLabel, resultListName))
        unionSet = union[name][benchmarkLabel]
        union[name][benchmarkLabel] = unionSet.union( categorised[resultListName][benchmarkLabel][name]['program_set'])

        logging.debug('Computing intersection for {} for benchmark label {} for result set {}'.format(name, benchmarkLabel, resultListName))
        intersectionSet = intersection[name][benchmarkLabel]
        if intersectionSet == None:
          # This set hasn't been initialised so make it be a copy of the current set of programs
          # We can't do what we do with unions because we'd intersect with the initially empty set
          intersection[name][benchmarkLabel] = categorised[resultListName][benchmarkLabel][name]['program_set'].copy()
          assert isinstance(intersection[name][benchmarkLabel], set)
        else:
          intersection[name][benchmarkLabel] = intersectionSet.intersection( categorised[resultListName][benchmarkLabel][name]['program_set'])

  # compute onlyIn, start with the programs for that resultListName
  # We will then start removing items until we are left only with the benchmarks
  # that only that resultListName reported
  for resultListName in resultListNames:
    for benchmarkLabel in benchmarkLabels:
      for name, _ in FinalResultType.__members__.items():
        thisResultListsPrograms = categorised[resultListName][benchmarkLabel][name]['program_set'].copy()
        for otherResultListName in list(filter(lambda x: x != resultListName, resultListNames)):
          thisResultListsPrograms = thisResultListsPrograms.difference( categorised[otherResultListName][benchmarkLabel][name]['program_set'] )
        onlyIn[resultListName][benchmarkLabel][name] = thisResultListsPrograms.copy() # copy just to be safe


  # Show computed information
  uncommonResults = { }
  properSuperSetResults = { }
  for name, _ in FinalResultType.__members__.items():
    uncommonResults[name] = { }
    properSuperSetResults[name] = { }
    for benchmarkLabel in benchmarkLabels:
      uncommonResults[name][benchmarkLabel] = set()
      properSuperSetResults[name][benchmarkLabel] = set()

  for benchmarkLabel in benchmarkLabels:
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
      for resultListName in resultListNames:
        if categorised[resultListName][benchmarkLabel][name]['program_set'].issuperset(union[name][benchmarkLabel]):
          superSetResultSet.append(resultListName)

      if len(superSetResultSet) == 0:
        # No result set is a super set of the unioned benchmarks which implies
        # there are uncommon results. Compute this and store it
        uncommonResults[name][benchmarkLabel] = union[name][benchmarkLabel].difference( intersection[name][benchmarkLabel])
      elif len(superSetResultSet) < len(resultListNames):
        # There is at least one proper superset
        properSuperSetResults[name][benchmarkLabel] = union[name][benchmarkLabel].difference( intersection[name][benchmarkLabel])

      superSetString = "Result sets that are super sets of the unioned benchmarks {}".format(superSetResultSet)

      print("# of common results of type {}: {} out of {} ({:.2f}%)\n{}\n".format(name, intersectionSize, unionSize, percentage, superSetString))
      if pargs.only_in:
        for resultListName in resultListNames:
          theSet = onlyIn[resultListName][benchmarkLabel][name]
          assert isinstance(theSet, set)
          print("# of benchmarks only in {} : {}".format(resultListName, len(theSet)))
        print("")

  if pargs.uncommon:
    displayResultSet("uncommon results", uncommonResults, resultListNames, benchmarkLabels, programToRawResultMap)

  if pargs.proper_supersets:
    displayResultSet("superset results", properSuperSetResults, resultListNames, benchmarkLabels, programToRawResultMap)

  if pargs.common:
    displayResultSet("common results", intersection, resultListNames, benchmarkLabels, programToRawResultMap)

  if pargs.rank_intersection:
    rankIntersection(intersection, resultListNames, benchmarkLabels, programToRawResultMap)

  return 0

def displayResultSet(setName, data, resultListNames, benchmarkLabels, programToRawResultMap):
  assert isinstance(setName, str)
  assert isinstance(benchmarkLabels, list)

  for benchmarkLabel in benchmarkLabels:
    print("==={}===".format(benchmarkLabel))
    for name, _ in FinalResultType.__members__.items():
      print("Size of {} for {} {}: {}".format(setName, benchmarkLabel, name, len(data[name][benchmarkLabel])))
      if name == 'BUG_FOUND' or name == 'FULLY_EXPLORED':
        for program in data[name][benchmarkLabel]:
          print("{}".format(program))

          for resultListName in resultListNames:
            rawResult = programToRawResultMap[program][resultListName]
            print("{} : {} ({}) ({} secs)".format(resultListName,
                                                  classifyResult(rawResult),
                                                  rawResult['working_directory'],
                                                  rawResult['total_time']))

          print("")

def rankIntersection(intersection, resultListNames, benchmarkLabels, programToRawResultMap):
  """
    For result intersection rank results by execution time
  """
  print("Ranked results that intersect by execution time:")
  for benchmarkLabel in benchmarkLabels:
    print("==={}===".format(benchmarkLabel))
    for rType in list(FinalResultType):
      if rType != FinalResultType.FULLY_EXPLORED and rType != FinalResultType.BUG_FOUND and rType != FinalResultType.BOUND_HIT:
        # Skip types we don't want to be ranked
        continue
      print("===={}====".format(rType.name))
      sortedResults=[]
      for program in intersection[rType.name][benchmarkLabel]:
        # Gather the resultSets
        resultsForProgram= []
        for resultListName in resultListNames:
          r = programToRawResultMap[program][resultListName]
          # Hack the result set name into the result so we know where it came from
          assert not 'result_set' in r
          r['result_set'] = resultListName
          resultsForProgram.append(r)
        # Reverse sort the results by execution time
        resultsForProgram.sort(key=lambda element: element['total_time'], reverse=True)
        sortedResults.append(resultsForProgram)

      # Now we've collected the results for each program reverse sort them by execution time
      sortedResults.sort(key=lambda l: l[0]['total_time'], reverse=True)

      # Now loop over the resultListName (i.e. the files) printing when a tool came first
      winCount = {}
      for resultListName in resultListNames:
        winCount[resultListName] = 0
        print("====={} won=====".format(resultListName))
        for results in sortedResults:
          if results[-1]['result_set'] != resultListName: # The last element in the list was the fastest (i.e. smallest time)
            continue
          winCount[resultListName] += 1
          print("program: {}".format(results[0]['program']))
          for r in results:
            if 'total_time_stddev' in r:
              print("{} ({} +/- {} secs)".format(r['result_set'], r['total_time'], r['total_time_stddev']))
            else:
              print("{} ({} secs)".format(r['result_set'], r['total_time']))
          print("")
      
      print("**Win summary**")
      for resultListName in resultListNames:
        print("{} : {} wins".format(resultListName, winCount[resultListName]))

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
