# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import logging
import pkgutil
import importlib
import os

_logger = logging.getLogger(__name__)

def getRunnerClass(runnerString):
  _logger.info('Attempting to load runner "{}"'.format(runnerString))
  from . import Runners

  module = None
  path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Runners')
  for moduleFinder, name, isPkg in pkgutil.iter_modules([path]):
    if name == runnerString:
      # FIXME: I don't like that we have to specify "BoogieRunner"
      module = importlib.import_module('.' + name, 'BoogieRunner.Runners')


  return module.get()
