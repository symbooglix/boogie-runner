#!/usr/bin/env python
"""
Sort a result list by a particular top level key.
The key must have a total order (e.g. strings, ints, floats)
"""
import argparse
import os
import logging
import pprint
import sys
import yaml
from br_util import FinalResultType, classifyResult

# HACK
_brPath = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _brPath)
from BoogieRunner import ProgramListLoader

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

def main(args):
    resultTypes = [ r.name for r in list(FinalResultType)] # Get list of ResultTypes as strings
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('key', type=str)
    parser.add_argument('result_yml', type=argparse.FileType('r'), help='File to open, if \'-\' then use stdin')
    parser.add_argument('-r', '--reverse', default=False, action='store_true')
    pargs = parser.parse_args(args)

    logging.info('Loading YAML')
    results = yaml.load(pargs.result_yml, Loader=Loader)
    logging.info('Finished loading YAML')

    assert isinstance(results, list)
    assert len(results) > 0
    
    if not pargs.key in results[0]:
        logging.info('Results do not have the key "{}"'.format(pargs.key))
        return 1

    results.sort(key= lambda r: r[pargs.key], reverse=pargs.reverse)
    try:
        print(yaml.dump(results, default_flow_style=False, Dumper=Dumper))
    except BrokenPipeError as e:
        pass


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
