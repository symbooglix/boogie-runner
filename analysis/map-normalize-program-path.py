#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
Strip prefix from key used in a correctness label map. This can be used if
slightly different paths were used to generate result sets and they need to
made comparable.
"""
import argparse
import os
import logging
import pprint
import sys
import yaml
from br_util import validateMappingFile

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

def main(args):
    parser = argparse.ArgumentParser()
    parser.add_argument('label_map_yml', type=argparse.FileType('r'), help='File to open, if \'-\' then use stdin')
    parser.add_argument('prefix_to_strip', help='Prefix to strip')
    parser.add_argument('output_label_map_yml', help='Output file')
    parser.add_argument("-l","--log-level",type=str, default="info",
      dest="log_level", choices=['debug','info','warning','error'])
    pargs = parser.parse_args(args)

    logLevel = getattr(logging, pargs.log_level.upper(),None)
    logging.basicConfig(level=logLevel)

    if os.path.exists(pargs.output_label_map_yml):
      logging.error('Refusing to overwrite {}'.format(pargs.output_label_map_yml))
      return 1

    logging.info('Loading correctness mapping')
    correctnessMapping = yaml.load(pargs.label_map_yml, Loader=Loader)
    validateMappingFile(correctnessMapping)
    logging.info('Finished loading correctness mapping')

    newCorrectnessMaping = { }
    for programName, data in correctnessMapping.items():
      if not programName.startswith(pargs.prefix_to_strip):
        logging.error('Path "{}" does not start with prefix {}'.format(programName, pargs.prefix_to_strip))
        return 1

      newProgramName = programName.replace(pargs.prefix_to_strip, '')
      if newProgramName in newCorrectnessMaping:
        logging.error('Error stripping prefix causes program name clash for {}'.format(programName))
        return 1
      
      newCorrectnessMaping[newProgramName] = data
      assert not 'original_progra' in data
      data['original_program'] = programName

    assert len(newCorrectnessMaping) == len(correctnessMapping)
    with open(pargs.output_label_map_yml, 'w') as f:
      yamlString = yaml.dump(newCorrectnessMaping, default_flow_style=False, Dumper=Dumper)
      f.write(yamlString)
    
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
