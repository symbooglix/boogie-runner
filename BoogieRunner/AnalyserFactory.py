# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import logging
import pkgutil
import importlib
import os

_logger = logging.getLogger(__name__)

def getAnalyserClass(analyserString):
  _logger.info('Attempting to load runner "{}"'.format(analyserString))
  from . import Analysers

  module = None
  path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Analysers')
  for moduleFinder, name, isPkg in pkgutil.iter_modules([path]):
    if name == analyserString:
      # FIXME: I don't like that we have to specify "BoogieRunner"
      module = importlib.import_module('.' + name, 'BoogieRunner.Analysers')


  return module.get()
