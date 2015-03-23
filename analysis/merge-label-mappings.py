#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab tw=80 colorcolumn=80:
"""
This script takes a correctness mapping file
and applies it to the provide results YAML file
"""
import argparse
import logging
import os
import pprint
import sys
import yaml
from br_util import validateMappingFile, ValidateMappingFileException

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('trusted_mapping_file', type=argparse.FileType('r'),
    help="mapping file to trust (used if correctness is not unknown)")
  parser.add_argument('fallback_mapping_file', type=argparse.FileType('r'),
    help="Mapping file to use if there are unknown results in the trusted"
    " mapping file")
  parser.add_argument('output_mapping_file', help="Output mapping file")
  parser.add_argument("-l","--log-level",type=str, default="info",
    dest="log_level", choices=['debug','info','warning','error'])
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if os.path.exists(pargs.output_mapping_file):
    logging.error('Refusing to overwrite "{}"'.format(pargs.output_mapping_file))
    return 1

  try:
    logging.info('Loading trusted mapping...')
    trustedMapping = yaml.load(pargs.trusted_mapping_file, Loader=Loader)
    validateMappingFile(trustedMapping)
  except ValidateMappingFileException:
    logging.error('Failed to load trusted mapping')
    return 1

  try:
    logging.info('Loading fallback mapping...')
    fallbackMapping = yaml.load(pargs.fallback_mapping_file, Loader=Loader)
    validateMappingFile(fallbackMapping)
  except ValidateMappingFileException:
    logging.error('Failed to load fallback mapping')
    return 1

  assert len(trustedMapping) == len(fallbackMapping)

  newMapping = { }
  useTrustedLabelCount = 0
  useFallbackLabelCount = 0
  trustedFallbackMismatchCount = 0
  for programName, expectedCorrect in [ (k, v['expected_correct']) for (k,v) in trustedMapping.items() ]:
    fallbackExpectedCorrect = fallbackMapping[programName]['expected_correct']
    finalExpectedCorrect = None
    fromInferred = None
    # There is an existing label
    if expectedCorrect == None:
      if fallbackExpectedCorrect == None:
        logging.info('Both fallback and trusted are none for {}'.format(
          programName))
        useTrustedLabelCount += 1
        fromInferred = True
      elif isinstance(fallbackExpectedCorrect, bool):
        finalExpectedCorrect = fallbackExpectedCorrect
        logging.info('Using fallback correctness of {} for "{}"'.format(
          fallbackExpectedCorrect, programName))
        useFallbackLabelCount += 1
        fromInferred = False
      else:
        raise Exception('Unreachable')
    else:
      assert isinstance(expectedCorrect, bool)
      if isinstance(fallbackExpectedCorrect, bool) and \
         not expectedCorrect == fallbackExpectedCorrect:
        logging.warning('There is conflict between fallback and trusted for "{}".'
        'Trusted: {}, Fallback: {}'.format(programName, expectedCorrect,
          fallbackExpectedCorrect))
        trustedFallbackMismatchCount += 1

      useTrustedLabelCount += 1
      finalExpectedCorrect = expectedCorrect
      fromInferred = True

    # Write the new mapping entry
    newMapping[programName] = {
      'expected_correct': finalExpectedCorrect,
      'from_inferred': fromInferred
    }

  assert len(trustedMapping) == useTrustedLabelCount + useFallbackLabelCount
  assert len(trustedMapping) == len(newMapping)

  # Output new mapping
  with open(pargs.output_mapping_file, 'w') as f:
    yamlString = yaml.dump(newMapping, default_flow_style=False, Dumper=Dumper)
    f.write(yamlString)

  print("# of trusted labels used: {} ({:.2f}%)".format(
    useTrustedLabelCount, 100*float(useTrustedLabelCount)/len(trustedMapping)))
  print("# of fallback labels used: {} ({:.2f}%)".format(
    useFallbackLabelCount, 100*float(useFallbackLabelCount)/len(trustedMapping)))
  print("# of mistmatches between trusted (when not unknown) and fall back"
        ": {} ({:.2f}%)".format(trustedFallbackMismatchCount,
        100*float(trustedFallbackMismatchCount)/len(trustedMapping)))
  print("# of labels: {}".format(len(trustedMapping)))
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
