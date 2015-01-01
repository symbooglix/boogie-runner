# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . RunnerBase import RunnerBaseClass, ResultType
import logging
import os
import psutil
import re
import yaml

_logger = logging.getLogger(__name__)

class BoogalooRunnerException(Exception):
  def __init__(self, msg):
    self.msg = msg

class BoogalooRunner(RunnerBaseClass):

  staticCounter = 0
  def __init__(self, boogieProgram, rc):
    _logger.debug('Initialising {}'.format(boogieProgram))

    super(BoogalooRunner, self).__init__(boogieProgram, rc)

    # Sanity checks
    # TODO


  @property
  def name(self):
    return "boogaloo" + ('-docker' if self.useDocker else '')

  def getResults(self):
    results = super(BoogalooRunner, self).getResults()

    # Interpret exit code and log output
    resultType = ResultType.UNKNOWN

    if not os.path.exists(self.logFile):
      _logger.error('log file is missing')
      return results

    timeoutHit = (self.exitCode == None)
    # scan for know keywords to determine if any bugs were found
    successes = 0
    errors = 0

    successR = re.compile(r'Execution \d+:.+ passed')
    errorR = re.compile(r'Execution \d+:.+ failed')
    with open(self.logFile, 'r') as f:
      for line in f:
        matchS = successR.search(line)
        if matchS != None:
          successes += 1
        
        matchE = errorR.search(line)
        if matchE != None:
          errors += 1
   
    _logger.debug('Found {} errors, {} successes'.format(
      errors, successes))
    if errors > 0:
      if timeoutHit:
        resultType = ResultType.BUGS_TIMEOUT
      else:
        resultType = ResultType.BUGS_NO_TIMEOUT
    elif successes > 0: 
      if timeoutHit:
        resultType = ResultType.NO_BUGS_TIMEOUT
      else:
        resultType = ResultType.NO_BUGS_NO_TIMEOUT
    else:
      _logger.warning('Unknown result')
    
    results['result'] = resultType
    return results

  def run(self):
    cmdLine = [ ]

    # FIXME: Move this into RunnerBaseClass
    containerName = ""
    if self.useDocker:
      cmdLine.extend(['docker', 'run', '--rm'])

      # Specifying tty prevents buffering of boogaloo's output
      cmdLine.append('--tty')

      containerName = 'boogaloo-bg-{}-{}'.format(os.getpid(), self.uid)

      # Compute the volume we need to mount inside the container
      volumeSrc = os.path.dirname(self.program)

      cmdLine.append('--volume={src}:{dest}'.format(
        src=volumeSrc, dest=self.dockerVolume))

      cmdLine.append('--name={}'.format(containerName))

      # Compute working directory inside the container
      containerWorkDir = os.path.join(self.dockerVolume, self.workDirName)
      cmdLine.append('--workdir={}'.format(containerWorkDir))

      cmdLine.append(self.dockerImage)
      cmdLine.append(self.toolPath)


    else:
      cmdLine.append(self.toolPath)

    # Use Boogaloo in execute mode
    cmdLine.append('exec')

    cmdLine.extend(self.additionalArgs)
    cmdLine.append('--proc={}'.format(self.entryPoint))

    # Add the boogie source file as last arg
    cmdLine.append(self.programPathArgument)

    # We assume that Boogie has no default timeout
    # so we force the timeout within python
    self.exitCode = None
    try:
      self.exitCode = self.runTool(cmdLine, isDotNet=False)
    except psutil.TimeoutExpired as e:
      _logger.warning('Boogaloo hit hard timeout')

      if self.useDocker:
        _logger.info('Trying to kill container {}'.format(containerName))
        process = psutil.Popen(['docker', 'kill', containerName])
        process.wait()

def get():
  return BoogalooRunner
