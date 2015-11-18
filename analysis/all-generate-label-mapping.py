#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab tw=80 colorcolumn=80:
"""
This script takes a program list are marks them all
correct or incorrect
"""
import argparse
import logging
import os
import pprint
import sys
import yaml
from br_util import validateMappingFile

# HACK
_file = os.path.abspath(__file__)
_dir = os.path.dirname(os.path.dirname(_file))
sys.path.insert(0, _dir)
from BoogieRunner import ProgramListLoader

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info",
    dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--rprefix", default=os.getcwd(),
    help="Prefix for relative paths for program_list")
  parser.add_argument('program_list', help="List of SV-COMP bencharks")
  parser.add_argument('output_mapping_file',
    help='Output path for mapping file')

  group = parser.add_mutually_exclusive_group()
  group.add_argument('--correct', action='store_true')
  group.add_argument('--incorrect', action='store_true')

  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  labelAsCorrect = None
  if pargs.correct:
    labelAsCorrect = True
  elif pargs.incorrect:
    labelAsCorrect = False
  else:
    logging.error('Unreachable')
    return1

  if not os.path.exists(pargs.program_list):
    logging.error('"{}" does not exist'.format(pargs.program_list))
    return 1

  if os.path.exists(pargs.output_mapping_file):
    logging.error('Refusing to overwrite "{}"'.format(
      pargs.output_mapping_file))
    return 1

  programList = None
  try:
    logging.info('Loading program_list from "{}"'.format(pargs.program_list))
    programList = ProgramListLoader.load(pargs.program_list, pargs.rprefix)
  except (ProgramListLoader.ProgramListLoaderException) as e:
    logging.error(e)
    logging.debug(traceback.format_exc())
    return 1

  labelMapping = { }
  for programPath in programList:
    assert not programPath in labelMapping
    correct = labelAsCorrect

    # Remove rprefix from path, the + '/' is a hack
    strippedProgramPath = programPath.replace(pargs.rprefix + '/','')

    logging.debug('"{}" => {}'.format(strippedProgramPath, correct))
    labelMapping[strippedProgramPath] = { 'expected_correct': correct }

  # Validate
  validateMappingFile(labelMapping)

  # Write output
  logging.info('Writing mapping file to "{}"'.format(pargs.output_mapping_file))
  with open(pargs.output_mapping_file, 'w') as f:
    yamlString = yaml.dump(labelMapping, Dumper=Dumper,
        default_flow_style=False)
    f.write(yamlString)

  return 0
if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
