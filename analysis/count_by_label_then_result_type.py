#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import os
import logging
import sys
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile, ValidateMappingFileException

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper


def main(args):
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser()
  parser.add_argument('label_mapping_file', type=argparse.FileType('r'),
    help='correctness label mapping file')
  parser.add_argument('result_yml', type=argparse.FileType('r'), help='Input YAML file')
  pargs = parser.parse_args(args)

  logging.info('Loading correctness label mapping file')
  correctnessMapping = yaml.load(pargs.label_mapping_file, Loader=Loader)
  validateMappingFile(correctnessMapping)

  logging.info('Loading YAML file')
  results = yaml.load(pargs.result_yml, Loader=Loader)
  logging.info('Loading complete')

  assert isinstance(results, list)

  labelledCorrect = { }
  labelledIncorrect = { }
  labelledUnknown = { }
  for name, _ in FinalResultType.__members__.items():
    labelledCorrect[name] = [ ]
    labelledIncorrect[name] = [ ]
    labelledUnknown[name] = [ ]


  # Put results into buckets
  expectedCorrectCount = 0
  expectedIncorrectCount = 0
  expectedUnknownCount = 0
  for r in results:
    if not 'bug_found' in r:
      logging.error('Key "bug_found" not in result')
      return 1

    expectedCorrect = correctnessMapping[ r['program'] ]['expected_correct']
    if expectedCorrect == True:
      expectedCorrectCount += 1
      dictToWriteTo = labelledCorrect
    elif expectedCorrect == False:
      expectedIncorrectCount += 1
      dictToWriteTo = labelledIncorrect
    elif expectedUnknownCount == None:
      expectedUnknownCount += 1
      dictToWriteTo = labelledUnknown
    else:
      raise Exception('Unreachable')

    rType = classifyResult(r)
    l = dictToWriteTo[rType.name]
    assert isinstance(l, list)
    l.append(r)

  # Output information

  sortedResultTypeNames = [ name for name, _ in FinalResultType.__members__.items()]
  sortedResultTypeNames.sort()

  print("Total # of results: {}".format(len(results)))
  print("Results expected to be correct (total {})".format(expectedCorrectCount))
  if expectedCorrectCount > 0:
    for label in sortedResultTypeNames:
      l = labelledCorrect[label]
      assert isinstance(l, list)
      percentage = 100 * (float(len(l))/ expectedCorrectCount)
      print("# classified as {}: {} ({:.2f}%)".format(label, len(l), percentage))
  print("Results expected to be incorrect (total {})".format(expectedIncorrectCount))
  if expectedIncorrectCount > 0:
    for label in sortedResultTypeNames:
      l = labelledIncorrect[label]
      assert isinstance(l, list)
      percentage = 100 * (float(len(l))/ expectedIncorrectCount)
      print("# classified as {}: {} ({:.2f}%)".format(label, len(l), percentage))
  print("Results expected to be unknown (total {})".format(expectedUnknownCount))
  if expectedUnknownCount > 0:
    for label in sortedResultTypeNames:
      l = labelledUnknown[label]
      assert isinstance(l, list)
      percentage = 100 * (float(len(l))/ expectedUnknownCount)
      print("# classified as {}: {} ({:.2f}%)".format(label, len(l), percentage))

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
