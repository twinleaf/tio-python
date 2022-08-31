"""
..
    Copyright: 2017-2021 Twinleaf LLC
    Author: kornack@twinleaf.com
    OriginalDate: November 2017
"""

import tio

class TwinleafDataController(object):
  def __init__(self, dev):
    self._dev = dev

  def __call__(self, samples=1, duration=None, timeaxis=False, flush=True, simplify_single=True):
    return self._dev._tio.stream_read_raw(samples = samples, duration=duration, flush=flush, timeaxis=timeaxis, simplify_single=simplify_single)

  def columnnames(self, withName=True):
    columnnames = self._dev._tio.protocol.columns
    if withName:
      routingString = "/"+"/".join(map(str,self._dev._tio.routing))
      columnnames = [self._dev._tio.name+' '+routingString+' '+columnname for columnname in columnnames ]
    return columnnames

  def iter(self, samples=0, flush=True, timeaxis=False, simplify_single=True):
    if flush:
      self._dev._tio.pub_flush()
    if samples==0:
      while True:
        self._dev._tio.pub_warn_overload()
        yield self._dev._tio.stream_read_raw(samples = 1, flush=False, timeaxis=timeaxis, simplify_single=simplify_single)
    else:
      for x in range(samples):
        self._dev._tio.pub_warn_overload()
        yield self._dev._tio.stream_read_raw(samples = 1, flush=False, timeaxis=timeaxis, simplify_single=simplify_single)

  def queueSize(self):
    return self._dev._tio.pub_queue.qsize()

  def rate(self, value=None):
    if value is None:
      return self._dev._tio.protocol.streams[0]['stream_Fs'] 
    else:
      return self._dev._tio.rpc_val('data.rate', rpcType = tio.FLOAT32_T, value=value)
