#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
This script is designed to take a set of results
and set them all to timeouts.
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

  for r in results:
    r['failed'] = False
    r['bound_hit'] = False
    r['bug_found'] = False
    r['timeout_hit'] = True
    r['exit_code'] = None
    if 'original_results' in r:
      r.pop('original_results')
    r['total_time'] = 900.0
    r['out_of_memory'] = False
    r['total_time_stddev'] = 0.0
    if 'sbx_dir' in r:
      r.pop('sbx_dir')
    r['sbx_dir'] = '/not/real/result'
    r['log_file'] = '/not/real/result'
    if 'instructions_executed' in r:
      r.pop('instructions_executed')

    assert classifyResult(r) == FinalResultType.TIMED_OUT

  # Write result out
  with open(pargs.output_yml, 'w') as f:
    yamlText = yaml.dump(results,
                         default_flow_style=False,
                         Dumper=Dumper)
    f.write(yamlText)

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
