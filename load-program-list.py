#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
    Script to load and check a program list.
"""
import argparse
import logging
import os
from BoogieRunner import ProgramListLoader
import traceback
import signal
import sys

_logger = None

def entryPoint(args):
  global _logger, futureToRunner
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("--rprefix", default=os.getcwd(), help="Prefix for relative paths for program_list")
  parser.add_argument('--report-missing', dest='report_missing', default=False, action="store_true")
  parser.add_argument("program_list", help="File containing list of Boogie programs")

  pargs = parser.parse_args()

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  if logLevel == logging.DEBUG:
    logFormat = '%(levelname)s:%(threadName)s: %(filename)s:%(lineno)d %(funcName)s()  : %(message)s'
  else:
    logFormat = '%(levelname)s:%(threadName)s: %(message)s'

  logging.basicConfig(level=logLevel, format=logFormat)
  _logger = logging.getLogger(__name__)

  programList = None
  try:
    _logger.debug('Loading program_list from "{}"'.format(pargs.program_list))
    programList = ProgramListLoader.load(pargs.program_list,
                  pargs.rprefix,
                  existCheck= not pargs.report_missing)
  except (ProgramListLoader.ProgramListLoaderException) as e:
    _logger.error(e)
    _logger.debug(traceback.format_exc())
    return 1

  # Report missing files if requested
  missingCount=0
  presentCount=0
  if pargs.report_missing:
    for p in programList:
      if not os.path.exists(p):
        _logger.warning('Program "{}" is missing'.format(p))
        missingCount += 1
      else:
        presentCount +=1
    _logger.info('{} missing programs'.format(missingCount))
    _logger.info('{} present programs'.format(presentCount))

  logging.info('Loaded {} programs'.format(len(programList)))
  return 0

if __name__ == '__main__':
  sys.exit(entryPoint(sys.argv[1:]))
