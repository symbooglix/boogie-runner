#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
    Script to run a Boogie tool on a single boogie program
"""
import argparse
import logging
import os
from  BoogieRunner import ConfigLoader
from  BoogieRunner import RunnerFactory
import traceback
import yaml
import sys

_logger = None

def entryPoint(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="debug", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--dry", action='store_true', help="Stop after initialising runners")
  parser.add_argument("config_file", help="YAML configuration file")
  parser.add_argument("boogie_program", help="Boogie program to pass to tool")
  parser.add_argument("working_dir", help="Working directory")
  parser.add_argument("yaml_output", help="path to write YAML output to")

  pargs = parser.parse_args()

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  if logLevel == logging.DEBUG:
    logFormat = '%(levelname)s:%(threadName)s: %(filename)s:%(lineno)d %(funcName)s()  : %(message)s'
  else:
    logFormat = '%(levelname)s:%(threadName)s: %(message)s'

  logging.basicConfig(level=logLevel, format=logFormat)
  _logger = logging.getLogger(__name__)

  # Compute absolute path to boogie program
  boogieProgram = os.path.abspath(pargs.boogie_program)
  if not os.path.exists(boogieProgram):
    _logger.error('Specified boogie program "{}" does not exist'.format(boogieProgram))
    return 1

  config = None
  try:
    _logger.debug('Loading configuration from "{}"'.format(pargs.config_file))
    config = ConfigLoader.load(pargs.config_file)
  except ConfigLoader.ConfigLoaderException as e:
    _logger.error(e)
    _logger.debug(traceback.format_exc())
    return 1

  yamlOutputFile = os.path.abspath(pargs.yaml_output)
  if os.path.exists(yamlOutputFile):
    _logger.error('yaml_output file ("{}") already exists'.format(yamlOutputFile))
    return 1

  # Setup the working directory
  workDir = os.path.abspath(pargs.working_dir)
  if os.path.exists(workDir):
    # Check it's a directory and it's empty
    if not os.path.isdir(workDir):
      _logger.error('"{}" exists but is not a directory'.format(workDir))
      return 1

    workDirRootContents = next(os.walk(workDir, topdown=True))
    if len(workDirRootContents[1]) > 0 or len(workDirRootContents[2]) > 0:
      _logger.error('"{}" is not empty ({},{})'.format(workDir,
        workDirRootContents[1], workDirRootContents[2]))
      return 1
  else:
    # Try to create the working directory
    try:
      os.mkdir(workDir)
    except Exception as e:
      _logger.error('Failed to create working_dirs_root "{}"'.format(workDirsRoot))
      _logger.error(e)
      _logger.debug(traceback.format_exc())
      return 1

  # Get Runner class to use
  RunnerClass = RunnerFactory.getRunnerClass(config['runner'])
  runner = RunnerClass(boogieProgram, workDir, config['runner_config'])

  if pargs.dry:
    _logger.info('Not running runner')
    return 0

  # Run the runner
  report = [ ]
  exitCode = 0
  try:
    runner.run()
    report.append(runner.getResults())
  except KeyboardInterrupt:
    _logger.error('Keyboard interrupt')
  except:
    _logger.error("Error handling:{}".format(runner.program))
    _logger.error(traceback.format_exc())

    # Attempt to add the error to the report
    errorLog = {}
    errorLog['program'] = runner.program
    errorLog['error'] = traceback.format_exc()
    report.append(errorLog)
    exitCode = 1

  # Write result to YAML file
  _logger.info('Writing output to {}'.format(yamlOutputFile))
  result = yaml.dump(report, default_flow_style=False)
  with open(yamlOutputFile, 'w') as f:
    f.write('# BoogieRunner report using runner {}\n'.format(config['runner']))
    f.write(result)

  return exitCode

if __name__ == '__main__':
  sys.exit(entryPoint(sys.argv[1:]))
