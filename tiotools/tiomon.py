#!/usr/bin/env python3
"""
..
    Copyright: 2017-2021 Twinleaf LLC
    Author: kornack@twinleaf.com

This is a command-line program which receives DAQ data from a socket
and dumps ASCII art and statistics to the console.

Python Library Dependencies:
    - blessings (for curses terminal animations)
"""

import blessings
import math
import time
import signal
import sys

class TermPlotter(object):
  """This is a helper/wrapper class to manage CLI animations and updates"""

  def __init__(self, columns, simple = False):
    self.columns = columns
    self.simple = simple
    self.term = blessings.Terminal()
    sys.stdout.write(self.term.move_up) # cover up connecting message from tio...
    self.ranges = [(0,0)] * len(self.columns)
    self.counts = [0] * len(columns)
    self.startTimes = [None] * len(self.columns)
    self.nameWidth = 0
    for column in self.columns:
      sys.stdout.write(f"\r\n{column:10s}: ...")
      self.nameWidth = max(len(column),self.nameWidth)
    print(self.term.move_up*(len(self.columns)+1))
    self.done = False

  def bar(self, value, column, width=50):
    """Internal helper for animating scalar values in ASCII.
    Returns up to 'width' bars, plus two characters (surrounding square
    brackets)"""
    (rmin, rmax) = self.ranges[column]
    if not math.isfinite(value) or not math.isfinite(rmin) or not math.isfinite(rmax):
        return "[%s]" % ("x" * width)
    if value > rmax or value < rmin:
        rmax = max(value, rmax)
        rmin = min(value, rmin)
        self.ranges[column] = (rmin, rmax)
    scale = rmax - rmin
    if scale != 0:
      fraction = (value - rmin) / (rmax - rmin)
    else:
      fraction = 0
    bars = int(fraction * width)
    s = "[%s%s]" % ("#" * bars, " " * (width-bars))
    return s#[:width+2]

  def update(self, row):
    for i, datum in enumerate(row):
      if (self.simple):
        sys.stdout.write(f"\r\n{self.term.clear_eol}{self.columns[i]:{self.nameWidth}s} {datum:10.4g}")
      else:
        # Count data
        self.counts[i] += 1
        spinner = "🕛🕐🕑🕒🕓🕔🕕🕖🕗🕘🕙🕚"[self.counts[i] % 12]
        #spinner = "|/-\\"[self.counts[i] % 4]

        # Measure rate
        if self.startTimes[i] is None:
          self.startTimes[i] = time.time()
          measuredRate = 0
        else:
          measuredRate = (self.counts[i]-1)/(time.time()-self.startTimes[i])
        rateString = "%6.2f Hz"% measuredRate

        barwidth = self.term.width - ( self.nameWidth + 29)
        barString = self.bar(datum, i, width=barwidth)

        sys.stdout.write(f"\r\n{self.term.clear_eol}{self.columns[i]:{self.nameWidth}s} {datum:10.4g} {spinner} {rateString} {barString}")

    if len(row) == len(self.columns): # Clean up rest of screen
      sys.stdout.write(self.term.clear_eos)
    sys.stdout.write(self.term.move_up*(len(row)+1))

  def finish(self):
    self.done = True
    print(self.term.move_down*(len(self.columns)))

def monitor(dev, simple=False):
  ui = TermPlotter(dev._tio.protocol.columns, simple=simple)

  def setExit(signal, frame):
    ui.finish()
    sys.exit(0)
  signal.signal(signal.SIGINT, setExit)
  signal.signal(signal.SIGTERM, setExit)

  for row in dev.data.stream_iter(): # This should block
    sys.stdout.write(f"\r\n{dev._tio.name} - {dev._tio.desc}")
    ui.update(row)

def main():
  # Running this script will attempt to connect to an attached vector magnetometer
  # It expects you to be tumbling the magnetometer for the specified duration
  import tldevice
  import argparse

  parser = argparse.ArgumentParser(prog='tio_monitor', 
                                   description='Live Twinleaf I/O Data Stream Monitor.')

  parser.add_argument("url", 
                      nargs='?', 
                      default='tcp://localhost/',
                      help='URL: tcp://localhost')
  parser.add_argument("--rpc", 
                      action='append', 
                      default=[],
                      type=lambda kv: kv.split(":"), 
                      help='Commands to be run on start; rpc:type:val')
  parser.add_argument('--simple',
                      action="store_true",
                      default=False,
                      help='Simplify display')
  args = parser.parse_args()

  device = tldevice.Device(url=args.url, rpcs=args.rpc, connectingMessage=False)
  monitor(device, simple=args.simple)


if __name__ == "__main__":
  main()

