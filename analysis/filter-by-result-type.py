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


def main(args):
    resultTypes = [ r.name for r in list(FinalResultType)] # Get list of ResultTypes as strings
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('result_yml', type=argparse.FileType('r'), help='File to open, if \'-\' then use stdin')
    parser.add_argument('result_type', choices=resultTypes, help='ResultType to match or filter out (depending on -n)')
    parser.add_argument('-n', '--not-matching', action='store_true', dest='not_matching', help='Change behaviour to output results that are not of type \'result_type\'')
    pargs = parser.parse_args(args)

    results = yaml.load(pargs.result_yml)

    assert isinstance(results, list)

    # Get out of requested type
    matchResulType = FinalResultType[pargs.result_type]
    collected = [ ]
    for r in results:
        rType = classifyResult(r)
        logging.debug('Classified {} as {}'.format(r['program'], rType))
        if pargs.not_matching:
            if rType != matchResulType:
                collected.append(r)
        else:
            if rType == matchResulType:
                collected.append(r)

    if pargs.not_matching:
        logging.info('Kept {} results'.format(len(collected)))
    else:
        logging.info('Count of type {} : {}'.format(pargs.result_type, len(collected)))

    logging.info('Filtered out {} results out of {}'.format(len(results) - len(collected), len(results)))

    print(yaml.dump(collected, default_flow_style=False))

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
