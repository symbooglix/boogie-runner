#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
  Script to recompute analyses on existing results
"""
import argparse
import logging
import os
from  BoogieRunner import AnalyserFactory
import traceback
import re
import yaml
import sys

_logger = None

def entryPoint(args):
  global _logger
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="debug", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--fake-use-docker", dest="useDocker", default=False, action='store_true', help='pretend docker was used')
  parser.add_argument("-s", "--search-workdir-regex", default="", dest="search_workdir_regex", help="Substitue workdir matching this regex")
  parser.add_argument("-r", "--replace-workdir-regex", default="", dest="replace_workdir_regex", help="replace matched workdir with this (can use backrefs)")
  parser.add_argument("analyser", help="Analyser name (e.g. Boogaloo)")
  parser.add_argument("yaml_old_results")
  parser.add_argument("yaml_output")

  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  if logLevel == logging.DEBUG:
    logFormat = '%(levelname)s:%(threadName)s: %(filename)s:%(lineno)d %(funcName)s()  : %(message)s'
  else:
    logFormat = '%(levelname)s:%(threadName)s: %(message)s'
  logging.basicConfig(level=logLevel, format=logFormat)

  _logger = logging.getLogger(__name__)

  # Compute absolute paths
  oldResultsPath = os.path.abspath(pargs.yaml_old_results)
  outputPath = os.path.abspath(pargs.yaml_output)

  if not os.path.exists(oldResultsPath):
    _logger.error('Old results file "{}" does not exist'.format(oldResultsPath))
    return 1

  if os.path.exists(outputPath):
    _logger.error('{} already exists'.format(outputPath))
    return 1

  if oldResultsPath == outputPath:
    _logger.error('Input file cannot be same as output')
    return 1

  # Try to get the analyser class
  try:
    analyserClass = AnalyserFactory.getAnalyserClass(pargs.analyser)
  except Exception as e:
    _logger.error('Failed to load analyser {}'.format(pargs.analyser))
    return 1

  # Try to load old results in
  oldResults = None
  with open(oldResultsPath, 'r') as f:
    oldResults = yaml.load(f)

  if not isinstance(oldResults, list):
    _logger.error('Expected top level data structure to be list in {}'.format(oldResultsPath))
    return 1

  _logger.info('Loaded {} results'.format(len(oldResults)))

  newResults = [ ]
  # Iterate over the results
  for index, r in enumerate(oldResults):
    assert isinstance(r, dict)

    # Extract the keys we need to initialise the analyser
    exitCode = None
    hitHardTimeout = None
    workingDirectory = None

    try:
      exitCode = r['exit_code']
    except KeyError:
      _logger.error('exit_code key is missing from input file at index {}'.format(index))
      return 1

    # hit_hard_timeout is only implemented by some runners
    try:
      hitHardTimeout = r['hit_hard_timeout']
    except KeyError:
      pass

    # Find the log file
    try:
      workingDirectory = r['working_directory']
    except KeyError:
      _logger.error('working_directory key is missing from input file at index {}'.format(index))
      return 1

    # FIXME: There should be a better way to do this
    # Guess where it is
    logFilePath = getLogFilePath(workingDirectory, pargs.search_workdir_regex, pargs.replace_workdir_regex, 'log.txt')

    if not os.path.exists(logFilePath):
      _logger.error('Could not find log file {}'.format(logFilePath))
      return 1

    # Create analyser and reanalyse result
    analyser = analyserClass(exitCode=exitCode, logFile=logFilePath, useDocker=pargs.useDocker, hitHardTimeout=hitHardTimeout)
    updatedAnalyses = analyser.getAnalysesDict()

    # Merge the old and new results
    mergedResult = merge(r, updatedAnalyses)
    newResults.append(mergedResult)

  # Write result to file
  _logger.info('Writing updated results to {}'.format(outputPath))
  with open(outputPath, 'w') as f:
    f.write('# Updated results using analyser {}\n'.format(str(analyser)))
    f.write(yaml.dump(newResults, default_flow_style=False))

  return 0

def merge(oldResult, updatedAnalyses):
  _logger.info('Merging {}'.format(oldResult['program']))
  newResult = oldResult.copy()

  for k,v in updatedAnalyses.items():
    _logger.debug('Updating with {}:{}'.format(k,v))
    newResult[k] = v

  # Compute new or changed fields
  newOrChanged = set(newResult.items()) - set(oldResult.items())

  for k, v in newOrChanged:
    if k in oldResult:
      _logger.warning('Key {} changed "{}" => "{}"'.format(k, oldResult[k], v))
    else:
      _logger.warning('New key added {}: "{}"'.format(k, v))

  return newResult

def getLogFilePath(originalworkDir, searchRegex, replaceRegex, logFileName):
  assert isinstance(originalworkDir, str)
  assert isinstance(searchRegex, str)
  assert isinstance(replaceRegex, str)
  assert isinstance(logFileName, str)

  if len(searchRegex) == 0 or len(replaceRegex) == 0:
    # Don't use regexes to change the working directory specified
    return os.path.join(originalworkDir, logFileName)

  r = re.compile(searchRegex)
  newWorkDir = r.sub(replaceRegex, originalworkDir, count=1)
  return os.path.join(newWorkDir, logFileName)


if __name__ == '__main__':
  sys.exit(entryPoint(sys.argv[1:]))
