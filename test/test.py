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

# Hack
sys.path.insert(0, repoDir)
from BoogieRunner import ProgramListLoader
# Another Hack
sys.path.insert(0, os.path.join(repoDir, 'analysis'))
from br_util import FinalResultType, classifyResult

class RunnerTool:
  def __init__(self, configFile, listFile, relativePathPrefix, workDir, yamlOutput):
    self.configFile = configFile
    self.listLocation = listFile
    self.relativePathPrefix = relativePathPrefix
    self.workDir = workDir
    self.yamlOutput = yamlOutput
    assert os.path.exists(self.listLocation)

  def doCleanUp(self):
    shutil.rmtree(self.workDir)
    os.remove(self.yamlOutput)

  def getFileList(self):
    return ProgramListLoader.load(self.listLocation, self.relativePathPrefix)

class BatchRunnerTool(RunnerTool):
  def __init__(self, configFile, listFile, relativePathPrefix, workDir, yamlOutput):
    super(BatchRunnerTool, self).__init__(configFile, listFile, relativePathPrefix, workDir, yamlOutput)
    self.numJobs = 1

  def setNumJobs(self, count):
    assert count > 0
    self.numJobs = count

  def getResults(self, testFiles, clean=True):
    if os.path.exists(self.yamlOutput):
      os.remove(self.yamlOutput)

    exitCode = subprocess.call([self.tool,
                                "--jobs={}".format(self.numJobs),
                                self.configFile,
                                self.listLocation,
                                self.workDir,
                                self.yamlOutput
                               ])
    if exitCode != 0:
      logging.error('Tool failed')
      sys.exit(1)

    if not os.path.exists(self.yamlOutput):
      logging.error('cannot find yaml output')
      sys.exit(1)

    results = None
    with open(self.yamlOutput, 'r') as y:
      results = yaml.load(y)

    if clean:
      self.doCleanUp()
    return results

  @property
  def tool(self):
    return os.path.join(repoDir, 'boogie-batch-runner.py')

class SingleRunTool(RunnerTool):
  def getResults(self, testFiles, clean=False):
    logging.warning('clean directive ignored')
    # Run over the tests
    results = [ ]
    for testFile in testFiles.keys():
      exitCode = subprocess.call([self.tool,
                                  self.configFile,
                                  testFile,
                                  self.workDir,
                                  self.yamlOutput
                                 ])
      if exitCode != 0:
        logging.error('Tool failed')
        sys.exit(1)

      if not os.path.exists(self.yamlOutput):
        logging.error('Yaml output is missing')
        sys.exit(1)

      with open(self.yamlOutput, 'r') as f:
        results.extend(yaml.load(f))
      self.doCleanUp()
    return results

  @property
  def tool(self):
    return os.path.join(repoDir, 'boogie-runner.py')

def main(args):
  logging.basicConfig(level=logging.DEBUG)
  parser = argparse.ArgumentParser()
  parser.add_argument("-j", "--jobs", type=int, default=1,
                      help='jobs to run in parallel. Only works when using batch mode')
  parser.add_argument("-k", "--keep-files", dest='keep_files',
                      action='store_true', default=False)
  parser.add_argument("-l", "--list-file", dest='list_file',
                      type=str, default="simple_boogie_programs.txt")
  parser.add_argument("config_file")
  parser.add_argument("mode", choices=['single', 'batch'], help="Front end to use. Valid options %(choices)s")
  pargs = parser.parse_args(args)

  if pargs.mode != 'batch' and pargs.jobs > 1:
    logging.error('Can only specify jobs when using "batch" mode')
    return 1

  # Compute some paths
  workDir = os.path.join(testDir, 'working_dir')
  yamlOutput = os.path.join(testDir, 'result.yml')

  if not os.path.exists(pargs.config_file):
    logging.error('Could not find config_file {}'.format(pargs.config_file))
    return 1

  listFile = os.path.join(testDir, pargs.list_file)
  if not os.path.exists(listFile):
    logging.error('Could not find list file "{}".'.format(listFile))
    return 1

  if pargs.mode == 'single':
    runnerConstructor = SingleRunTool
  elif pargs.mode == 'batch':
    runnerConstructor = BatchRunnerTool
  else:
    logging.error('Invalid mode')
    return 1
  runner = runnerConstructor(pargs.config_file, listFile, testDir, workDir, yamlOutput)
  if pargs.jobs > 1:
    runner.setNumJobs(pargs.jobs)

  if not os.path.exists(runner.tool):
    logging.error('Cannot find {}'.format(runner.tool))
    return 1

  if os.path.exists(yamlOutput):
    logging.error('Yaml output file "{}" exists. Remove it'.format(yamlOutput))
    return 1

  # Find all the tests
  testFiles = {}
  filenames = runner.getFileList()
  for potentialTest in filenames:
    if not os.path.exists(potentialTest):
      logging.error('Could not find file "{}"'.format(potentialTest))
      return 1
    r = re.compile(r'^//\s*(\w+)')
    # Read expected test result from first line of file
    with open(potentialTest, 'r') as testFile:
      line = testFile.readline()

      m = r.match(line)
      if m == None:
        logging.error('Failed to find result on first line of file {}'.format(potentialTest))
        return 1

      expectedResultStr = m.group(1)

      expectedResultEnum = FinalResultType[expectedResultStr]

      logging.info('Found test:{} - {}'.format(potentialTest, expectedResultEnum))
      testFiles[potentialTest] = expectedResultEnum

  # Run tests
  if os.path.exists(workDir):
    logging.info('removing {}'.format(workDir))
    shutil.rmtree(workDir)

  os.mkdir(workDir)
  results = runner.getResults(testFiles, clean= not pargs.keep_files)

  # Check the results against the testFiles
  logging.info('Got results:\n{}'.format(pprint.pformat(results)))

  for result in results:
    filename = result['program']
    actualClassification =  classifyResult(result)
    expectedClassification = testFiles[filename]

    if actualClassification != expectedClassification:
      logging.error('Result mismatch for {}, expected {}, got {}'.format(
        filename, expectedClassification, actualClassification))
      return 1

  logging.info('SUCCESS!')
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
