#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import os
import logging
import sys
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

def main(args):
  parser = argparse.ArgumentParser()
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument('map_yml', type=argparse.FileType('r'))
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  correctnessMapping = yaml.load(pargs.map_yml, Loader=Loader)
  validateMappingFile(correctnessMapping)

  # Count
  correct = []
  incorrect = []
  unknown = []
  for (programName, correctness) in [ (k, v['expected_correct']) for (k,v) in correctnessMapping.items()]:
    if correctness == True:
      correct.append(programName)
    elif correctness == False:
      incorrect.append(programName)
    elif correctness == None:
      unknown.append(programName)
    else:
      raise Exception('Unreachable')

  print("Total: {}".format(len(correctnessMapping)))
  print("# of correct: {} ({:.2f}%)".format(len(correct),
    100*float(len(correct))/len(correctnessMapping)))
  print("# of incorrect: {} ({:.2f}%)".format(len(incorrect),
    100*float(len(incorrect))/len(correctnessMapping)))
  print("# of unknown: {} ({:.2f}%)".format(len(unknown),
    100*float(len(unknown))/len(correctnessMapping)))

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
