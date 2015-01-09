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
  parser.add_argument("--dry", action='store_true', help="Stop after initialising runners")
  parser.add_argument("-j", "--jobs", type=int, default="1", help="Number of jobs to run in parallel (Default %(default)s)")
  parser.add_argument("config_file", help="YAML configuration file")
  parser.add_argument("program_list", help="File containing list of Boogie programs")
  parser.add_argument("working_dirs_root", help="Directory to create working directories inside")
  parser.add_argument("yaml_output", help="path to write YAML output to")

  pargs = parser.parse_args()

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  if logLevel == logging.DEBUG:
    logFormat = '%(levelname)s:%(threadName)s: %(filename)s:%(lineno)d %(funcName)s()  : %(message)s'
  else:
    logFormat = '%(levelname)s:%(threadName)s: %(message)s'

  logging.basicConfig(level=logLevel, format=logFormat)
  _logger = logging.getLogger(__name__)

  if pargs.jobs <= 0:
    _logger.error('jobs must be <= 0')
    return 1

  config = None
  programList = None
  try:
    _logger.debug('Loading configuration from "{}"'.format(pargs.config_file))
    config = ConfigLoader.load(pargs.config_file)
    _logger.debug('Loading program_list from "{}"'.format(pargs.program_list))
    programList = ProgramListLoader.load(pargs.program_list, pargs.rprefix)
  except (ProgramListLoader.ProgramListLoaderException, ConfigLoader.ConfigLoaderException) as e:
    _logger.error(e)
    _logger.debug(traceback.format_exc())

    return 1

  if len(programList) < 1:
    logging.error('program_list cannot be empty')
    return 1

  yamlOutputFile = os.path.abspath(pargs.yaml_output)

  if os.path.exists(yamlOutputFile):
    _logger.error('yaml_output file ("{}") already exists'.format(yamlOutputFile))
    return 1

  # Setup the directory to hold working directories
  workDirsRoot = os.path.abspath(pargs.working_dirs_root)
  if os.path.exists(workDirsRoot):
    # Check its a directory and its empty
    if not os.path.isdir(workDirsRoot):
      _logger.error('"{}" exists but is not a directory'.format(workDirsRoot))
      return 1

    workDirsRootContents = next(os.walk(workDirsRoot, topdown=True))
    if len(workDirsRootContents[1]) > 0 or len(workDirsRootContents[2]) > 0:
      _logger.error('"{}" is not empty ({},{})'.format(workDirsRoot,
        workDirsRootContents[1], workDirsRootContents[2]))
      return 1
  else:
    # Try to create the working directory
    try:
      os.mkdir(workDirsRoot)
    except Exception as e:
      _logger.error('Failed to create working_dirs_root "{}"'.format(workDirsRoot))
      _logger.error(e)
      _logger.debug(traceback.format_exc())
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
  for index, program in enumerate(programList):
    # Create working directory for this runner
    workDir = os.path.join(workDirsRoot, 'workdir-{}'.format(index))
    assert not os.path.exists(workDir)

    try:
      os.mkdir(workDir)
    except Exception as e:
      _logger.error('Failed to create working directory "{}"'.format(workDir))
      _logger.error(e)
      _logger.debug(traceback.format_exc())
      return 1

    # Pass in a copy of rc so that if a runner accidently modifies
    # a config it won't affect other runners.
    runners.append(RunnerClass(program, workDir, rc.copy()))

  # Run the runners and build the report
  report = []
  exitCode = 0

  if pargs.dry:
    _logger.info('Not running runners')
    return exitCode

  if pargs.jobs == 1:
    _logger.info('Running jobs sequentially')
    for r in runners:
      try:
        r.run()
        report.append(r.getResults())
      except KeyboardInterrupt:
        _logger.error('Keyboard interrupt')
        break
      except:
        _logger.error("Error handling:{}".format(r.program))
        _logger.error(traceback.format_exc())

        # Attempt to add the error to the report
        errorLog = {}
        errorLog['program'] = r.program
        errorLog['error'] = traceback.format_exc()
        report.append(errorLog)
        exitCode = 1
  else:
    _logger.info('Running jobs in parallel')
    import concurrent.futures
    try:
      with concurrent.futures.ThreadPoolExecutor(max_workers=pargs.jobs) as executor:
        futureToRunner = { executor.submit(r.run) : r for r in runners }
        for future in concurrent.futures.as_completed(futureToRunner):
          r = futureToRunner[future]
          _logger.debug('{} runner finished'.format(r.programPathArgument))

          if future.exception():
            e = future.exception()
            # Attempt to log the error report
            errorLog = {}
            errorLog['program'] = r.program
            errorLog['error'] = "\n".join(traceback.format_exception(type(e), e, None))
            _logger.error('{} runner hit exception:\n{}'.format(r.programPathArgument, errorLog['error']))
            report.append(errorLog)
          else:
            report.append(r.getResults())
    except KeyboardInterrupt:
      # The executor should of been cleaned terminated.
      # We'll then write what we can to the output YAML file
      _logger.error('Keyboard interrupt')

  # Write result to YAML file
  _logger.info('Writing output to {}'.format(yamlOutputFile))
  result = yaml.dump(report, default_flow_style=False)
  with open(yamlOutputFile, 'w') as f:
    f.write('# BoogieRunner report using runner {}\n'.format(config['runner']))
    f.write(result)

  return exitCode
