# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import logging
import os
from . import ProgramListLoader
from . import ConfigLoader
from . import RunnerFactory
import traceback
import yaml

_logger = None

def entryPoint(args):
  """
      Script to run a Boogie tool over boogie programs
  """
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="debug", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--rprefix", default=os.getcwd(), help="Prefix for relative paths for program_list")
  parser.add_argument("config_file", help="YAML configuration file")
  parser.add_argument("program_list", help="File containing list of Boogie programs")
  parser.add_argument("yaml_output", help="path to write YAML output to")

  pargs = parser.parse_args()

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  if logLevel == logging.DEBUG:
    logFormat = '%(levelname)s:%(filename)s:%(lineno)d %(funcName)s()  : %(message)s'
  else:
    logFormat = '%(levelname)s: %(message)s'

  logging.basicConfig(level=logLevel, format=logFormat)
  _logger = logging.getLogger(__name__)

  config = None
  programList = None
  try:
    _logger.debug('Loading configuration from "{}"'.format(pargs.config_file))
    config = ConfigLoader.load(pargs.config_file)
    _logger.debug('Loading program_list from "{}"'.format(pargs.program_list))
    programList = ProgramListLoader.load(pargs.program_list, pargs.rprefix)
  except (ProgramListLoader.ProgramListLoaderException, ConfigLoader.ConfigLoaderException) as e:
    _logger.error(e)
    logging.debug(traceback.format_exc())

    return 1

  if len(programList) < 1:
    logging.error('program_list cannot be empty')
    return 1

  yamlOutputFile = os.path.abspath(pargs.yaml_output)

  if os.path.exists(yamlOutputFile):
    _logger.error('yaml_output file ("{}") already exists'.format(yamlOutputFile))
    return 1

  # Get Runner class to use
  RunnerClass = RunnerFactory.getRunnerClass(config['runner'])

  if not 'runner_config' in config:
    _logger.error('"runner_config" missing from config')
    return 1

  if not isinstance(config['runner_config'],dict):
    _logger.error('"runner_config" should map to a dictionary')
    return 1

  rc = config['runner_config']

  # Create the runners
  runners = []
  for program in programList:
    # Pass in a copy of rc so that if a runner accidently modifies
    # a config it won't affect other runners.
    runners.append(RunnerClass(program, rc.copy()))

  # Run the runners and build the report
  report = []
  exitCode = 0
  for r in runners:
    try:
      r.run()
      report.append(r.getResults())
    except:
      _logger.error("Error handling:{}".format(r.program))
      _logger.error(traceback.format_exc())

      # Attempt to add the error to the report
      errorLog = {}
      errorLog['program'] = r.program
      errorLog['error'] = traceback.format_exc()
      report.append(errorLog)
      exitCode = 1

  # Write result to YAML file
  result = yaml.dump(report, default_flow_style=False)
  with open(yamlOutputFile, 'w') as f:
    f.write('# BoogieRunner report using runner {}\n'.format(config['runner']))
    f.write(result)

  return exitCode
