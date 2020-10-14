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
  def __init__(self, url="tcp://localhost", verbose=False, rpcs=[], rpcsSync=[], stateCache=True, connectingMessage = True, connectionTime = 1):
    self._routes = {}
    self._routes["/"] = tldevice.Device(url=url, verbose=verbose, rpcs=rpcsSync, stateCache=stateCache, connectingMessage=connectingMessage)
    self._routes["/"]._tio.recv_router = self._recvRouter
    self.__dict__[self._routes["/"]._shortname] = self._routes["/"]
    self.rpcs = rpcs
    time.sleep(connectionTime)

  def _recvRouter(self, routing, packet):
    routingKey = '/'.join(map(str,routing))
    if routingKey in self._routes.keys():
        self._routes[routingKey]._tio.recv_queue.put(packet)
    else: # Create new route
      #print(f"Creating route to {routingKey}.")
      self._routes[routingKey] = tldevice.Device(url="router://interthread/"+routingKey, send_router = self._routes["/"]._tio.send, rpcs=self.rpcs, verbose=True, specialize=False)
      threading.Thread(target=self._specialize, args=(routingKey,)).start()

  def _specialize(self, routingKey):
    self._routes[routingKey]._specialize(stateCache=False)
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
  def __init__(self, devices = [], streams = []):
    for device in devices:
      if not isinstance(device, tldevice.Device):
        raise Exception("Not a valid device")
    self.devices = devices
    self.streams = streams

  def sync(self, flush=True):
    # Find the initial datum time
    times = []
    for device in self.devices:
      time, row = device._tio.stream_read_raw(flush=True, timeaxis=False)
      times.append(time)

    # Ensure the times match up!
    # If not, catch up on the devices that are behind
    maxtime = max(times)
    mintime = min(times)
    if maxtime != mintime:
      for i,device in enumerate(self.devices):
        max_deviation = 0
        while times[i] < maxtime:
          print(f"Drop a sample from stream {i}")
          times[i] = device._tio.stream_read_raw(flush=False)[0]
          max_deviation += 1
          # if max_deviation > 5:
          #   raise Exception("Can't sync stream!")

  def read(self, sync=True, parse=False):
    if sync:
      self.sync()

    # Acquire data
    streamdata = {}
    starttimes = []
    for device in self.devices:
      time, data = device._tio.stream_read_raw(flush=False)
      parsedData = device._tio.get_topics_from_data(data, self.streams)
      streamdata[device._shortname] = parsedData
      starttimes.append(time)
    
    if max(starttimes) != min(starttimes):
      delta = max(starttimes) - min(starttimes)
      self.sync()
      print(f"Streams out of sync by {delta}!")
      # raise Exception(f"Streams out of sync by {delta}!")

    if parse:
      return map(lambda row: device._tio.parse_data(row), streamdata)

    return streamdata

  def iter(self, samples=0, sync=True):
    if sync:
      yield self.read(sync=True)
    counter = samples
    if counter:
      while counter > 0:
        yield self.read(sync=False)
        counter -= 1
    else:
      while True:
        yield self.read(sync=False)
  
if __name__ == "__main__":
  device = DeviceSync()
  device._interact()