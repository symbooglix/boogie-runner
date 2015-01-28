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
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser()
  parser.add_argument('result_yml', type=argparse.FileType('r'), help='Input YAML file')
  parser.add_argument('fe_correct_yml', help='full explored correct output yaml path')
  parser.add_argument('fe_incorrect_yml', help='full explored incorrect output yaml path')
  parser.add_argument('fe_unknown_yml', help='full explored incorrect output yaml path')
  pargs = parser.parse_args(args)

  if os.path.exists(pargs.fe_correct_yml):
    logging.error('{} already exists'.format(pargs.fe_correct_yml))
    return 1
  if os.path.exists(pargs.fe_incorrect_yml):
    logging.error('{} already exists'.format(pargs.fe_incorrect_yml))
    return 1
  if os.path.exists(pargs.fe_unknown_yml):
    logging.error('{} already exists'.format(pargs.fe_unknown_yml))
    return 1

  logging.info('Loading YAML file')
  results = yaml.load(pargs.result_yml, Loader=Loader)
  logging.info('Loading complete')

  assert isinstance(results, list)

  fullyExploredCorrect = [ ]
  fullyExploredIncorrect = [ ]
  fullyExploredUnknown = [ ]
  for r in results:
    if not 'bug_found' in r:
      logging.error('Key "bug_found" not in result')
      return 1

    if not 'expected_correct' in r:
      logging.error('Key "expected_correct" not in result')
      return 1
    
    # Definition of "fully explored". If the tool used was unbounded then the boogie program was verified
    if r['bug_found'] == False and r['timeout_hit'] == False and r['failed'] == False:
      logging.info('Found result fully explored result: {}'.format(r['program']))

      # Use correctness label to group
      correct = r['expected_correct']
      if correct == True:
        fullyExploredCorrect.append(r)
      elif correct == False:
        fullyExploredIncorrect.append(r)
      else:
        fullyExploredUnknown.append(r)
      
  size = len(fullyExploredCorrect) + len(fullyExploredIncorrect) + len(fullyExploredUnknown)
  print("# of fully explored {}".format(size))
  print("# of fully explored, expected correct {}".format(len(fullyExploredCorrect)))
  print("# of fully explored, expected incorrect {}".format(len(fullyExploredIncorrect)))
  print("# of fully explored, expected unknown {}".format(len(fullyExploredUnknown)))

  writeFilteredResults(pargs.fe_correct_yml, fullyExploredCorrect, "correct")
  writeFilteredResults(pargs.fe_incorrect_yml, fullyExploredIncorrect, "incorrect")
  writeFilteredResults(pargs.fe_unknown_yml, fullyExploredUnknown, "unknown")

  return 0

def writeFilteredResults(fileName, listToUse, name):
  if fileName != None:
    if os.path.exists(fileName):
      logging.error('Refusing to overwrite {}'.format(fileName))
      sys.exit(1)

    if len(listToUse) == 0:
      logging.info('Result list is empty not writing')
      return

    with open(fileName, 'w') as f:
      logging.info('Writing "{}" results to file {}'.format(name, fileName))
      yamlString = yaml.dump(listToUse, Dumper=Dumper, default_flow_style=False)
      f.write(yamlString)

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
