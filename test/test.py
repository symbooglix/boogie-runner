#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import logging
import os
import pprint
import re
import shutil
import subprocess
import sys
import yaml

testDir = os.path.dirname(os.path.abspath(__file__))
repoDir = os.path.dirname(testDir)
workDir = os.path.join(testDir, 'working_dir')
yamlOutput = os.path.join(testDir, 'result.yml')
# Hack
sys.path.insert(0, repoDir)
from BoogieRunner.ResultType import ResultType
from BoogieRunner import ProgramListLoader

class BatchRunnerTool:
  def __init__(self, configFile):
    self.listLocation = os.path.join(testDir, 'list.txt')
    self.configFile = configFile

  def getFileList(self):
    return ProgramListLoader.load(self.listLocation, testDir)

  def getResults(self, testFiles):
    if os.path.exists(yamlOutput):
      os.remove(yamlOutput)

    exitCode = subprocess.call([self.tool,
                                self.configFile,
                                self.listLocation,
                                workDir,
                                yamlOutput
                               ])
    if exitCode != 0:
      logging.error('Tool failed')
      sys.exit(1)

    if not os.path.exists(yamlOutput):
      logging.error('cannot find yaml output')
      sys.exit(1)

    with open(yamlOutput, 'r') as y:
      return yaml.load(y)

  @property
  def tool(self):
    return os.path.join(repoDir, 'boogie-batch-runner.py')

class SingleRunTool:
  def __init__(self, configFile):
    self.configFile = configFile

  def getFileList(self):
    _, _, filenames = next(os.walk(testDir, topdown=True))
    return [ f for f in filenames if f.endswith('.bpl')]

  def getResults(self, testFiles):
    
    # Run over the tests
    results = [ ]
    for testFile in testFiles.keys():
      exitCode = subprocess.call([self.tool,
                                  self.configFile,
                                  testFile,
                                  workDir,
                                  yamlOutput
                                 ])
      if exitCode != 0:
        logging.error('Tool failed')
        sys.exit(1)

      if not os.path.exists(yamlOutput):
        logging.error('Yaml output is missing')
        sys.exit(1)

      with open(yamlOutput, 'r') as f:
        results.extend(yaml.load(f))

      shutil.rmtree(workDir)
      os.remove(yamlOutput)

    return results

  @property
  def tool(self):
    return os.path.join(repoDir, 'boogie-runner.py')

def main(args):
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser()
  parser.add_argument("config_file")
  parser.add_argument("mode", choices=['single', 'batch'], help="Front end to use. Valid options %(choices)s")
  pargs = parser.parse_args(args)

  if not os.path.exists(pargs.config_file):
    logging.error('Could not find config_file {}'.format(pargs.config_file))
    return 1

  if pargs.mode == 'single':
    runner = SingleRunTool(pargs.config_file)
  elif pargs.mode == 'batch':
    runner = BatchRunnerTool(pargs.config_file)
  else:
    logging.error('Invalid mode')
    return 1

  if not os.path.exists(runner.tool):
    logging.error('Cannot find {}'.format(runner.tool))
    return 1

  if os.path.exists(yamlOutput):
    logging.error('Yaml output file "{}" exists. Remove it'.format(yamlOutput))
    return 1

  # Find all the tests
  testFiles = {}
  filenames = runner.getFileList()
  for potentialTest in [os.path.basename(f) for f in filenames]:

    r = re.compile(r'^//\s*(\w+)')
    # Read expected test result from first line of file
    with open(os.path.join(testDir, potentialTest), 'r') as testFile:
      line = testFile.readline()

      m = r.match(line)
      if m == None:
        logging.error('Failed to find result on first line of file {}'.format(potentialTest))
        return 1

      expectedResultStr = m.group(1)

      expectedResultEnum = ResultType[expectedResultStr]

      logging.info('Found test:{} - {}'.format(potentialTest, expectedResultEnum))
      testFiles[potentialTest] = expectedResultEnum

  # Run tests
  if os.path.exists(workDir):
    logging.info('removing {}'.format(workDir))
    shutil.rmtree(workDir)

  os.mkdir(workDir)
  results = runner.getResults(testFiles)

  # Check the results against the testFiles
  logging.info('Got results:\n{}'.format(pprint.pformat(results)))

  for result in results:
    filename = os.path.basename(result['program'])
    actualResult = ResultType(result['result'])
    expectedResult = testFiles[filename]

    if actualResult != expectedResult:
      logging.error('Result mismatch for {}, expected {}, got {}'.format(
        filename, expectedResult, actualResult))
      return 1

  logging.info('SUCCESS!')
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
