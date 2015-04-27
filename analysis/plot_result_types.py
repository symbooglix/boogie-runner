#!/usr/bin/env python
# vim: set sw=2 ts=2 softtabstop=2 expandtab:
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


def main(args):
  labelTypes = ['all', 'correct', 'incorrect', 'unknown', 'stacked']

  parser = argparse.ArgumentParser()
  parser.add_argument("-l","--log-level",type=str, default="info", dest="log_level", choices=['debug','info','warning','error'])
  parser.add_argument('-m', '--label-mapping-file', type=argparse.FileType('r'), default=None, dest='label_mapping_file')
  parser.add_argument('--ipython', action='store_true')
  parser.add_argument('label_type', type=str, choices=labelTypes, help='The label type.')
  parser.add_argument('result_ymls', nargs='+', help='Input YAML files')
  pargs = parser.parse_args(args)

  logLevel = getattr(logging, pargs.log_level.upper(),None)
  logging.basicConfig(level=logLevel)

  if len(pargs.result_ymls) < 2:
    logging.error('Need at least two YAML files')

  # Load mapping file if necessary
  if pargs.label_type != 'all':
    if pargs.label_mapping_file == None:
      logging.error('Label mapping file must be specified if using label type {}'.format(
        pargs.label_type))
      return 1
    else:
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

  resultListNameToResultTypeMapMap = {}
  # Create data structures
  for resultListName in resultListNames:
    # Get FinalResultType -> list of result map
    if pargs.label_type == 'all':
      resultListNameToResultTypeMapMap[resultListName] = groupByResultTypeThenLabel(data[resultListName], correctnessMapping=None, keyIsEnum=True)
      assert isinstance(resultListNameToResultTypeMapMap[resultListName], dict)
    else:
      labelledCorrect, labelledIncorrect, labelledUnknown = groupByResultTypeThenLabel(data[resultListName], correctnessMapping=correctnessMapping, keyIsEnum=True) 
      if pargs.label_type == 'correct':
        resultListNameToResultTypeMapMap[resultListName] = labelledCorrect
      elif pargs.label_type == 'incorrect':
        resultListNameToResultTypeMapMap[resultListName] = labelledIncorrect
      elif pargs.label_type == 'unknown':
        resultListNameToResultTypeMapMap[resultListName] = labelledUnknown
      else:
        raise Exception('Unexpected label type')

  correctCounts = list(map(lambda name: 
                      len(resultListNameToResultTypeMapMap[name][FinalResultType.FULLY_EXPLORED]),
                      resultListNames))
  incorrectCounts = list(map(lambda name: 
                      len(resultListNameToResultTypeMapMap[name][FinalResultType.BUG_FOUND]),
                      resultListNames))
  boundHitCounts = list(map(lambda name: 
                      len(resultListNameToResultTypeMapMap[name][FinalResultType.BOUND_HIT]),
                      resultListNames))

  unknownCounts = [ ]
  for resultListName in resultListNames:
    count = 0
    rTypeToListMap = resultListNameToResultTypeMapMap[resultListName]
    assert isinstance(rTypeToListMap, dict)
    for key, l in rTypeToListMap.items():
      assert isinstance(key, FinalResultType)
      assert isinstance(l, list)
      if (key == FinalResultType.FULLY_EXPLORED or 
          key == FinalResultType.BUG_FOUND or
          key == FinalResultType.BOUND_HIT):
        continue
      count += len(l)
    unknownCounts.append(count) 

  # Now plot
  assert len(correctCounts) == len(resultListNames)
  assert len(incorrectCounts) == len(resultListNames)
  assert len(boundHitCounts) == len(resultListNames)
  assert len(unknownCounts) == len(resultListNames)
  import numpy
  indicies = numpy.arange(len(resultListNames))
  width=0.25

  # Find the maximum bar height so we can calculate the yticks
  maxY = max(correctCounts + incorrectCounts + boundHitCounts + unknownCounts)
  assert maxY >= 0

  fig, ax = plt.subplots()
  fig.set_figwidth(3.25)
  fig.set_figheight(2)
  # Ewww. Inches
  logging.info('Figure size is:{}'.format(fig.get_size_inches()))
  correctBars = ax.bar(indicies, correctCounts, width, color='g', hatch='\\')
  incorrectBars = ax.bar(indicies + width, incorrectCounts, width, color='r', hatch='/')
  boundHitBars = ax.bar(indicies + 2*width, boundHitCounts, width, color='b', hatch='x')
  unknownBars = ax.bar(indicies + 3*width, unknownCounts, width, color='y')

  titleString=None
  if pargs.label_type == 'all':
    titleString="Tool results over all benchmarks"
  else:
    titleString = "Tool results over all benchmarks with expected correctness {}".format(
      pargs.label_type)

  ax.set_title(titleString)
  ax.set_xlabel('Tool')
  ax.set_ylabel('Benchmark count')
  #step = 25
  #ax.set_yticks(numpy.arange(0, maxY +1, step))

  ax.set_xticks(numpy.arange(len(resultListNames)) + 0.5, minor=True)
  # Sort out the xlabels
  import textwrap
  suffix='merged.yml'
  maxLabelWidth=10
  # -1 is for slash in <thing>/<suffix>
  xLabels = list(map(lambda s: textwrap.fill(s,maxLabelWidth),
      map(lambda s: s[0:-len(suffix) -1] if s.endswith(suffix) else s,
    resultListNames)))
  ax.set_xticklabels(xLabels, minor=True)

  # Use major labels to divide the tools
  ax.set_xticks(numpy.arange(1, len(resultListNames)), minor=False)
  ax.set_xticklabels([ '' for _ in resultListNames ], minor=False)
  ax.xaxis.set_tick_params(which='major', width=3, direction='out')

  # attach some text labels
  for barPlot in [correctBars, incorrectBars, boundHitBars, unknownBars]:
    for rect in barPlot:
      height = rect.get_height()
      ax.text(rect.get_x()+rect.get_width()/2., 1.02*height, '%d'%int(height),
                ha='center', va='bottom')

  # Add legend
  ax.legend( (correctBars, incorrectBars, boundHitBars, unknownBars),
             ('Correct', 'Incorrect', 'Bound hit', 'Unknown'),
             loc='upper left')

  if pargs.ipython:
    from IPython import embed
    embed()
    # Call fig.show() to see the figure
  else:
    plt.show()
  return 0

if __name__ == '__main__':
  sys.exit(main(sys.argv[1:]))
