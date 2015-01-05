from enum import Enum, unique

@unique
class ResultType(Enum):
  NO_BUGS_NO_TIMEOUT = 0
  BUGS_NO_TIMEOUT = 1
  NO_BUGS_TIMEOUT = 2
  BUGS_TIMEOUT = 3
  UNKNOWN = 4