#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
This script is designed to patch old symbooglix
results where hitting speculative paths was incorrect
treated as BOUND_HIT
"""
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
  parser.add_argument('input_yml', type=argparse.FileType('r'))
  parser.add_argument('output_yml', type=str)
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if os.path.exists(pargs.output_yml):
    logging.error('Refusing to overwrite "{}"'.format(pargs.output_yml))
    return 1

  results = yaml.load(pargs.input_yml, Loader=Loader)

  assert isinstance(results, list)

  if len(results) == 0:
    logging.error('Result list is empty')
    return 1

  # Count
  rewriteCount = 0
  rTypeToResultMap = {}
  for rType in FinalResultType:
    rTypeToResultMap[rType] = []

  for r in results:
    rType = classifyResult(r)
    logging.debug('Classified {} as {}'.format(r['program'], rType))

    if rType == FinalResultType.BOUND_HIT:
      logging.info('Classified {} as {}'.format(r['program'], rType))
      logging.info('Doing rewrite')
      rewriteCount += 1

      # Sanity checks
      assert r['failed'] == False
      assert r['bound_hit'] == True
      assert r['speculative_paths_nb'] == True

      # Set new values
      r['failed'] = True
      r['bound_hit'] = False

      assert classifyResult(r) == FinalResultType.UNKNOWN

    rTypeToResultMap[classifyResult(r)].append(r)

  print("Rewrite count: {}".format(rewriteCount))

  print("Total: {}".format(len(results)))
  for rType in FinalResultType:
    name = rType.name
    resultList = rTypeToResultMap[rType]
    print("# of {}: {} ({:.2f}%)".format(name, len(resultList),
      100*float(len(resultList))/len(results)))

  # Write result out
  with open(pargs.output_yml, 'w') as f:
    yamlText = yaml.dump(results,
                         default_flow_style=False,
                         Dumper=Dumper)
    f.write(yamlText)

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
