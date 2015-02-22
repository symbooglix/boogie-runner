#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
    Script to run a Symbooglix's AxiomAndEntryRequiresCheckTransformPass
    pass on a set of boogie programs (from a program List) in preparation
    for running a smoke test to check that all the assumptions leading to
    an entry point are satisfiable.
"""
import argparse
import logging
import multiprocessing
import os
import pprint
from  BoogieRunner import ProgramListLoader
from BoogieRunner import EntryPointFinder
import traceback
import yaml
import signal
import sys
import subprocess

_logger = None
futureToRunner = None

def handleInterrupt(signum, frame):
  logging.info('Received signal {}'.format(signum))
  if futureToRunner != None:
    cancel(futureToRunner)

def entryPoint(args):
  global _logger, futureToRunner
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--rprefix", default=os.getcwd(), help="Prefix for relative paths for program_list")
  parser.add_argument("-j", "--jobs", default=multiprocessing.cpu_count(), type=int, help="jobs to run in parallel")
  parser.add_argument("input_program_list", help="File containing list of Boogie programs")
  parser.add_argument("output_dir", help="Directory to create working transformed programs in")
  parser.add_argument("output_program_list")

  parser.add_argument("--spr-path", dest='spr_path', required=True, help="Path to Symbooglix pass runner tool (spr)")

  # Options to set the entry point
  group = parser.add_mutually_exclusive_group(required=True)
  group.add_argument("--entry-point", dest='entry_point', default=None, help="Entry point name")
  group.add_argument("--entry-point-from-bool-attribute", dest='entry_point_from_bool_attribute',
    default=None, help="Get entry point from bool attribute on procedure e.g. {:entry_point}")

  pargs = parser.parse_args()

  if pargs.jobs < 1:
    _logger.error('Jobs must be >= 1')
    return 1

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  if logLevel == logging.DEBUG:
    logFormat = '%(levelname)s:%(threadName)s: %(filename)s:%(lineno)d %(funcName)s()  : %(message)s'
  else:
    logFormat = '%(levelname)s:%(threadName)s: %(message)s'

  logging.basicConfig(level=logLevel, format=logFormat)
  _logger = logging.getLogger(__name__)

  # Check paths that must exist
  for pathToCheck in [ pargs.input_program_list, pargs.spr_path]:
    if not os.path.exists(pathToCheck):
      _logger.error('"{}" does not exist'.format(pathToCheck))
      return 1

  # Check paths that must not already exist
  for pathToCheck in [ pargs.output_program_list, pargs.output_dir]:
    if os.path.exists(pathToCheck):
      _logger.error('Refusing to overwrite "{}"'.format(pathToCheck))
      return 1

  # Load list of programs
  programList = None
  try:
    _logger.debug('Loading program_list from "{}"'.format(pargs.input_program_list))
    programList = ProgramListLoader.load(pargs.input_program_list, pargs.rprefix)
  except (ProgramListLoader.ProgramListLoaderException) as e:
    _logger.error(e)
    _logger.debug(traceback.format_exc())

    return 1

  # Compute list index to entry point name mapping
  entryPoints = [ ]
  _logger.info('Getting program entry points...')
  for programPath in programList:
    if pargs.entry_point != None:
      entryPoints.append(pargs.entry_point)
    else:
      assert pargs.entry_point_from_bool_attribute != None
      entryPointName = EntryPointFinder.findEntryPointWithBooleanAttribute(pargs.entry_point_from_bool_attribute, programPath)
      assert entryPointName != None
      entryPoints.append(entryPointName)

  # Generate new programs
  _logger.info('Generating new programs')
  tasks = [ ]
  os.mkdir(pargs.output_dir)
  for index, (programPath, entryPoint) in enumerate(zip(programList, entryPoints)):
    outputPath = os.path.join(pargs.output_dir, 'program-{}.bpl'.format(index))
    tasks.append( ProgramGenTask(programPath, entryPoint, outputPath, pargs.spr_path) )

  # Run
  if pargs.jobs == 1:
    for t in tasks:
      t.run()
  else:
    signal.signal(signal.SIGINT, handleInterrupt)
    signal.signal(signal.SIGTERM, handleInterrupt)

    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=pargs.jobs) as executor:
      futureToRunner = { executor.submit(t.run) : t for t in tasks }
      for future in concurrent.futures.as_completed(futureToRunner):
        r = futureToRunner[future]
        _logger.info('{} runner finished'.format(r.outputPath))

        if future.exception():
          e = future.exception()
          cancel(futureToRunner)
          _logger.error(e)
          return 1

        if r.exitCode != 0:
          _logger.error('Tool failed')
          cancel(futureToRunner)
          return 1

  # Write program list
  with open(pargs.output_program_list, 'w') as f:
    for t in tasks:
      if t.exitCode != None:
        f.writelines('# Generated from {}\n'.format(t.programPath))
        f.writelines('{}\n\n'.format(t.outputPath))
      else:
        f.writelines('# Skipping program "{}" due to failure\n'.format(t.programPath))

  _logger.info('Finished')

  return 0

def cancel(futureToRunner):
  _logger.warning('Cancelling futures')
  for future in futureToRunner.keys():
    future.cancel()

class ProgramGenTask:
  def __init__(self, programPath, entryPoint, outputPath, sprPath):
    assert isinstance(programPath, str)
    assert isinstance(entryPoint, str)
    assert isinstance(outputPath, str)
    assert isinstance(sprPath, str)
    assert os.path.exists(programPath)
    self.programPath = programPath
    self.entryPoint = entryPoint
    self.outputPath = outputPath
    self.sprPath = sprPath
    self.exitCode = None

  def run(self):
    cmdLine = [ self.sprPath,
                '-e', self.entryPoint,
                '-p', 'Transform.AxiomAndEntryRequiresCheckTransformPass',
                '-o', self.outputPath,
                self.programPath
              ]
    _logger.debug('Running:\n{}'.format(pprint.pformat(cmdLine)))
    exitCode = subprocess.call(cmdLine)
    _logger.debug('Finished')
    self.exitCode = exitCode

if __name__ == '__main__':
  try:
    sys.exit(entryPoint(sys.argv[1:]))
  except KeyboardInterrupt:
    sys.exit(2)
