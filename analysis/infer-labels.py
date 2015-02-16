#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab tw=80 colorcolumn=80:
"""
This script takes sets of results and tries
to infer correctness labels based on the results. The
inferred results are written to a file describing the
inferred mapping.
"""
import argparse
import logging
import os
import pprint
import sys
import yaml
from br_util import FinalResultType, classifyResult

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

class LoadYAMLException(Exception):
  pass

def loadYAMLResultFile(filePath):
  if not os.path.exists(filePath):
    msg = '{} does not exist'.format(filePath)
    logging.error(msg)
    raise LoadYAMLException(msg)

  results = None
  with open(filePath, 'r') as f:
    results = yaml.load(f, Loader=Loader)

  return results

def LoadResultSets(filePaths):
  resultSets = { } # Confusingly these are actually lists, not sets
  for resultFile in filePaths:
    try:
      if resultFile in resultSets:
        logging.error('Cannot specify result file "{}" twice'.format(
          resultFile))
        sys.exit(1)

      logging.info('Loading {}'.format(resultFile))
      resultSets[resultFile] = loadYAMLResultFile(resultFile)
      assert isinstance(resultSets[resultFile], list)
    except LoadYAMLException as e:
      sys.exit(1)

  return resultSets

def findResultFromProgramNameInResultSet(resultList, programName):
  assert isinstance(resultList, list)
  assert isinstance(programName, str)
  for result in resultList:
    assert 'program' in result
    if result['program'] == programName:
      return result

  return None

def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--trust-only-fe', default=[], action='append',
    dest='ofe', help='Specify files (can specify repeatedly) where only the'
    ' FULLY_EXPLORED results are trusted')
  parser.add_argument('--trust-only-bf', action='append', default=[],
    dest='obf', help='Specify files (can specify repeatedly) where only the'
    'BUG_FOUND results are trusted')
  parser.add_argument('--trust-fe-and-bf', default=[], action='append',
    dest='fe_and_bf', help='Specify files (can specify repeatedly) where both'
    ' FULLY_EXPLORED and BUG_FOUND results are trusted')
  parser.add_argument('mapping_file', default=None,
    help='output file for mapping')
  pargs = parser.parse_args(args)

  logging.basicConfig(level=logging.DEBUG)

  if os.path.exists(pargs.mapping_file):
    logging.error('Refusing to overwrite {}'.format(pargs.mapping_file))
    return 1

  # Load ofe, obf and fe_and_bf results
  ofe = LoadResultSets(pargs.ofe)
  obf = LoadResultSets(pargs.obf)
  feAndBf = LoadResultSets(pargs.fe_and_bf)

  # Check that the same file is not in any of the groups
  toCheck = [ set(s.keys()) for s in [ ofe, obf, feAndBf] ]
  for i in range(0, len(toCheck)):
    for j in range(i+1, len(toCheck)):
      common = toCheck[i].intersection( toCheck[j] )
      if len(common) > 0:
        logging.error('Found the same file(s) in multiple groups: {}'.format(
          common))
        return 1

  # Build list of program names
  programNames = set()
  for category in ['ofe', 'obf', 'feAndBf']:
    resultDict = locals()[category]
    for resultList in resultDict.values():
      assert isinstance(resultList, list)
      for r in resultList:
        programNames.add( r['program'])

  # Build program to { 'obe: [], 'obf': [], 'feAndBf': [] } map
  programToDataMap = { }
  for programName in programNames:
    assert not programName in programToDataMap
    mapForProgram = programToDataMap[programName] = { }
    for category in ['ofe', 'obf', 'feAndBf']:
      mapForProgram[category] = listForProgramAndCategory = []

      resultDict = locals()[category]
      for fileName, resultList in resultDict.items():
        assert isinstance(fileName, str)
        assert isinstance(resultList, list)
        resultForProgram = findResultFromProgramNameInResultSet(resultList,
                                                                programName)
        if resultForProgram != None:
          listForProgramAndCategory.append(resultForProgram)
        else:
          logging.warning('Could not find {} in {}'.format(
            programName, fileName))

  # Infer correctness labelling
  fileToCorrectnessLabel = { }
  programsWithDisagreement = [ ]
  for programName in programToDataMap.keys():
    logging.debug('Inferring correctness of {}'.format(programName))

    correctnessLabel = None # None means unknown
    trustOnlyFullyExplored = programToDataMap[programName]['ofe']
    trustOnlyBugFound = programToDataMap[programName]['obf']
    trustFullyExploredAndBugFound = programToDataMap[programName]['feAndBf']

    # See if one or more result sets believe the program to be correct (i.e.
    # fully explored) Only do this for result sets we trust
    if has(trustOnlyFullyExplored, FinalResultType.FULLY_EXPLORED) or \
    has(trustFullyExploredAndBugFound, FinalResultType.FULLY_EXPLORED):
      # Look for disagreement (i.e. bug found) from any results that we trust
      if has(trustOnlyBugFound, FinalResultType.BUG_FOUND) or \
      has(trustFullyExploredAndBugFound, FinalResultType.BUG_FOUND):
        logging.warning('There is disagreement on the correctness of "{}".'
          ' Assuming unknown'.format(programName))
        programsWithDisagreement.append(programName)
      else:
        logging.info('"{}" inferred to be correct'.format(programName))
        correctnessLabel = True
    elif has(trustOnlyBugFound, FinalResultType.BUG_FOUND) or \
    has(trustFullyExploredAndBugFound, FinalResultType.BUG_FOUND):
      # A bug was found from a result set we trust (and no result we trust fully
      # explored the program) so we can infer that this program has a bug
      logging.info('"{}" inferred to be incorrect'.format(programName))
      correctnessLabel = False
    else:
      logging.info(
        'Could not infer correctness of "{}". Assuming unknown'.format(
          programName))

    fileToCorrectnessLabel[programName] = {'expected_correct': correctnessLabel}

  if len(programsWithDisagreement) > 0:
    logging.warning('There were one of more programs where results disagree')
    logging.warning('\n{}'.format(pprint.pformat(programsWithDisagreement)))

  # Output mapping file
  with open(pargs.mapping_file, 'w') as f:
    f.write('# Inferred correctness mapping\n')
    yamlText = yaml.dump(fileToCorrectnessLabel,
                         default_flow_style=False,
                         Dumper=Dumper)
    f.write(yamlText)


def has(resultList, desiredResultType):
  assert isinstance(resultList, list)
  assert isinstance(desiredResultType, FinalResultType)
  for r in resultList:
    resultType = classifyResult(r)

    if resultType == desiredResultType:
      return True

  return False


  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
