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
    return self._dev._tio.protocol.columns

  def stream_iter(self, number=0, flush=True):
    if flush:
      self._dev._tio.pub_flush()
    if number==0:
      while True:
        self._dev._tio.pub_warn_overload()
        yield self._dev._tio.dstream_read_raw(rows = 1, duration=None, flush=False)
    else:
      for x in range(number):
        self._dev._tio.pub_warn_overload()
        yield self._dev._tio.dstream_read_raw(rows = 1, duration=None, flush=False)

