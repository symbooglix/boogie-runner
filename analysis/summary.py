#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import os
import logging
import sys
import yaml

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
    fileName = os.path.basename(r['program'])
    if r['bug_found'] == False and r['timeout_hit'] == False and r['failed'] == False:
      # might be fully explored
      if 'recursion_bound_hit' in r and r['recursion_bound_hit'] == True:
        # Corral run hit recursion bound
        hitBound.append(r)
        logging.debug('Classified {} as hit bound'.format(fileName))
      else:
        fullExplore.append(r)
        logging.debug('Classified {} as fully explored'.format(fileName))
    elif r['bug_found'] == True:
      assert r['failed'] != True
      assert r['timeout_hit'] != True
      bugFound.append(r)
      logging.debug('Classified {} as bug found'.format(fileName))
    elif r['timeout_hit'] == True and (r['failed'] == False or r['failed'] == None):
      assert r['failed'] != None
      logging.debug('Classified {} as timeout'.format(fileName))
      timedOut.append(r)
    else:
      assert r['failed'] == True
      unknown.append(r)
      logging.debug('Classified {} as unknown'.format(fileName))

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
