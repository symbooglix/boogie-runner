# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import logging
import os
import pprint
import traceback
import yaml

class ConfigLoaderException(Exception):
  def __init__(self, msg):
    self.msg = msg

_logger = logging.getLogger(__name__)

def load(configFileName):
  _logger.debug('Loading config file from "{}"'.format(configFileName))

  if not os.path.exists(configFileName):
    raise ConfigLoaderException('Config file "{}" does not exist'.format(configFileName))

  config = None
  with open(configFileName, 'r') as f:
    try:
      config = yaml.load(f)
    except Exception as e:
      raise ConfigLoaderException('Caught exception whilst loading config:\n' +
                                  traceback.format_exc())

  # A few sanity checks
  required_top_level_keys = ['runner', 'runner_config']
  for key in required_top_level_keys:
    if not key in config:
      raise ConfigLoaderException(
        '"{}" key missing from config file "{}"'.format(key, configFileName))

  _logger.info('Loaded config:\n{}'.format(pprint.pformat(config)))
  return config
