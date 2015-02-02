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

  # Initialise data structures
  buckets = { }
  for name, _ in FinalResultType.__members__.items():
    corOrIn = {}
    corOrIn['correct'] = []
    corOrIn['incorrect'] = []
    buckets[name] = corOrIn


  # Put results into buckets
  for r in results:
    if not 'bug_found' in r:
      logging.error('Key "bug_found" not in result')
      return 1

    if not 'expected_correct' in r:
      logging.error('Key "expected_correct" not in result')
      return 1

    expectedCorrect = r['expected_correct']
    assert expectedCorrect != None

    rType = classifyResult(r)
    l = buckets[rType.name][ 'correct' if expectedCorrect else 'incorrect']
    assert isinstance(l, list)
    l.append(r)

  # Output information
  print("Total # of results: {}".format(len(results)))
  for name, _ in FinalResultType.__members__.items():
    total = len(buckets[name]['correct']) + len(buckets[name]['incorrect'])
    print("Result of type {} (total {})".format(name, total))
    print("# expected correct: {}".format(len(buckets[name]['correct'])))
    print("# expected incorrect: {}".format(len(buckets[name]['incorrect'])))
    print("")
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
