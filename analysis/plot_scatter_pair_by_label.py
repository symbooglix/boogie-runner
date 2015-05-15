#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
import argparse
import logging
import os
import pprint
import sys
import yaml
from br_util import FinalResultType, classifyResult, validateMappingFile
import matplotlib.pyplot as plt

try:
  # Try to use libyaml which is faster
  from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
  # fall back on python implementation
  from yaml import Loader, Dumper


def main(args):
  # FIXME: Clean me up!
  #resultTypes = [ r.name for r in list(FinalResultType)] # Get list of ResultTypes as strings
  #defaultTypes = [ r.name for r in list(FinalResultType) if r in [FinalResultType.FULLY_EXPLORED, FinalResultType.BUG_FOUND]]

  #failureTypes = { FinalResultType.UNKNOWN, FinalResultType.TIMED_OUT, FinalResultType.OUT_OF_MEMORY }

  usefulAnswerResultTypes = { FinalResultType.FULLY_EXPLORED, FinalResultType.BUG_FOUND}

  parser = argparse.ArgumentParser()
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument("-v", "--verbose", action='store_true', help='Show detailed information about mismatch')
  parser.add_argument('label_mapping', type=argparse.FileType('r'), help='correctness mapping YAML file')
  parser.add_argument('result_ymls', nargs=2, help='Input YAML files')
  parser.add_argument('max_time', type=int, help='Maximum time in seconds, results timings will be clamped to this value')
  parser.add_argument('--ipython', action='store_true')
  parser.add_argument('--point-size', type=float, default=30.0, dest='point_size')
  parser.add_argument('--click-shows-raw-data', dest='click_shows_raw_data', action='store_true', default=False)
  parser.add_argument('--only-show', dest='only_show', default='incorrect', choices=['correct', 'incorrect', 'unknown'])
  parser.add_argument('-c', '--only-allow-consistent', dest='only_allow_consistent',action='store_true', default=False)
  parser.add_argument('--axis-name-map',dest='axis_name_map', default=None, type=str)
  parser.add_argument('--draw-dual-timeout-count',dest='draw_dual_timeout_count', action='store_true', default=False)

  #group = parser.add_mutually_exclusive_group()
  #group.add_argument('-r', '--result-types-to-plot', nargs='+', dest='result_types_to_plot',
  #  choices=resultTypes, default=defaultTypes,
  #  help='Result types to plot (at least one of the pair must be of this type). Default: %(default)s')
  #group.add_argument('--all', default=False, action='store_true', help='Plot all result types')

  pargs = parser.parse_args(args)
  print(pargs)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if len(pargs.result_ymls) != 2:
    logger.error('Need two YAML files')

  # Load mapping
  correctnessMapping = yaml.load(pargs.label_mapping, Loader=Loader)
  validateMappingFile(correctnessMapping)

  axisMapping = None
  # Load the legend mapping if it exists
  if pargs.axis_name_map != None:
    if not os.path.exists(pargs.axis_name_map):
      logging.error('"{}" does not exist'.format(pargs.axis_name_map))
      return 1
    with open(pargs.axis_name_map, 'r') as openFile:
      axisMapping = yaml.load(openFile, Loader=Loader)
      if not isinstance(axisMapping, dict):
        logging.error('axis mapping should be a dictionary mapping file paths to axis name')
        return 1
  ## Create set of allowed result types
  #if pargs.all:
  #  allowedResultTypes = set(FinalResultType)
  #else:
  #  allowedResultTypes = set()
  #  for rType in pargs.result_types_to_plot:
  #    allowedResultTypes.add(FinalResultType[rType])
  #logging.info('Plotting points of type {}'.format(allowedResultTypes))

  # Check that each yml file exists
  # resultListName (i.e. filename) -> list of results for that file
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

  programToResultSetsMap = { }
  for resultListName in resultListNames:
    for r in data[resultListName]:
      programName = r['program']

      # Only add programs that we want
      if not programName in correctnessMapping:
        logging.error('{} is missing from correctness mapping'.format(programName))
        return 1
      expectedCorrect = correctnessMapping[programName]['expected_correct']
      assert expectedCorrect == None or isinstance(expectedCorrect, bool)

      skipBenchmark = False
      if pargs.only_show == 'incorrect':
        if expectedCorrect != False:
          skipBenchmark = True
      elif pargs.only_show == 'correct':
        if expectedCorrect != True:
          skipBenchmark = True
      elif pargs.only_show == 'unknown':
        if expectedCorrect != None:
          skipBenchmark = True
      else:
        assert False

      if skipBenchmark:
        logging.info('Filtering out {} ({}) because we are only showing benchmarks labelled as {}'.format(programName, expectedCorrect, pargs.only_show))
        continue
      try:
        existingDict = programToResultSetsMap[programName]
        existingDict[resultListName] = r
      except KeyError:
        programToResultSetsMap[programName] = { resultListName:r }

  # Check there are the same number of results for each program
  allowConsistentMismatchCount = 0
  disregardedResultTypeCount = 0
  clampCount = 0
  failedAnalysisGivenMaxTimeCount = 0
  xData = [ ]
  yData = [ ]
  countXLtYExceptDualTimeout=0
  countYLtXExceptDualTimeout=0
  countDualTimeout=0
  countXEqYExceptDualTimeout=0
  annotationLabels = [ ]
  for programName, resultListNameToRawResultMap  in programToResultSetsMap.items():
    if len(resultListNameToRawResultMap) != len(resultListNames):
      logging.error('For program {} there we only {} result lists but expected {}'.format(
        programName, len(resultListNameToRawResultMap), len(resultListNames)))
      logging.error(pprint.pformat(resultListNameToRawResultMap))
      return 1

    firstResult = resultListNameToRawResultMap[resultListNames[0]]
    secondResult = resultListNameToRawResultMap[resultListNames[1]]
    firstType = classifyResult(firstResult)
    secondType = classifyResult(secondResult)

    if pargs.only_allow_consistent:
      # For this program check that classifications are consistent
      # we take the first programList name as the expected
      if firstType != secondType:
        allowConsistentMismatchCount += 1
        logging.warning('Found mismatch for program {}:'.format(programName))
        for resultListName in resultListNames:
          logging.warning('{}: {}'.format(resultListName, classifyResult(resultListNameToRawResultMap[resultListName])))
        if pargs.verbose:
          logging.warning('\n{}'.format(pprint.pformat(resultListNameToRawResultMap)))
        logging.warning('Disregarding result\n')
        continue

    #if not firstType in allowedResultTypes and not secondType in allowedResultTypes:
    #  disregardedResultTypeCount += 1
    #  logging.warning('Disregarding {} in {} due to neither result types ({} and {}) not being one of the allow result types'.format(
    #    programName,
    #    resultListNames[0],
    #    firstType,
    #    secondType))
    #  continue

    # Clamp timings
    didClamp = False
    for resultListName in resultListNames:
      r = resultListNameToRawResultMap[resultListName]
      if r['total_time'] > pargs.max_time:
        logging.debug('Clamping {} for {}'.format(programName, resultListName))
        r['total_time'] = pargs.max_time
        didClamp = True
      if not classifyResult(r) in usefulAnswerResultTypes:
        logging.info('Clamping time for program {} for {} with result type {}'.format(
          r['program'], resultListName, classifyResult(r)))
        r['total_time'] = pargs.max_time
        didClamp = True

    if didClamp:
      clampCount += 1

        
    # Add data point for plotting
    xPoint = firstResult['total_time']
    yPoint = secondResult['total_time']

    # Update counts
    if xPoint == yPoint and xPoint == pargs.max_time:
      countDualTimeout += 1
    else:
      if xPoint < yPoint:
        countXLtYExceptDualTimeout +=1
        #print(programName)
        #print(pprint.pformat(resultListNameToRawResultMap))
        #return 1
      elif yPoint < xPoint:
        countYLtXExceptDualTimeout +=1
      else:
        assert xPoint == yPoint
        countXEqYExceptDualTimeout +=1

    xData.append(xPoint)
    yData.append(yPoint)
    annotationLabels.append(programName)

  # Give information
  # This is highly result specific and probably should be removed.
  occuranceCount = 0
  yValueThresh = 10.0
  xValueThresh = 100.0
  for xValue, yValue in zip(xData, yData):
    if yValue < yValueThresh and xValue > xValueThresh and xValue != pargs.max_time:
      occuranceCount += 1
  print(" # of times yValue < {} and xValue > {} and where for tool on x axis it was not a timeout : {}".format(yValueThresh, xValueThresh, occuranceCount))

  # Finally do plotting
  assert len(xData) == len(yData) == len(annotationLabels)
  assert countXLtYExceptDualTimeout + countYLtXExceptDualTimeout + countXEqYExceptDualTimeout + countDualTimeout == len(xData)
  extend = 100
  tickFreq = 100
  xAxisLabel=""
  yAxisLabel=""
  if pargs.axis_name_map:
    xAxisLabel = axisMapping[resultListNames[0]]
    yAxisLabel = axisMapping[resultListNames[1]]
  else:
    xAxisLabel=resultListNames[0]
    yAxisLabel=resultListNames[1]

  if pargs.only_allow_consistent:
    logging.info('# of mismatches when only allowing consistent results: {}'.format(allowConsistentMismatchCount))
  logging.info('# of result pairs clamped: {}'.format(clampCount))
  logging.info('# of points plotted: {} out of {}'.format(len(xData), len(programToResultSetsMap)))
  logging.info('# of {x} < {y} (x < y): {}'.format(countXLtYExceptDualTimeout, x=xAxisLabel, y=yAxisLabel))
  logging.info('# of {y} < {x} (y < x): {}'.format(countYLtXExceptDualTimeout, x=xAxisLabel, y=yAxisLabel))
  logging.info('# of {x} == {y} (x == y) (ignoring timeouts): {}'.format(countXEqYExceptDualTimeout, x=xAxisLabel, y=yAxisLabel))
  logging.info('# of dual timeouts: {}'.format(countDualTimeout))
  fig, ax = plt.subplots()
  splot = ax.scatter(xData, yData, picker=5, s=pargs.point_size)

  ax.tick_params(which='both', labelsize=15)
  xAxisLabel += " execution time (s)"
  yAxisLabel += " execution time (s)"
  ax.set_xlabel(xAxisLabel, fontsize=15)
  ax.set_xlim(0,pargs.max_time + extend)
  # +1 is just so the pargs.max_time is included because range()'s end is not inclusive
  ax.set_xticks(range(0, pargs.max_time + 1, tickFreq))
  ax.set_ylabel(yAxisLabel, fontsize=15)
  ax.set_ylim(0,pargs.max_time + extend)
  ax.set_yticks(range(0, pargs.max_time + 1, tickFreq))
  ax.grid(False)

  # HACK: Annotate gt,lt and dual timeout numbers
  # FIXME: don't hardcode
  ax.annotate('{}'.format(countXLtYExceptDualTimeout), xy=(200,550), fontsize=40)
  ax.annotate('{}'.format(countYLtXExceptDualTimeout), xy=(550,200), fontsize=40)
  if countXEqYExceptDualTimeout > 0:
    ax.annotate('{}'.format(countXEqYExceptDualTimeout), xy=(450,450))
  if pargs.draw_dual_timeout_count:
    ax.annotate('{}'.format(countDualTimeout), xy=(pargs.max_time -5, pargs.max_time -5), xytext=(pargs.max_time -100, pargs.max_time), arrowprops=dict(width=0.5,facecolor='black', shrink=0.05))


  # Add annotations that become visible when clicked
  DataPointReporter(splot, xData, yData, annotationLabels, programToResultSetsMap, pargs.click_shows_raw_data)

  fig.tight_layout()

  # Identity line
  ax.plot([ 0 , pargs.max_time + extend], [0, pargs.max_time + extend], linewidth=1.0, color='black')
  if pargs.ipython:
    from IPython import embed
    embed()
    # Call fig.show() to see the figure
  else:
    plt.show()


  return 0

