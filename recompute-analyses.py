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
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("-s", "--search-workdir-regex", default="", dest="search_workdir_regex", help="Substitue workdir matching this regex")
  parser.add_argument("-r", "--replace-workdir-regex", default="", dest="replace_workdir_regex", help="replace matched workdir with this (can use backrefs)")
  parser.add_argument("--allow-new-fields-only", default=False, dest="allow_new_fields_only", action='store_true',
                      help="When getting new results from the analyser only allow new fields to be added")
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
    if logLevel == logging.DEBUG:
      raise e
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

    # Handle the case of error reports being in result list (generated on boogie-batch-runner being terminated)
    if ('log_file' not in r) and ('error' in r) and ('program' in r):
      _logger.warning(('Found error report in results for program "{}",' +
                      ' copying result over without processing').format(r['program']))
      newResults.append(r)
      continue
    logFileName = os.path.basename(r['log_file'])
    logFileDir = os.path.dirname(r['log_file'])
    logFileDir = getWorkingDirectory(logFileDir,
                                     pargs.search_workdir_regex,
                                     pargs.replace_workdir_regex)

    patchedLogFilePath = os.path.join(logFileDir, logFileName)
    if not os.path.exists(patchedLogFilePath):
      _logger.error('Could not find log file {}'.format(patchedLogFilePath))
      return 1

    originalLogFilePath = r['log_file']
    # Patch for the analyser
    r['log_file'] = patchedLogFilePath

    # Create analyser and reanalyse result
    analyser = analyserClass(r)
    newResult = analyser.getAnalysesDict()

    # Undo the patch the log file path
    assert 'log_file' in newResult
    newResult['log_file'] = originalLogFilePath

    # Merge the old and new results
    mergedResult = merge(r, newResult, logFileDir, pargs.allow_new_fields_only)
    newResults.append(mergedResult)

  # Write result to file
  _logger.info('Writing updated results to {}'.format(outputPath))
  with open(outputPath, 'w') as f:
    f.write('# Updated results using analyser {}\n'.format(str(analyser)))
    f.write(yaml.dump(newResults, default_flow_style=False))

  return 0

def merge(oldResult, updatedAnalyses, workingDirectory, allowNewFieldsOnly):
  _logger.info('Merging {}'.format(oldResult['program']))
  newResult = oldResult.copy()

  for k,v in updatedAnalyses.items():
    _logger.debug('Updating with {}:{}'.format(k,v))
    newResult[k] = v

  # Compute new or changed fields
  newOrChanged = set(newResult.items()) - set(oldResult.items())

  for k, v in newOrChanged:
    if k in oldResult:
      _logger.warning('[{}] Key {} changed "{}" => "{}"'.format(workingDirectory, k, oldResult[k], v))
      if allowNewFieldsOnly:
        _logger.error('Changing field values disallowed by --allow-new-fields-only')
        sys.exit(1)
    else:
      _logger.info('[{}] New key added {}: "{}"'.format(workingDirectory, k, v))

  return newResult

def getWorkingDirectory(originalworkDir, searchRegex, replaceRegex):
  assert isinstance(originalworkDir, str)
  assert isinstance(searchRegex, str)
  assert isinstance(replaceRegex, str)

  if len(searchRegex) == 0 or len(replaceRegex) == 0:
    # Don't use regexes to change the working directory specified
    return originalworkDir

  r = re.compile(searchRegex)
  newWorkDir = r.sub(replaceRegex, originalworkDir, count=1)
  return newWorkDir


if __name__ == '__main__':
  sys.exit(entryPoint(sys.argv[1:]))
