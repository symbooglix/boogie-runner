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

def computeProgramNameToResults(data, resultListNames):
  output = { }

  for resultListName in resultListNames:
    for r in data[resultListName]:
      program = r['program']
      if program in output:
        output[program][resultListName] = r
      else:
        output[program] = { resultListName:r}

  for program, results in output.items():
    if len(results) != len(resultListNames):
      logging.warning('There are missing results for program {}'.format(program))

  return output


def main(args):
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument('label_mapping_file', type=argparse.FileType('r'))
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  parser.add_argument('--title', default="", type=str)
  parser.add_argument('--legend-name-map',dest='legend_name_map', default=None, type=str)
  parser.add_argument('--legend-position',dest='legend_position', choices=['outside_bottom', 'outside_right'])

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

  legendMapping = None
  # Load the legend mapping if it exists
  if pargs.legend_name_map != None:
    if not os.path.exists(pargs.legend_name_map):
      logging.error('"{}" does not exist'.format(pargs.legend_name_map))
      return 1
    with open(pargs.legend_name_map, 'r') as openFile:
      legendMapping = yaml.load(openFile, Loader=Loader)
      if not isinstance(legendMapping, dict):
        logging.error('Legend mapping should be a dictionary mapping file paths to legend name')
        return 1
      
      # Validate
      for resultListName in pargs.result_ymls:
        if not resultListName in legendMapping:
          logging.error('"{}" key is missing from the legend mapping file {}'.format(resultListName, pargs.legend_name_map))
          return 1

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

  # For Visualisation later
  programToResultsMap = computeProgramNameToResults(data, resultListNames)

  resultListNameToScoredResultList = {}
  resultListNameToAccumScore = {}
  resultListNameToRunTime = {}
  resultListNameToRunTimeStdDev = {}
  resultListNameToRawResultsListOrdered = { }
  # Create data structures
  for resultListName in resultListNames:
    srl = ScoredResultList(resultListName, correctnessMapping)
    resultListNameToScoredResultList[resultListName] = srl
    resultListNameToAccumScore[resultListName] = accumScores = [ ]
    resultListNameToRunTime[resultListName] = runTimes = [ ]
    resultListNameToRunTimeStdDev[resultListName] = runTimeStdDevs = []
    resultListNameToRawResultsListOrdered[resultListName] = rawResults = []

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
    rawResults.append(None) # Dummy

    largestSeenTime = dummyTime # used for an assert
    accum = 0
    # Add other points
    for (score, r) in positiveResults:
      assert r['total_time'] >= largestSeenTime
      largestSeenTime = r['total_time']
      accum += score
      accumScores.append(accum)
      runTimes.append(r['total_time'])
      rawResults.append(r)
      if 'total_time_stddev' in r:
        runTimeStdDevs.append(r['total_time_stddev'])
      else:
        logging.warning('Standard deviation missing for result {}'.format(r['program']))
        runTimeStdDevs.append(0)

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


  if len(pargs.title) > 0:
    ax.set_title(pargs.title)
  ax.set_xlabel('Accumulated score')
  ax.set_ylabel('Runtime (s)')

  class DataPointReporter:
    def __init__(self, plt, resultListName, resultListNames, resultListNameToRawResultsListOrdered, resultListNameToAccumScore, programToResultsMap):
      print("init")
      self.plt = plt
      self.cid = plt.figure.canvas.mpl_connect('pick_event',self)
      self.resultListNames = resultListNames
      self.resultListName = resultListName
      self.resultListNameToRawResultsListOrdered = resultListNameToRawResultsListOrdered # FIXME: Rename, this is just postive score results
      self.resultListNameToAccumScore = resultListNameToAccumScore
      self.programToResultsMap = programToResultsMap

    def dump(self, resultListName, program):
      resultsForProg = self.programToResultsMap[program]
      if not resultListName in resultsForProg:
        print("{} : not available".format(resultListName))
      else:
        result = resultsForProg[resultListName]
        rType = classifyResult(result)
        runTime = result['total_time']
        stdDev =  "UNKNOWN" if not 'total_time_stddev' in result else result['total_time_stddev']
        accumScore = self.getAccumScore(resultListName, program)
        accumScoreStr = "unknown" if accumScore == None else accumScore
        print("{} : {} ({} ± {} secs) (accumScore: {})".format(resultListName, rType, runTime, stdDev, accumScore))

    def getAccumScore(self, resultListName, program):
      # Try to find program in raw resultsList ordered
      # it might not be there
      index=0
      found = False
      for r in self.resultListNameToRawResultsListOrdered[resultListName]:
        if r == None:
          index += 1
          continue # Skip dummy point
        if r['program'] == program:
          found = True
          break
        index +=1

      if not found:
        return None

      return self.resultListNameToAccumScore[resultListName][index]


    def __call__(self, event):
      orderedResultList = self.resultListNameToRawResultsListOrdered[self.resultListName]
      scoreList = self.resultListNameToAccumScore[self.resultListName]
      artist = event.artist

      # Only print if we were clicked on
      if self.plt != artist:
        return

      print("*****")
      dataIndex = event.ind[0]
      r=orderedResultList[dataIndex]
      if r == None:
        print("Dummy point")
        return
      print("program: {}".format(r['program']))
      self.dump(self.resultListName, r['program'])
      print("Accum Score: {}".format(self.resultListNameToAccumScore[self.resultListName][dataIndex]))
      print("")
      print("OTHERS:")
      for resultListName in self.resultListNames:
        if self.resultListName == resultListName:
          continue
        self.dump(resultListName, r['program'])
      print("*****")

  # Add curves
  curves = [ ]
  legendNames = [ ]
  for resultListName in resultListNames:
    x = resultListNameToAccumScore[resultListName]
    y = resultListNameToRunTime[resultListName]
    yErrors = resultListNameToRunTimeStdDev[resultListName]
    pickTolerance=4
    if pargs.error_bars:
      p = ax.errorbar(x,y,yerr=yErrors, picker=pickTolerance)
    else:
      p = ax.plot(x,y, '-o' if pargs.points else '-', picker=pickTolerance)
    DataPointReporter(p[0], resultListName, resultListNames, resultListNameToRawResultsListOrdered, resultListNameToAccumScore, programToResultsMap)
    curves.append(p[0])
    legendNames.append(legendMapping[resultListName] if pargs.legend_name_map else resultListName)
  # Add legend
  assert len(legendNames) == len(curves)

  if pargs.legend_position == 'outside_right':
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
  else:
    box = ax.get_position()
    legend = ax.legend(tuple(curves), tuple(legendNames), ncol=3, bbox_to_anchor=(0.5, -0.08), loc='upper center')
    # Work out how wide the legend is in terms of axes co-ordinates
    fig.canvas.draw() # Needed say that legend size computation is correct
    legendWidth, legendHeight = ax.transAxes.inverted().transform((legend.get_frame().get_width(), legend.get_frame().get_height()))
    ax.set_position([box.x0, box.y0 + legendHeight + 0.1, box.width, box.height - (legendHeight + 0.05)])

  legend.draggable(True) # Make it so we can move the legend with the mouse
  # Adjust y-axis so it is a log plot everywhere except [-1,1] which is linear
  ax.set_yscale('symlog', linthreshy=1.0, linscaley=0.1)

  #set minor ticks on y-axis
  from matplotlib.ticker import LogLocator
  import numpy
  yAxisLocator = LogLocator(subs=numpy.arange(1.0,10.0))
  ax.yaxis.set_minor_locator(yAxisLocator)
  ax.yaxis.set_tick_params(which='minor', length=4)
  ax.yaxis.set_tick_params(which='major', length=6)
  #ax.grid()


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
