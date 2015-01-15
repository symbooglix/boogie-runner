#!/usr/bin/env python
"""
Filer a results file (as YAML) and
output a filtered YAML file.

By default only results of type 'result_type'
are outputted. If -n is used then this is inverted.
"""
import argparse
import os
import logging
import pprint
import sys
import yaml

# HACK
_file = os.path.abspath(__file__)
_dir = os.path.dirname(os.path.dirname(_file))
sys.path.insert(0, _dir)
from BoogieRunner.ResultType import ResultType

def main(args):
    resultTypes = [ r.name for r in list(ResultType)] # Get list of ResultTypes as strings
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('result_yml', type=argparse.FileType('r'), help='File to open, if \'-\' then use stdin')
    parser.add_argument('result_type', choices=resultTypes, help='ResultType to match or filter out (depending on -n)')
    parser.add_argument('-n', '--not-matching', action='store_true', dest='not_matching', help='Change behaviour to output results that are not of type \'result_type\'')
    pargs = parser.parse_args(args)

    results = yaml.load(pargs.result_yml)

    assert isinstance(results, list)

    # Get out of requested type
    resultCode = ResultType[pargs.result_type].value
    collected = [ ]
    for r in results:
        if pargs.not_matching:
            if r['result'] != resultCode:
                collected.append(r)
        else:
            if r['result'] == resultCode:
                collected.append(r)

    if pargs.not_matching:
        logging.info('Kept {} results'.format(len(collected)))
    else:
        logging.info('Count of type {} : {}'.format(pargs.result_type, len(collected)))

    logging.info('Filtered out {} results out of {}'.format(len(results) - len(collected), len(results)))

    print(yaml.dump(collected, default_flow_style=False))

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
