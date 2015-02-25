#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
Script to remove obsolete correctness labels
from result files.
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
  parser.add_argument("yml_file", help='YAML result file')
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if not os.path.exists(pargs.yml_file):
    logging.error('"{}" does not exist'.format(pargs.yml_file))
    return 1

  results = None
  with open(pargs.yml_file, 'r') as f:
    logging.info('Loading {}'.format(pargs.yml_file))
    results = yaml.load(f, Loader=Loader)
  assert isinstance(results, list)
  assert len(results) > 0

  for r in results:
    assert isinstance(r, dict)
    if 'expected_correct' in r:
      del r['expected_correct']


  with open(pargs.yml_file, 'w') as f:
    logging.info('Writing {}'.format(pargs.yml_file))
    yamlStr = yaml.dump(results, Dumper=Dumper, default_flow_style=False)
    f.write(yamlStr)
  assert isinstance(results, list)
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
