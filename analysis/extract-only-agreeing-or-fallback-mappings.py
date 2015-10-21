#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab tw=80 colorcolumn=80:
"""
This script takes a trusted mapping (i.e. results from trusted tools) and a
fallback (e.g. inferred from svcomp benchmark names) mapping and returns a
mapping where the only listed mappings are where both mappings agree on
the result or the trusted mapping does not know the result but the fallback
does.
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
  parser.add_argument("--disallow-only-fallback", default=False,
                      dest='disallow_only_fallback', action='store_true')
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
  useLabelCount = 0
  rejectLabelCount = 0
  for programName, trustedExpectedCorrect in [ (k, v['expected_correct']) for (k,v) in trustedMapping.items() ]:
    fallbackExpectedCorrect = fallbackMapping[programName]['expected_correct']
    finalExpectedCorrect = None
    fromInferred = None
    # There is an existing label
    if trustedExpectedCorrect == None:
      if fallbackExpectedCorrect == None:
        logging.info('REJECT: Both fallback and trusted are none for {}'.format(
          programName))
        rejectLabelCount +=1
        continue
      elif isinstance(fallbackExpectedCorrect, bool):
        if pargs.disallow_only_fallback:
          logging.info('REJECT: not using only fallback correctness for' +
                       '"{}"'.format(programName))
          rejectLabelCount += 1
          continue
        else:
          finalExpectedCorrect = fallbackExpectedCorrect
          logging.info('ACCEPT: Using fallback correctness of {} for "{}"'.format(
            fallbackExpectedCorrect, programName))
          fromInferred = False
          useLabelCount += 1
      else:
        raise Exception('Unreachable')
    else:
      assert isinstance(trustedExpectedCorrect, bool)
      if isinstance(fallbackExpectedCorrect, bool) and \
         not trustedExpectedCorrect == fallbackExpectedCorrect:
        logging.info('REJECT:There is conflict between fallback and trusted for "{}".'
        'Trusted: {}, Fallback: {}'.format(programName, trustedExpectedCorrect,
          fallbackExpectedCorrect))
        rejectLabelCount +=1
        continue
      else:
        # Both mappings agree so not really from inferred or fallback so set to
        # None
        finalExpectedCorrect = trustedExpectedCorrect
        fromInferred = None
        useLabelCount += 1
        assert trustedExpectedCorrect == fallbackExpectedCorrect
        logging.info('ACCEPT: trusted and fallback agree for' +
                     '{}'.format(programName))

    # Write the new mapping entry
    newMapping[programName] = {
      'expected_correct': finalExpectedCorrect,
      'from_inferred': fromInferred
    }

  assert len(trustedMapping) == useLabelCount + rejectLabelCount
  assert len(trustedMapping) >= len(newMapping)

  # Output new mapping
  with open(pargs.output_mapping_file, 'w') as f:
    yamlString = yaml.dump(newMapping, default_flow_style=False, Dumper=Dumper)
    f.write(yamlString)

  print("# of labels used: {} ({:.2f}%)".format(
    useLabelCount, 100*float(useLabelCount)/len(trustedMapping)))
  print("# of labels rejected: {} ({:.2f}%)".format(
    rejectLabelCount, 100*float(rejectLabelCount)/len(trustedMapping)))
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
