#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
"""
This script generates a "quantile" style plot
inspired by the quantile plots used SV-COMP.
"""
import argparse
import logging
import os
import pprint
import sys
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile
from count_by_label_then_result_type import groupByResultTypeThenLabel
import matplotlib.pyplot as plt

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper

class ComputeScoreException(Exception):
  pass

class ScoredResultList:
  def __init__(self, listName, correctnessMapping):
    self.listName = listName
    self._correctnessMapping = correctnessMapping
    validateMappingFile(self._correctnessMapping)
    self._positiveResults = []
    self._zeroResults = []
    self._negativeResults = []

  def reset(self):
    self._positiveResults.clear()
    self._zeroResults.clear()
    self._negativeResult.clear()

  def addResult(self, r):
    score = self.computeScore(r)
    if score > 0:
      self._positiveResults.append( (score, r) )
    elif score == 0:
      self._zeroResults.append( r )
    else:
      assert score < 0
      self._negativeResults.append( (score, r) )

    return score

  def computeScore(self, r):
    # Get expected correctness
    programName = r['program']
    expectedCorrect = self._correctnessMapping[programName]['expected_correct']

    if expectedCorrect == None:
      # Can't handle results where the expected correctness is not known
      raise ComputeScoreException('Correctness not known for program {}'.format(programName))

    assert isinstance(expectedCorrect, bool)

    rType = classifyResult(r)

    # FIXME: We need to decide on what the most sensible scoring scheme is
    if expectedCorrect:
      if rType == FinalResultType.FULLY_EXPLORED:
        return 1
      elif rType == FinalResultType.BUG_FOUND:
        return -1 # Penalise wrong result
      elif rType == FinalResultType.BOUND_HIT:
        return 0
      else:
        return 0
    else:
      if rType == FinalResultType.FULLY_EXPLORED:
        return -1 # Penalise wrong result
      elif rType == FinalResultType.BUG_FOUND:
        return 1
      elif rType == FinalResultType.BOUND_HIT:
        return 0
      else:
        return 0


  @property
  def positiveResults(self):
    """
    Returns list that iterates over (score, result) tuples
    where the tuples are ordered (increasing) 'total_time' attribute
    """
    pResults = self._positiveResults.copy()
    pResults.sort(key=lambda e: e[1]['total_time'], reverse=False)
    return pResults

  @property
  def numOfPositiveResults(self):
    return len(self._positiveResults)

  @property
  def zeroResults(self):
    """
    Returns list that iterates over results that were
    given a zero score. The order of results is not defined
    """
    zResults = self._zeroResults.copy()
    return zResults

  @property
  def numOfZeroResults(self):
    return len(self._zeroResults)

  @property
  def negativeResults(self):
    """
    Returns list that iterates over (score, result) tuples
    where the tuples are ordered (increasing) 'total_time' attribute
    """
    nResults = self._negativeResults.copy()
    nResults.sort(key=lambda e: e[1]['total_time'], reverse=False)
    return nResults

  @property
  def numOfNegativeResults(self):
    return len(self._negativeResults)

  @property
  def totalNegativeScore(self):
    totalScore = 0
    for score, _ in self._negativeResults:
      assert isinstance(score, int)
      totalScore += score

    return totalScore

  @property
  def totalPositiveScore(self):
    totalScore = 0
    for score, _ in self._positiveResult:
      assert isinstance(score, int)
      totalScore += score

    return totalScore

  def totalScore(self):
    return self.totalNegativeScore + self.totalPositiveScore

