#!/usr/bin/env python
import argparse
import os
import logging
import sys
import yaml

# HACK
_file = os.path.abspath(__file__)
_dir = os.path.dirname(os.path.dirname(_file))
sys.path.insert(0, _dir)
from BoogieRunner.ResultType import ResultType

def main(args):
    logging.basicConfig(level=logging.DEBUG)
    parser = argparse.ArgumentParser()
    parser.add_argument('result_yml', type=argparse.FileType('r'))
    pargs = parser.parse_args(args)

    results = yaml.load(pargs.result_yml)

    assert isinstance(results, list)

    # Count
    binned = {}
    for r in results:
        resultCode = ResultType(r['result'])
        try:
            count = binned[resultCode]
            binned[resultCode] = count +1
        except KeyError:
            binned[resultCode] = 1

    # print results
    total = 0
    for rType, count in binned.items():
        print("{type} : {count}".format(type=rType, count=count))
        total += count
    print("Total benchmarks : {}".format(total))

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
