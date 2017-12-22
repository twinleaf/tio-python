"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com
    OriginalDate: November 2017
"""

import tio

class TwinleafDataController(object):
  def __init__(self, dev):
    self._dev = dev
    self.stream = self._dev._tio.dstream_read_raw

  def stream_columns(self):
    return self._dev._tio.columns

  def stream_iter(self, number=0):
    if number==0:
      while True:
        yield self._dev._tio.dstream_read_raw(rows = 1, duration=None)
    else:
      for x in range(number):
        yield self._dev._tio.dstream_read_raw(rows = 1, duration=None)

