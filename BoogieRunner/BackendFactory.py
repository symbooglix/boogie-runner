# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import logging
import pkgutil
import importlib
import os

_logger = logging.getLogger(__name__)

def getBackendClass(backendString):
  _logger.debug('Attempting to load backend "{}"'.format(backendString))
  from . import Backends

  module = None
  path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'Backends')
  for moduleFinder, name, isPkg in pkgutil.iter_modules([path]):
    if name == backendString:
      # FIXME: I don't like that we have to specify "BoogieRunner"
      module = importlib.import_module('.' + name, 'BoogieRunner.Backends')

  return module.get()
