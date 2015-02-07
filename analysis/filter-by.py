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
    parser.add_argument('-c', '--correctness-label', dest='correctness_label', choices=['true', 'false'], default=None,
                        help='Filter by "expected_correct" label')
    parser.add_argument('-n', '--not-matching', action='store_true', dest='not_matching', help='Change behaviour to output results that are not of type \'result_type\'')
    pargs = parser.parse_args(args)

    if pargs.result_type == None and pargs.correctness_label == None:
        logging.error('No filter specified')
        return 1

    # Setup filter functions
    filters = [ ]
    if pargs.result_type != None:
        matchResulType = FinalResultType[pargs.result_type]
        filters.append( lambda r: classifyResult(r) == matchResulType)

    if pargs.correctness_label != None:
        matchCorrect = True if pargs.correctness_label == 'true' else False
        filters.append( lambda r: r['expected_correct'] == matchCorrect )

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
    matchResulType = FinalResultType[pargs.result_type]
    collected = None
    if pargs.not_matching:
        collected = list(filter(lambda r: not combinedFilters(r), results))
    else:
        collected = list(filter(combinedFilters, results))

    logging.info('Filtered out {} results out of {}'.format(len(results) - len(collected), len(results)))

    print(yaml.dump(collected, default_flow_style=False, Dumper=Dumper))

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
