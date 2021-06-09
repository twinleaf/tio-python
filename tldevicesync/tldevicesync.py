#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf Generic Multi Device Control
Copyright 2019 Twinleaf LLC
License: MIT
"""

import tldevice
import threading
import time

class DeviceSync():
  def __init__(self, url="tcp://localhost", verbose=False, rpcs=[], stateCache=True, connectingMessage = True, connectionTime = 1, timeout = False):
    self._routes = {}
    self._routes["/"] = tldevice.Device(url=url, verbose=verbose, rpcs=rpcs, stateCache=stateCache, connectingMessage=connectingMessage, timeout = timeout)
    self._routes["/"]._tio.recv_router = self._recvRouter
    self.__dict__[self._routes["/"]._shortname] = self._routes["/"]
    time.sleep(connectionTime)

  def _recvRouter(self, routing, packet):
    routingKey = '/'.join(map(str,routing))
    if routingKey in self._routes.keys():
        self._routes[routingKey]._tio.recv_queue.put(packet)
    else: # Create new route
      #print(f"Creating route to {routingKey}.")
      self._routes[routingKey] = tldevice.Device(url="router://interthread/"+routingKey, send_router = self._routes["/"]._tio.send, verbose=True, specialize=False)
      threading.Thread(target=self._specialize, args=(routingKey,)).start()

  def _specialize(self, routingKey):
    self._routes[routingKey]._specialize()
    self._routes[routingKey]._shortname += routingKey
    #self._routes[routingKey]._tio.shortname = self._routes[routingKey]._shortname
    self.__dict__[self._routes[routingKey]._shortname.replace("/","")] = self._routes[routingKey]

  def _interact(self):
    imported_objects = {}
    imported_objects['tio'] = self
    banner=""
    exit_msg = f"tio thanks you."
    try:
      from IPython import embed
      embed(
        user_ns=imported_objects, 
        banner1=banner, 
        banner2=f"Use   : tio.<tab>",
        exit_msg=exit_msg)
    except ImportError:
      import code
      repl = code.InteractiveConsole(locals=imported_objects)
      repl.interact(
        banner=banner, 
        exitmsg = exit_msg)

class SyncStream():
  def __init__(self, streams = []):
    self.streams = streams

  def sync(self, flush=True):
    # Find the initial datum time
    times = []
    data = []
    for stream in self.streams:
      row = stream(samples=1, flush=flush, timeaxis=True)
      times += [row[0]]
      data += row[1:]

    # Ensure the times match up!
    # If not, catch up on the streams that are behind
    maxtime = max(times)
    mintime = min(times)
    if maxtime != mintime:
      for i,stream in enumerate(self.streams):
        max_deviation = 0
        while times[i] < maxtime:
          print(f"Drop a sample on stream {i}")
          times[i] = stream(samples=1, flush=False, timeaxis=True)[0]
          max_deviation -= 1
          if max_deviation > 5:
            raise Exception("Can't sync stream!")

  def read(self, samples = 1, duration=None, timeaxis=True, sync=True):
    if sync:
      self.sync()

    # Acquire data
    times = []
    data = [] 
    for stream in self.streams:
      streamdata = stream(samples=samples, duration=duration, flush=False, timeaxis=True)
      times += [streamdata[0]]
      data += streamdata[1:]
    
    if samples == 1:
      starttimes = times
    else:
      starttimes = [timecol[0] for timecol in times]

    if max(starttimes) != min(starttimes):
      delta = max(starttimes) - min(starttimes)
      raise Exception(f"Streams out of sync by {delta}!")
    
    if timeaxis:
      data = [times[0]] + data

    return data
    
  def columnnames(self, timeaxis=True):
    # TODO: Get resource shortname + routing; vmr0.vector.x
    names = []
    for stream in self.streams:
      names += stream.columnnames()
    if timeaxis:
      names = ["time"] + names
    return names

  def iter(self, samples=0, sync=True):
    if sync:
      yield self.read(samples = 1, sync=sync)
      samples -= 1
    if samples<=0:
      while True:
        yield self.read(samples = 1, sync=False)
    else:
      for x in range(number):
        yield self.read(samples = 1, sync=False)
  
if __name__ == "__main__":
  device = DeviceSync()
  device._interact()