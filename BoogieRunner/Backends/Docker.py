# vim: set sw=2 ts=2 softtabstop=2 expandtab:
from . BackendBase import *
import logging

_logger = logging.getLogger(__name__)

class DockerBackendException(BackendException):
  pass

class DockerBackend(BackendBaseClass):
  def __init__(self, hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, **kwargs):
    super().__init__(hostProgramPath, workingDirectory, timeLimit, memoryLimit, stackLimit, **kwargs)

  @property
  def name(self):
    return "Docker"

  def run(self, cmdLine, logFilePath, extraEnv):
    raise DockerBackendException('Not implemented')

  def kill(self):
    raise DockerBackendException('Not implemented')

  def programPath(self):
    raise DockerBackendException('Not implemented')

def get():
  return DockerBackend
