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
  def __init__(self, boogieProgram, config):
    _logger.debug('Initialising {}'.format(boogieProgram))

    # Needed to give unique name for docker containers
    self.counter = BoogalooRunner.staticCounter
    BoogalooRunner.staticCounter += 1

    try:
      toolPath = config['runner_config']['tool_path']
    except KeyError:
      raise BoogalooRunnerException('"runner_config":"tool_path" not in config')

    self.useDocker = 'docker' in config['runner_config']

    if self.useDocker:
      # We need to fake 'tool_path' because its inside the container
      # We'll use the path to this python file
      config['runner_config']['tool_path'] = os.path.abspath(__file__)
      
    super(BoogalooRunner, self).__init__(boogieProgram, config)

    if self.useDocker:
      # Set the toolPath to be correct (overriding what parent constructor did)
      self.toolPath = toolPath

      # Check that the docker image is specified correctly

      dockerConfig = config['runner_config']['docker']
      if not isinstance(dockerConfig, dict):
        raise BoogalooRunnerException('"docker" key must map to a dictionary')
      
      if not 'image' in dockerConfig:
        raise BoogalooRunner('"image" missing from docker config')

      self.dockerImage = dockerConfig['image']

      if not isinstance(self.dockerImage, str):
        raise BoogalooRunnerException(
          '"image" must be a string that is a valid docker image name')

      if len(self.dockerImage) == 0:
        raise BoogalooRunnerException('"image" cannot be an empty string')

      # Get the docker volume location (inside the container)
      try:
        self.dockerVolume = dockerConfig['volume']
      except KeyError:
        raise BoogalooRunnerException('"volume" not specified for docker container')

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

    containerName = ""
    if self.useDocker:
      cmdLine.extend(['docker', 'run', '--rm'])

      containerName = 'boogaloo-bg-{}-{}'.format(os.getpid(), self.counter)

      # Compute the volume we need to mount inside the container
      volumeSrc = os.path.dirname(self.program)

      cmdLine.append('--volume={src}:{dest}'.format(
        src=volumeSrc, dest=self.dockerVolume))

      cmdLine.append('--name={}'.format(containerName))

      cmdLine.append(self.dockerImage)
      cmdLine.append(self.toolPath)
    else:
      cmdLine.append(self.toolPath)

    # Use Boogaloo in execute mode
    cmdLine.append('exec')

    cmdLine.extend(self.additionalArgs)
    cmdLine.append('--proc={}'.format(self.entryPoint))


    # Add the boogie source file as last arg
    if self.useDocker:
      progFilename = os.path.basename(self.program)  
      programPathInContainer = os.path.join(self.dockerVolume, progFilename)
      cmdLine.append(programPathInContainer)
    else:
      cmdLine.append(self.program)

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