def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument('label_mapping_file', type=argparse.FileType('r'))
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  parser.add_argument('--strip-result-set-suffix', dest='strip_result_set_suffix', type=str, default=None)

  actionGroup = parser.add_mutually_exclusive_group()
  actionGroup.add_argument('--ipython', action='store_true')
  actionGroup.add_argument('--pdf', help='Write graph to PDF')

  plotGroup = parser.add_mutually_exclusive_group()
  plotGroup.add_argument("--points", action='store_true')
  plotGroup.add_argument("--error-bars", action='store_true', dest='error_bars')

  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if len(pargs.result_ymls) < 2:
    logging.error('Need at least two YAML files')

  if pargs.pdf != None:
    if not pargs.pdf.endswith('.pdf'):
      logging.error('--pdf argument must end with .pdf')
      return 1
    if os.path.exists(pargs.pdf):
      logging.error('Refusing to overwrite {}'.format(pargs.pdf))
      return 1

  # Load correctness mapping file
  correctnessMapping = yaml.load(pargs.label_mapping_file, Loader=Loader)
  validateMappingFile(correctnessMapping)

  # Check that each yml file exists
  data = { }
  resultListNames = [ ]
  for f in pargs.result_ymls:
    if not os.path.exists(f):
      logging.error('YAML file {} does not exist'.format(f))
      return 1

    # Compute result set name
    resultListName = f
    resultListNames.append(resultListName)
    if resultListName in data:
      logging.error('Can\'t use {} as label name because it is already used'.format(resultListName))
      return 1

    data[resultListName] = None # Will be filled with loaded YAML data

  # Now load YAML
  length = 0
  for f in pargs.result_ymls:
    logging.info('Loading YAML file {}'.format(f))
    with open(f, 'r') as openFile:
      results = yaml.load(openFile, Loader=Loader)
    logging.info('Loading complete')
    assert isinstance(results, list)
    resultListName = f
    data[resultListName] = results
    length = len(results)

  # Check the lengths are the same
  for name, rList in data.items():
    if len(rList) != length:
      logging.error('There is a length mismatch for {}, expected {} entries but was'.format(name, length, len(rList)))
      return 1

  resultListNameToScoredResultList = {}
  resultListNameToAccumScore = {}
  resultListNameToRunTime = {}
  resultListNameToRunTimeStdDev = {}
  # Create data structures
  for resultListName in resultListNames:
    srl = ScoredResultList(resultListName, correctnessMapping)
    resultListNameToScoredResultList[resultListName] = srl
    resultListNameToAccumScore[resultListName] = accumScores = [ ]
    resultListNameToRunTime[resultListName] = runTimes = [ ]
    resultListNameToRunTimeStdDev[resultListName] = runTimeStdDevs = []

    # Add results and compute score
    unknownBenchmarkCount=0
    for r in data[resultListName]:
      try:
        srl.addResult(r)
      except ComputeScoreException as e:
        unknownBenchmarkCount +=1
        programName = r['program']
        logging.debug('Failed to compute score for "{}": {}'.format(programName, e))

    # Report information about how benchmarks were used
    logging.info('{}: {} +ve , {} zero, {} -ve out of {} ({} unknown correctness)'.format(
                resultListName,
                srl.numOfPositiveResults,
                srl.numOfZeroResults,
                srl.numOfNegativeResults,
                len(data[resultListName]),
                unknownBenchmarkCount))

    positiveResults = srl.positiveResults
    # Add dummy point
    dummyTime = 0.0
    if len(positiveResults) == 0:
      logging.warning('No positive results will use 0 as time for dummy point')
    else:
      # Use the time of the first positive result which should have the shortest time
      firstResult = positiveResults[0][1]
      assert isinstance(firstResult, dict)
      dummyTime = firstResult['total_time']
    assert isinstance(dummyTime, float)
    assert dummyTime >= 0.0
    accumScores.append(0)
    runTimes.append(dummyTime)
    runTimeStdDevs.append(0.0) # Dummy point has no y errors

    largestSeenTime = dummyTime # used for an assert
    accum = 0
    # Add other points
    for (score, r) in positiveResults:
      assert r['total_time'] >= largestSeenTime
      largestSeenTime = r['total_time']
      accum += score
      accumScores.append(accum)
      runTimes.append(r['total_time'])
      runTimeStdDevs.append(r['total_time_stddev'])

    assert len(accumScores) == len(runTimes)
    # offset all points along the x-axis (accumalative score)
    xOffset = srl.totalNegativeScore
    assert xOffset <= 0.0
    for index in range(len(accumScores)):
      score = accumScores[index]
      accumScores[index] = score + xOffset
      

  # Now plot

  fig, ax = plt.subplots()
  #fig.set_figwidth(3.25)
  #fig.set_figheight(2)
  # Ewww. Inches
  logging.info('Figure size is:{}'.format(fig.get_size_inches()))


  titleString="Quantile plot"

  ax.set_title(titleString)
  ax.set_xlabel('Accumulated score')
  ax.set_ylabel('Runtime (s)')

  # Add curves
  curves = [ ]
  legendNames = [ ]
  for resultListName in resultListNames:
    x = resultListNameToAccumScore[resultListName]
    y = resultListNameToRunTime[resultListName]
    yErrors = resultListNameToRunTimeStdDev[resultListName]
    if pargs.error_bars:
      p = ax.errorbar(x,y,yerr=yErrors)
    else:
      p = ax.plot(x,y, '-o' if pargs.points else '-')
    curves.append(p[0])
    legendNames.append(resultListName)
  # Add legend
  if pargs.strip_result_set_suffix != None:
    suffix = pargs.strip_result_set_suffix
  else:
    suffix='merged.yml'
  legendNames = list(map(lambda s: s[0:-len(suffix) -1] if s.endswith(suffix) else s, legendNames))
  print(legendNames)
  assert len(legendNames) == len(curves)

  # HACK: move the legend outside
  # Shrink current axis by 20%
  box = ax.get_position()
  print(box)
  legend = ax.legend(tuple(curves), tuple(legendNames),
    loc='upper left',
    bbox_to_anchor=(1.01, 1.0),
    borderaxespad=0 # No padding so that corners line up
    )

  # Work out how wide the legend is in terms of axes co-ordinates
  fig.canvas.draw() # Needed say that legend size computation is correct
  legendWidth, _ = ax.transAxes.inverted().transform((legend.get_frame().get_width(), legend.get_frame().get_height()))
  assert legendWidth > 0.0

  # FIXME: Why do I have to use 0.95??
  ax.set_position([box.x0, box.y0, box.width * (0.95 - legendWidth), box.height])
  # Adjust y-axis so it is a log plot everywhere except [-1,1] which is linear
  ax.set_yscale('symlog', linthreshy=1.0, linscaley=0.1)
  ax.grid()


  # Use major labels to divide the tools
  #ax.set_xticks(numpy.arange(1, len(resultListNames)), minor=False)
  #ax.set_xticklabels([ '' for _ in resultListNames ], minor=False)
  #ax.xaxis.set_tick_params(which='major', width=3, direction='out')

  if pargs.ipython:
    # Useful interfactive console
    header="""Useful commands:
    fig.show() - Shows figure
    fig.canvas.draw() - Redraws figure (useful if you changed something)
    fig.savefig('something.pdf') - Save the figure
    """
    from IPython import embed
    embed(header=header)
  elif pargs.pdf != None:
    fig.show()
    logging.info('Writing PDF to {}'.format(pargs.pdf))
    fig.savefig(pargs.pdf)
  else:
    plt.show()
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
