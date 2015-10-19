# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass
from .. Analysers.Klee import KleeAnalyser
import logging
import os
import re
import psutil
import yaml

_logger = logging.getLogger(__name__)

class KleeRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class KleeRunner(RunnerBaseClass):
  softTimeoutDiff = 30 # Allow 30 seconds for file logging to finish
  def __init__(self, bitcodeProgram, workingDirectory, rc):
    _logger.debug('Initialising {}'.format(bitcodeProgram))
    super(KleeRunner, self).__init__(bitcodeProgram, workingDirectory, rc)

    # Sanity checks

    # We handle several options ourselves. Don't let the user set these
    disallowedArgs = [ '-maxtime',
                       '-max-memory',
                       '-entry-point',
                       '-exit-on-error'
                      ]
    for arg in self.additionalArgs:
      for disallowedArg in disallowedArgs:
        if arg.startswith(disallowedArg):
          raise KleeRunnerException('{} must not be specified'.format(disallowedArg))

    # KLEE will respect the timeout it was given and will not
    # be able to find anymore bugs after the timeout was hit, however
    # it needs to be allowed extra time to perform clean up because
    # it will log many files useful for debugging.
    self.softTimeout = self.maxTimeInSeconds
    self.maxTimeInSeconds = self.softTimeout + self.softTimeoutDiff
    assert self.maxTimeInSeconds >= self.softTimeout

  @property
  def name(self):
    return "klee"

  def GetNewAnalyser(self, resultDict):
    return KleeAnalyser(resultDict)

  def _buildResultDict(self):
    results = super(KleeRunner, self)._buildResultDict()
    results['klee_dir'] = self.outputDir
    return results

  def run(self):
    # Build the command line
    cmdLine = [ self.toolPath ] + self.additionalArgs

    # KLEE outputdir
    self.outputDir = os.path.join(self.workingDirectoryInBackend, "klee-wd")
    cmdLine.append('-output-dir={}'.format(self.outputDir))
    # Disable KLEE's enforcement of a memory limit. We enforce it externally instead.
    cmdLine.append('-max-memory=0')

    # Exit if we find a bug with exit code 1
    cmdLine.append('-exit-on-error')

    if self.entryPoint == None:
      _logger.warning('Entry point not specified!')
    else:
      # Set implementation to enter
      cmdLine.append('-entry-point={}'.format(self.entryPoint))

    # Force soft timeout
    _logger.info('Setting soft timeout of {} seconds'.format(self.softTimeout))
    cmdLine.append('-max-time={}'.format(self.softTimeout))

    # Add the LLVM bitcode file as the last arg
    cmdLine.append(self.programPathArgument)

    backendResult = self.runTool(cmdLine, isDotNet=False)
    if backendResult.outOfTime:
      _logger.warning('Hard timeout hit')

def get():
  return KleeRunner
