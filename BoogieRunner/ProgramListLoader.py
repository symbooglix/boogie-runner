# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import logging
import os

class ProgramListLoaderException(Exception):
  def __init__(self, msg):
    self.msg = msg

_logger = logging.getLogger(__name__)

def load(programListFileName, relativePathPrefix):
  _logger.debug('Loading program list from "{}"'.format(programListFileName))
  _logger.debug('Using relative path prefix "{}"'.format(relativePathPrefix))

  if not os.path.exists(programListFileName):
    raise ProgramListLoaderException(
      'programList file ("{}") does not exist'.format(programListFileName))

  programSet = set()

  with open(programListFileName, 'r') as f:
    lines = f.readlines()
    
    # Loop over lines (with newline characters stripped)
    lineCounter=0
    for line in [ l.rstrip("\r\n") for l in lines ]:
      lineCounter += 1
      logging.debug('Reading line {}: "{}"'.format(lineCounter, line))

      if line.startswith('#'):
        logging.debug('Skipping comment line')
        continue
      if len(line) == 0:
        logging.debug('Skipping empty line')
        continue

      path = None
      if os.path.isabs(line):
        if not os.path.exists(line):
          raise ProgramListLoaderException(
            'File "{}" on line {} does not exist'.format(line, lineCounter))

          path = line
      else:
        # Append the prefix to make path absolute
        path = os.path.join(relativePathPrefix, line)
        _logger.debug('Join prefix and relative to get "{}"'.format(path))

        if not os.path.isabs(path):
          raise ProgramListLoaderException(
            'Joined paths ("{}") are not absolute'.format(path))

        if not os.path.exists(path):
          raise ProgramListLoaderException(
            'Joined paths ("{}") does not exist on line'.format(path, lineCounter))
      
      if path in programSet:
        raise ProgramListLoaderException(
          'Duplicate entry ("{}") on line {}'.format(path, lineCounter))

      programSet.add(path)

  l = list(programSet)
  l.sort()
  return l

