# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import logging
import os
import re

_logger = logging.getLogger(__name__)

class EntryPointFinderException(Exception):
  pass

def findEntryPointWithBooleanAttribute(attributeName, programPath):
  assert isinstance(attributeName, str)
  assert isinstance(programPath, str)

  if not os.path.exists(programPath):
    msg = '"{}" does not exist'.format(programPath)
    _logger.error(msg)
    raise EntryPointFinderExcpetion(msg)

  entryPoint = None
  # Scan the Boogie program source code for the boolean attribute we want to match
  # The first procedure found with the attribute is returned
  with open(programPath) as f:
    lines = f.readlines()

    attrRegex = r'(?:\s*\{:\w+\s*([0-9]+|"[^"]+?")?\}\s*)*\s*'
    procNameRegex = r'(?P<proc>[a-zA-Z_$][a-zA-Z_$0-9]*)'
    fullRegex = r'procedure\s*' + attrRegex + r'\{:' + attributeName + r'\s*\}' + attrRegex + procNameRegex + r'\('
    r = re.compile(fullRegex)

    for line in [ l.rstrip() for l in lines]:
      m = r.match(line)
      #_logger.debug('Trying to match line \"{}\"'.format(line))
      if m != None:
        entryPoint = m.group('proc')
        break

    if entryPoint != None:
      _logger.debug('Found entry point "{}" in "{}"'.format(entryPoint, programPath))
    else:
      _logger.debug('Could not find entry point in "{}"'.format(programPath))

  return entryPoint
