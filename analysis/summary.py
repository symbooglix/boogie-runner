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
  parser.add_argument('result_yml', type=argparse.FileType('r'))
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  results = yaml.load(pargs.result_yml, Loader=Loader)

  assert isinstance(results, list)

  if len(results) == 0:
    logging.error('Result list is empty')
    return 1

  # Count
  rTypeToResultMap = {}
  for rType in FinalResultType:
    rTypeToResultMap[rType] = []

  for r in results:
    rType = classifyResult(r)
    logging.debug('Classified {} as {}'.format(r['program'], rType))
    rTypeToResultMap[rType].append(r)

  print("Total: {}".format(len(results)))
  for rType in FinalResultType:
    name = rType.name
    resultList = rTypeToResultMap[rType]
    print("# of {}: {} ({:.2f}%)".format(name, len(resultList),
      100*float(len(resultList))/len(results)))

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
