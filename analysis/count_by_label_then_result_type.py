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
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser()
  parser.add_argument('result_yml', type=argparse.FileType('r'), help='Input YAML file')
  pargs = parser.parse_args(args)

  logging.info('Loading YAML file')
  results = yaml.load(pargs.result_yml, Loader=Loader)
  logging.info('Loading complete')

  assert isinstance(results, list)

  labelledCorrect = { }
  labelledIncorrect = { }
  for name, _ in FinalResultType.__members__.items():
    labelledCorrect[name] = [ ]
    labelledIncorrect[name] = [ ]


  # Put results into buckets
  expectedCorrectCount = 0
  expectedIncorrectCount = 0
  for r in results:
    if not 'bug_found' in r:
      logging.error('Key "bug_found" not in result')
      return 1

    if not 'expected_correct' in r:
      logging.error('Key "expected_correct" not in result')
      return 1

    expectedCorrect = r['expected_correct']
    assert expectedCorrect != None
    if expectedCorrect:
      expectedCorrectCount += 1
    else:
      expectedIncorrectCount += 1

    dictToWriteTo = labelledCorrect if expectedCorrect else labelledIncorrect
    
    rType = classifyResult(r)
    l = dictToWriteTo[rType.name]
    assert isinstance(l, list)
    l.append(r)

  # Output information
  print("Total # of results: {}".format(len(results)))
  print("Results expected to be correct (total {})".format(expectedCorrectCount))
  for label, l in labelledCorrect.items():
    assert isinstance(l, list)
    percentage = 100 * (float(len(l))/ expectedCorrectCount)
    print("# classified as {}: {} ({:.2f}%)".format(label, len(l), percentage))
  print("Results expected to be incorrect (total {})".format(expectedIncorrectCount))
  for label, l in labelledIncorrect.items():
    assert isinstance(l, list)
    percentage = 100 * (float(len(l))/ expectedIncorrectCount)
    print("# classified as {}: {} ({:.2f}%)".format(label, len(l), percentage))

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
