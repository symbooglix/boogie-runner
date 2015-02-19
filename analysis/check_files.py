#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
Script to load multiple YAML result files and check
the files between them are consistent
"""
import argparse
import os
import pprint
import logging
import sys
import yaml

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--check-expected-correct", dest="check_expected_correct", help='Check "expected_correct" key is consistent')
  parser.add_argument('yml_files', nargs='+')
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  results = [ ]
  for index, filePath in enumerate(pargs.yml_files):

    if not os.path.exists(filePath):
      logging.error('{} does not exist'.format(filePath))
      return 1

    with open(filePath, 'r') as f:
      logging.info('Loading {}'.format(filePath))
      l = yaml.load(f, Loader=Loader)
    assert isinstance(l, list)
    results.append(l)

    if len(l) == 0:
      logging.error('File {} has no entries'.format(filePath))
      return 1


  # Create sets of used files
  programsIn = [ ]
  resultsMissingFrom = []
  programNameToListOfResultsMap = { }
  for index, rList in enumerate(results):
    assert len(programsIn) == index
    programsIn.append(set())
    resultsMissingFrom.append([])
    for r in rList:
      if r['program'] in programsIn[index]:
        logging.error('{} has a duplicate program entry "{}"'.format(pargs.yml_files[index], r['program']))
        return 1
      if pargs.check_expected_correct:
        if not 'expected_correct' in r:
          logging.error('The following result from file {} is missing "expected_correct":\n{}'.format(pargs.yml_files[index], r))
          return 1

      if not r['program'] in programNameToListOfResultsMap:
        programNameToListOfResultsMap[r['program']] = [ ]

      programsIn[index].add(r['program'])
      programNameToListOfResultsMap[r['program']].append(r)

  # Go through the different pairs (must do both orders)
  assert len(resultsMissingFrom) == len(results)
  for i in range(0, len(results)):
    fromSet = programsIn[i]
    assert len(fromSet) > 0
    # Set up [<from id>]{<but in id>] = [ ]
    resultsMissingFrom[i] = [ [ ] for _ in results ]
    assert len(resultsMissingFrom[i]) == len(results)

    for j in range(0, len(results)):
      if i == j:
        continue
      diff = programsIn[j].difference(fromSet)
      if len(diff) != 0:
        for program in diff:
          # FIXME: Record result set instead
          resultsMissingFrom[i][j].append( program )


  # Output
  index = 0
  exitCode = 0
  for missingFromList, filePath in zip(resultsMissingFrom, pargs.yml_files):
    assert isinstance(missingFromList, list)
    print("# of results in {}: {}".format(filePath, len(results[index])))
    for otherIndex in range(0, len(results)):
      if index == otherIndex:
        continue
      missing = resultsMissingFrom[index][otherIndex]
      if len(missing) > 0:
        print("{} results present in {} but not in {}".format(len(missing), pargs.yml_files[otherIndex], filePath))
        print("{}".format(pprint.pformat(missing)))
        exitCode = 2
    index += 1

  # Check "expected_correct" labels are consistent
  if pargs.check_expected_correct:
    if exitCode != 0:
      logging.error('Not checking "expected_correct" consistency because the number of files is not consistent')
    else:
      for progName, listOfResults in programNameToListOfResultsMap.items():
        expected = listOfResults[0]['expected_correct']
        assert len(listOfResults) > 1
        for index in range(1, len(listOfResults)):
          if listOfResults[index]['expected_correct'] != expected:
            logging.error('"expected_correct" labels are inconsistent for program "{}"'.format(progName))
            exitCode = 3
            break

    if exitCode == 0:
      logging.info('All "expected_correct" labels are consistent')

  return exitCode

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
