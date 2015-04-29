#!/usr/bin/env python
"""
Filer a results file (as YAML) and
output a filtered YAML file.

are outputted. If -n is used then this is inverted.
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
    parser.add_argument('result_yml', type=argparse.FileType('r'), help='File to open, if \'-\' then use stdin')
    parser.add_argument('-r', '--result-type', dest='result_type', choices=resultTypes, default=None, help='Filter by FinalResultType')
    parser.add_argument('--program-list', dest='program_list', default=None, type=str, help='Filter by the programs in the program list')
    parser.add_argument("--rprefix", default=os.getcwd(), help="Prefix for relative paths for program_list")
    parser.add_argument("--strip-prefix", default=None, dest='strip_prefix', help="Prefix to strip from loaded program list")
    parser.add_argument('-n', '--not-matching', action='store_true', dest='not_matching', help='Change behaviour to output results that are not of type \'result_type\'')
    pargs = parser.parse_args(args)

    if pargs.result_type == None and pargs.program_list == None:
        logging.error('No filter specified')
        return 1

    # Setup filter functions
    filters = [ ]
    if pargs.result_type != None:
        matchResultType = FinalResultType[pargs.result_type]
        filters.append( lambda r: classifyResult(r) == matchResultType)

    if pargs.program_list != None:
        logging.info('Loading program list {}'.format(pargs.program_list))
        if not os.path.exists(pargs.program_list):
            logging.error('{} does not exist'.format(pargs.program_list))
            return 1
        progList = ProgramListLoader.load(pargs.program_list, pargs.rprefix, existCheck=False)

        if pargs.strip_prefix:
            logging.info('Stripping with prefix "{}"'.format(pargs.strip_prefix))
            newProgList = []
            for p in progList:
                if not p.startswith(pargs.strip_prefix):
                    logging.error('Program "{}" does not start with prefix "{}"'.format(
                        p, pargs.strip_prefix))
                    return 1
                newProgList.append(p[len(pargs.strip_prefix):])
            progList = newProgList
        filters.append( lambda r: r['program'] in progList)

    def combinedFilters(result):
        for f in filters:
            keep = f(result)
            if keep == False:
                return False
        return True

    logging.info('Loading YAML')
    results = yaml.load(pargs.result_yml, Loader=Loader)
    logging.info('Finished loading YAML')

    assert isinstance(results, list)

    # Get out of requested type
    collected = None
    if pargs.not_matching:
        collected = list(filter(lambda r: not combinedFilters(r), results))
    else:
        collected = list(filter(combinedFilters, results))

    logging.info('Filtered out {} results out of {}'.format(len(results) - len(collected), len(results)))

    try:
        print(yaml.dump(collected, default_flow_style=False, Dumper=Dumper))
    except BrokenPipeError as e:
        pass


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