class DataPointReporter:
  def __init__(self, scatter, xData, yData, annotationLabels, programToResultSetsMap, clickShowsRawData):
    self.scatter = scatter
    self.cid = scatter.figure.canvas.mpl_connect('pick_event', self)
    self.annotationLabels = annotationLabels
    self.programToResultSetsMap = programToResultSetsMap
    self.clickShowsRawData = clickShowsRawData
    # Add annotations, by hide them by default
    self.annotationObjects = [ ]
    self.lastClickedAnnotationObj = None
    for index, text in enumerate(annotationLabels):
      text = text.replace('/','/\n')
      annotation = scatter.axes.annotate(text, (xData[index], yData[index]))
      annotation.set_visible(False)
      annotation.set_horizontalalignment('center')
      self.annotationObjects.append(annotation)

  def __call__(self, event):
    programName = self.annotationLabels[event.ind[0]]
    logging.info('*****')
    logging.info('{}'.format(programName))
    for resultListName, rawResultData in self.programToResultSetsMap[programName].items():
      if self.clickShowsRawData:
        logging.info('{}: {}\n{}'.format(resultListName, classifyResult(rawResultData), pprint.pformat(rawResultData)))
      else:
        logging.info('{}: {} ({} ± {} secs)'.format(
          resultListName,
          classifyResult(rawResultData),
          rawResultData['total_time'],
          rawResultData['total_time_stddev'] if 'total_time_stddev' in rawResultData else 'UNKNOWN'
          ))
    logging.info('*****')

    theAnnotation = self.annotationObjects[event.ind[0]]
    if self.lastClickedAnnotationObj != None:
      self.lastClickedAnnotationObj.set_visible(False)

    if self.lastClickedAnnotationObj != theAnnotation:
      theAnnotation.set_visible(True)
    else:
      # If the user click the point again we hide it
      theAnnotation.set_visible(False)

    self.lastClickedAnnotationObj = theAnnotation
    # Force redraw
    self.scatter.figure.canvas.draw()

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
