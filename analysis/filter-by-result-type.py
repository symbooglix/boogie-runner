#!/usr/bin/env python
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
    parser.add_argument('result_yml', type=argparse.FileType('r'), default='-')
    parser.add_argument('result_type', choices=resultTypes)
    pargs = parser.parse_args(args)

    results = yaml.load(pargs.result_yml)

    assert isinstance(results, list)

    # Get out of requested type
    resultCode = ResultType[pargs.result_type].value

    count = 0
    collected = [ ]
    for r in results:
        if r['result'] == resultCode:
            count += 1
            collected.append(r)

    logging.info('Count of type {} : {}'.format(pargs.result_type, count))

    print(yaml.dump(collected, default_flow_style=False))

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
