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
  parser.add_argument('output_yml', help='output yaml path')
  parser.add_argument('--use-expected-correct', dest='use_expected_correct', action='store_true')
  pargs = parser.parse_args(args)

  if os.path.exists(pargs.output_yml):
    logging.error('{} already exists'.format(pargs.output_yml))
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
    
    # Definition of "fully explored". If the tool used was unbounded then the boogie program was verified
    if r['bug_found'] == False and r['timeout_hit'] == False and r['failed'] == False:
      logging.info('Found result fully explored result: {}'.format(r['program']))

      if 'expected_correct' in r and pargs.use_expected_correct:
        # Use correctness label to group
        correct = r['expected_correct']
        if correct == True:
          fullyExploredCorrect.append(r)
        elif correct == False:
          fullyExploredIncorrect.append(r)
        else:
          fullyExploredUnknown.append(r)
      else:
        fullyExploredUnknown.append(r)
      
  size = len(fullyExploredCorrect) + len(fullyExploredIncorrect) + len(fullyExploredUnknown)
  if pargs.use_expected_correct:
    print("# of fully explored {}".format(size))
    print("# of fully explored, correct {}".format(len(fullyExploredCorrect)))
    print("# of fully explored, incorrect {}".format(len(fullyExploredIncorrect)))
    print("# of fully explored, unknown {}".format(len(fullyExploredUnknown)))
  else:
    print("# of fully explored {}".format(size))
    if not pargs.use_expected_correct:
      with open(pargs.output_yml, 'w') as f:
        logging.info('Writing results with consider as fullyExplored to {}'.format(pargs.output_yml))
        yamlString = yaml.dump(fullyExploredUnknown, Dumper=Dumper, default_flow_style=False)
        f.write(yamlString)

  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
