#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import os
import logging
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
  parser = argparse.ArgumentParser()
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument('result_yml', type=argparse.FileType('r'))
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  results = yaml.load(pargs.result_yml, Loader=Loader)

  assert isinstance(results, list)

  if len(results) == 0:
    logging.error('Result list is empty')
    return 1

  # Count
  fullExplore = [ ]
  bugFound = [ ]
  timedOut = [ ]
  hitBound = [ ]
  unknown = [ ]
  for r in results:
    rType = classifyResult(r)
    logging.debug('Classified {} as {}'.format(r['program'], rType))
    if rType == FinalResultType.FULLY_EXPLORED:
      fullExplore.append(r)
    elif rType == FinalResultType.BOUND_HIT:
      hitBound.append(r)
    elif rType == FinalResultType.BUG_FOUND:
      bugFound.append(r)
    elif rType == FinalResultType.TIMED_OUT:
      timedOut.append(r)
    else:
      unknown.append(r)

  print("Total: {}".format(len(results)))
  print("# of fully explored: {} ({:.2f}%)".format(len(fullExplore),
    100*float(len(fullExplore))/len(results)))
  print("# of bound hit: {} ({:.2f}%)".format(len(hitBound),
    100*float(len(hitBound))/len(results)))
  print("# of bug found: {} ({:.2f}%)".format(len(bugFound),
    100*float(len(bugFound))/len(results)))
  print("# of timeout: {} ({:2f}%)".format(len(timedOut),
    100*float(len(timedOut))/len(results)))
  print("# of unknown (crash/memout): {} ({:2f}%)".format(len(unknown),
    100*float(len(unknown))/len(results)))

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
