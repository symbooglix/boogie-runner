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
  parser.add_argument('first_yml', type=argparse.FileType('r'))
  parser.add_argument('second_yml', type=argparse.FileType('r'))
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  firstResults = yaml.load(pargs.first_yml, Loader=Loader)
  secondResults = yaml.load(pargs.second_yml, Loader=Loader)

  assert isinstance(firstResults, list)
  assert isinstance(secondResults, list)

  if len(firstResults) == 0:
    logging.error('First Result list is empty')
    return 1

  if len(secondResults) == 0:
    logging.error('Second Result list is empty')
    return 1

  print("# of results in first {}".format(len(firstResults)))
  print("# of results in second {}".format(len(secondResults)))

  # Create sets of used files
  programsInFirst = set()
  programsInSecond = set()
  for r in firstResults:
    programsInFirst.add(r['program'])
  for r in secondResults:
    programsInSecond.add(r['program'])

  resultMissingFromSecond= [ ]
  resultMissingFromFirst=[ ]
  # Check for files missing in second
  for r in firstResults:
    if not (r['program'] in programsInSecond):
      resultMissingFromSecond.append(r)
      logging.warning('Program {} is missing from second but present in first'.format(r['program']))
  # Check for files missing in first
  for r in secondResults:
    if not (r['program'] in programsInFirst):
      resultMissingFromFirst.append(r)
      logging.warning('Program {} is missing from first but present in second'.format(r['program']))

  print("# of programs missing from second but present in first: {}".format(len(resultMissingFromSecond)))
  print("# of programs missing from first but present in second: {}".format(len(resultMissingFromFirst)))
  print("")
  print("# Missing from second")
  for r in resultMissingFromSecond:
    print(r)
  print("# Missing from first")
  for r in resultMissingFromFirst:
    print(r)

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
