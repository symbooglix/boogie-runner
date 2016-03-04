#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import os
import pprint
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
  parser.add_argument('--show-false-positives', dest='show_false_positives', action='store_true')
  pargs = parser.parse_args(args)

  logging.info('Loading correctness label mapping file')
  correctnessMapping = yaml.load(pargs.label_mapping_file, Loader=Loader)
  validateMappingFile(correctnessMapping)

  logging.info('Loading YAML file')
  results = yaml.load(pargs.result_yml, Loader=Loader)
  logging.info('Loading complete')

  assert isinstance(results, list)

  # Put results into buckets
  expectedCorrectCount = 0
  expectedIncorrectCount = 0
  expectedUnknownCount = 0
  labelledCorrect, labelledIncorrect, labelledUnknown = groupByResultTypeThenLabel(results, correctnessMapping)
  assert isinstance(labelledCorrect, dict) and isinstance(labelledIncorrect, dict) and isinstance(labelledUnknown, dict)

  for l in labelledCorrect.values():
    expectedCorrectCount += len(l)
  for l in labelledIncorrect.values():
    expectedIncorrectCount += len(l)
  for l in labelledUnknown.values():
    expectedUnknownCount += len(l)

  # Output information

  sortedResultTypeNames = [ name for name, _ in FinalResultType.__members__.items()]
  sortedResultTypeNames.sort()

  collectiveUnknownTypes = list(map(lambda x: x.name, [FinalResultType.OUT_OF_MEMORY, FinalResultType.TIMED_OUT, FinalResultType.UNKNOWN, FinalResultType.BOUND_HIT]))

  falseAlarmCount=0
  collectiveUnknownCount=0
  print("Total # of results: {}".format(len(results)))
  print("Results expected to be correct (total {})".format(expectedCorrectCount))
  if expectedCorrectCount > 0:
    for rTypeName in sortedResultTypeNames:
      l = labelledCorrect[rTypeName]
      assert isinstance(l, list)
      percentage = 100 * (float(len(l))/ expectedCorrectCount)
      # Add description if appropriate
      if rTypeName == "FULLY_EXPLORED":
        desc="[True Negatives]"
      elif rTypeName == "BUG_FOUND":
        desc="[False Positives]"
        falseAlarmCount += len(l)
      else:
        desc=""
      if rTypeName in collectiveUnknownTypes:
        collectiveUnknownCount += len(l)
      print("# classified as {}: {} ({:.2f}%) {}".format(rTypeName, len(l), percentage, desc))
      if rTypeName == "BUG_FOUND" and pargs.show_false_positives:
        print("{}".format(pprint.pformat(l)))

  print("Results expected to be incorrect (total {})".format(expectedIncorrectCount))
  if expectedIncorrectCount > 0:
    for rTypeName in sortedResultTypeNames:
      l = labelledIncorrect[rTypeName]
      assert isinstance(l, list)
      percentage = 100 * (float(len(l))/ expectedIncorrectCount)
      # Add descriptiont if appropriate
      if rTypeName == "BUG_FOUND":
        desc="[True Positives]"
      elif rTypeName == "FULLY_EXPLORED":
        desc="[False Negatives]"
        falseAlarmCount += len(l)
      else:
        desc=""

      if rTypeName in collectiveUnknownTypes:
        collectiveUnknownCount += len(l)

      print("# classified as {}: {} ({:.2f}%) {}".format(rTypeName, len(l), percentage, desc))
  print("Results expected to be unknown (total {})".format(expectedUnknownCount))
  if expectedUnknownCount > 0:
    for rTypeName in sortedResultTypeNames:
      l = labelledUnknown[rTypeName]

      if rTypeName in collectiveUnknownTypes or rTypeName == "BUG_FOUND": # The BUG_FOUND must be a tool that gives false postives so we didn't trust it when generating the correctness labelling
        collectiveUnknownCount += len(l)

      assert isinstance(l, list)
      percentage = 100 * (float(len(l))/ expectedUnknownCount)
      print("# classified as {}: {} ({:.2f}%)".format(rTypeName, len(l), percentage))

  print("")
  print("# of false alarms: {}".format(falseAlarmCount))
  print("# of Collective unknowns (includes BUG_FOUND if benchmark classified as unknown): {}".format(collectiveUnknownCount))

  return 0

def groupByResultTypeThenLabel(results, correctnessMapping, keyIsEnum=False):
  if correctnessMapping != None:
    validateMappingFile(correctnessMapping)

  labelledCorrect = { }
  labelledIncorrect = { }
  labelledUnknown = { }
  labelledAll = { } # only used if there is no correctness mapping
  if keyIsEnum:
    # use the enum as the key
    for name in FinalResultType:
      labelledCorrect[name] = [ ]
      labelledIncorrect[name] = [ ]
      labelledUnknown[name] = [ ]
      labelledAll[name] = [ ]
  else:
    # Use the string as the key
    for name, _ in FinalResultType.__members__.items():
      labelledCorrect[name] = [ ]
      labelledIncorrect[name] = [ ]
      labelledUnknown[name] = [ ]
      labelledAll[name] = [ ]


  # Put results into buckets
  for r in results:
    if not 'bug_found' in r:
      logging.error('Key "bug_found" not in result')
      return 1

    if correctnessMapping != None:
      expectedCorrect = correctnessMapping[ r['program'] ]['expected_correct']
      if expectedCorrect == True:
        dictToWriteTo = labelledCorrect
      elif expectedCorrect == False:
        dictToWriteTo = labelledIncorrect
      elif expectedCorrect == None:
        dictToWriteTo = labelledUnknown
      else:
        raise Exception('Unreachable')
    else:
      dictToWriteTo = labelledAll

    rType = classifyResult(r)
    l = dictToWriteTo[rType if keyIsEnum else rType.name]
    assert isinstance(l, list)
    l.append(r)

  if correctnessMapping != None:
    return (labelledCorrect, labelledIncorrect, labelledUnknown)
  else:
    return labelledAll


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
