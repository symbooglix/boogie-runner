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

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

class ValidateMappingFileException(Exception):
  pass

def validateMappingFile(mapping):
  if not isinstance(mapping, dict):
    raise ValidateMappingFileException("Top level datastructure must be"
      " dictionary")

  for key, value in mapping.items():
    if not isinstance(key, str):
      raise ValidateMappingFileException("Top level keys must be strings")

    if not isinstance(value, dict):
      raise ValidateMappingFileException("Top level key must map to dictionary")

    if not 'expected_correct' in value:
      raise ValidateMappingFileException("{}'s dict is missing"
      "'expected_correct' key".format(key))

    if not isinstance(value['expected_correct'], bool) and \
    value['expected_correct'] != None:
      raise ValidateMappingFileException("{}'s dict does not map"
        "'expected_correct' map to bool".format(key))



def main(args):
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('mapping_file', type=argparse.FileType('r'),
    help="mapping file to apply")
  parser.add_argument('input_result_yml', type=argparse.FileType('r'),
    help="Input result YAML file")
  parser.add_argument('output_result_yml', help="Output result YAML file")
  parser.add_argument('--ignore-existing-labels', dest='ignore_existing_labels',
    default=False, action='store_true',
    help="Ignore existing correctness labels")
  pargs = parser.parse_args(args)

  if os.path.exists(pargs.output_result_yml):
    logging.error('Refusing to overwrite "{}"'.format(pargs.output_result_yml))
    return 1

  mapping = yaml.load(pargs.mapping_file, Loader=Loader)
  validateMappingFile(mapping)

  logging.info('Loading input results YAML file')
  results = yaml.load(pargs.input_result_yml, Loader=Loader)

  for r in results:
    assert 'program' in r
    programName = r['program']
    if not programName in mapping:
      logging.error('"{}" is missing from mapping file'.format(programName))
      return 1

    newLabel = mapping[programName]['expected_correct']

    existingLabel = None
    hasExistingLabel = False
    if 'expected_correct' in r:
      hasExistingLabel = True
      existingLabel = r['expected_correct']
      logging.debug('"{}" has an existing correctness label of {}'.format(
        programName, existingLabel))

    if pargs.ignore_existing_labels or not hasExistingLabel:
      r['expected_correct'] = newLabel
    else:
      assert hasExistingLabel
      # There is an existing label
      if isinstance(existingLabel, bool):
        if newLabel == None:
          # A label of None (i.e. unknown) from the mapping file is less useful
          # than the existing label which is (correct/incorrect). The rationale
          # here is we may have existing labels and the mapping probably comes
          # from inferred labels. If nothing could be inferred then we should
          # use the existing labels because that is our best guess
          logging.warning('Not using unknown correctness label from mapping'
            ' file to overwrite the existing correctness "{}"'.format(
            existingLabel))
        elif newLabel == existingLabel:
          logging.debug('Label from mapping file and existing match.')
          # No need to do anything
        else:
          logging.warning('Mapping file label ({}) and existing label ({}) '
            'do not match. Using label from mapping file'.format(
            newLabel, existingLabel))
          r['expected_correct'] = newLabel
      else:
        assert existingLabel == None
        if newLabel != None:
          logging.warning('Existing label for {} is {}. Using mapping file'
            'label {}'.format(programName, existingLabel, newLabel))
          r['expected_correct'] = newLabel
        else:
          assert newLabel == None

  # Output modified results
  with open(pargs.output_result_yml, 'w') as f:
    yamlString = yaml.dump(results, default_flow_style=False, Dumper=Dumper)
    f.write(yamlString)
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
