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
  def __init__(self, url="tcp://localhost", verbose=False, rpcs=[], stateCache=True, connectingMessage = True, connectionTime = 1):
    self._routes = {}
    self._routes["/"] = tldevice.Device(url=url, verbose=verbose, rpcs=rpcs, stateCache=stateCache, connectingMessage=connectingMessage)
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
    self.__dict__[self._routes[routingKey]._shortname] = self._routes[routingKey]

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

  def syncStreamsStart(self, syncStreams = [], flush=True):
    # Find the initial datum time
    times = []
    data = []
    for stream in syncStreams:
      row = stream(samples=1, flush=flush, timeaxis=True)
      times += [row[0]]
      data += row[1:]

    # Ensure the times match up!
    # If not, catch up on the streams that are behind
    maxtime = max(times)
    mintime = min(times)
    if maxtime != mintime:
      for i,stream in enumerate(syncStreams):
        max_deviation = 0
        while times[i] < starttime:
          row = stream(samples=1, flush=False, timeaxis=True)
          times[i] += [row[0]]
          max_deviation -= 1
          if max_deviation > 5:
            raise "Can't sync stream!"
    return syncStreams

  def syncStreamsRead(self, syncStreams = [], samples = 1, duration=None, timeaxis=True):
    # Acquire data
    times = []
    data = [] 
    for stream in syncStreams:
      streamdata = stream(samples=samples, duration=duration, flush=False, timeaxis=True)
      times += [streamdata[0]]
      data += streamdata[1:]
    
    starttimes = [timecol[0] for timecol in times]
    if max(starttimes) != min(starttimes):
      raise "Streams out of sync!"
    
    if timeaxis:
      data = [times[0]] + data

    return data
    
if __name__ == "__main__":
  device = DeviceSync()
  device._interact()