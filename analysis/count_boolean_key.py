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
  parser.add_argument('bool_key', help='top level key of boolean type')
  parser.add_argument('result_yml', type=argparse.FileType('r'), help='Input YAML file')
  parser.add_argument('--write-true', dest='write_true', default=None, help='Write results that have bool_key set to true as a YAML file')
  parser.add_argument('--write-false', dest='write_false', default=None, help='Write results that have bool_key set to false as a YAML file')
  parser.add_argument('--write-none', dest='write_none', default=None, help='Write results that have bool_key set to null (None) as a YAML file')
  pargs = parser.parse_args(args)

  logging.info('Loading YAML file')
  results = yaml.load(pargs.result_yml, Loader=Loader)
  logging.info('Loading complete')

  assert isinstance(results, list)

  trueList = [ ]
  falseList = [ ]
  noneList = [ ]
  for r in results:
    if not pargs.bool_key in r:
      logging.error('Key {} not in result'.format(pargs.bool_key))
      return 1
    
    value = r[pargs.bool_key]
    if (not isinstance(value, bool)) and value != None:
      logging.error('Key {} does not map to boolean or None')
      return 1

    if value == True:
      trueList.append(r)
    elif value == False:
      falseList.append(r)
    elif value == None:
      noneList.append(r)
    else:
      logging.error('unreachable!')
      return 1
      
  # print results
  print("Total {} keys: {}".format(pargs.bool_key, len(trueList) + len(falseList) + len(noneList)))
  print("# of True: {}".format(len(trueList)))
  print("# of not True {} ({} false, {} None)".format( len(falseList) + len(noneList), len(falseList) , len(noneList)))

  writeFilteredResults(pargs.write_true, trueList, pargs.bool_key)
  writeFilteredResults(pargs.write_false, falseList, pargs.bool_key)
  writeFilteredResults(pargs.write_none, noneList, pargs.bool_key)


  return 0

def writeFilteredResults(fileName, listToUse, key):
  if fileName != None:
    if os.path.exists(fileName):
      logging.error('Refusing to overwrite {}'.format(fileName))
      sys.exit(1)

    if len(listToUse) == 0:
      logging.info('Result list is empty not writing')
      return

    with open(fileName, 'w') as f:
      logging.info('Writing results with "{}" key set to "{}" to file {}'.format(key, str(listToUse[0][key]) ,fileName))
      yamlString = yaml.dump(listToUse, Dumper=Dumper, default_flow_style=False)
      f.write(yamlString)


if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
