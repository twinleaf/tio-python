#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf Generic Device Control
Copyright 2017 Twinleaf LLC
License: MIT

"""

import tio
from .tl_cmd_conf import *
from .tl_cmd_devinfo import *
import types

class Device():
  def __init__(self, url="tcp://localhost"):
    self._tio = tio.session(url)
    self._add_rpcs()
    self._add_dstreams()
    self.conf = TwinleafConfigController(self)
    self.dev = TwinleafDevInfoController(self)
    self._longname = self.dev.desc()
    self._shortname = self.dev.name().lower()

  def _interact(self):
    imported_objects = locals()
    imported_objects[self._shortname] = self
    banner = f"{self._longname} REPL"
    exit_msg = f"{self._shortname} thanks you."
    try:
      from IPython import embed
      embed(
        user_ns=imported_objects, 
        banner1=banner, 
        banner2=f"Use   : {self._shortname}.<tab>",
        exit_msg=exit_msg)
    except ImportError:
      import code
      repl = code.InteractiveConsole(locals=imported_objects)
      repl.interact(
        banner=banner, 
        exitmsg = exit_msg)

  def _add_rpc_method(parent,parentClass=None,name="test", rpcName="", rpcType=tio.FLOAT32_T, callWithValue=True):
    def  __init__(self):
      self._tio = parent._tio
      self._rpcName = rpcName
      self._rpcType = rpcType
    def rpcCallWithValue(self, value=None):
      return self._tio.rpc_val(self._rpcName, self._rpcType, value)
    def rpcCallNoValue(self):
      return self._tio.rpc_val(self._rpcName, self._rpcType)
    if rpcName is not "":
      if callWithValue:
        cls = type(name,(), {'__init__':__init__, '__call__':rpcCallWithValue})
      else:
        cls = type(name,(), {'__init__':__init__, '__call__':rpcCallNoValue})
    else:
      cls = type(name,(), {'__init__':__init__})
    clsInstance = cls()
    setattr(parentClass, name, clsInstance)

  def _add_rpc_path(self,path="this.here.command", rpcType=tio.FLOAT32_T, callWithValue=True):
    parts = path.split('.')
    parent = self
    for part in parts[:-1]:
      if part not in vars(parent).keys():
        self._add_rpc_method(parentClass=parent, name=part)
      parent = parent.__dict__[part]
    self._add_rpc_method(parentClass=parent, name=parts[-1], rpcName=path, rpcType=rpcType, callWithValue=callWithValue)

  def _add_rpcs(self):
    sorted_rpcs = self._tio.rpcs
    sorted_rpcs.sort(key=lambda x:x['name']) # Make sure x() is registered before x.offset()
    for rpc in sorted_rpcs:
      if rpc['valid']:
        self._add_rpc_path(path=rpc['name'], rpcType=rpc['datatype'], callWithValue=rpc['w'])

  def _add_dstream_method(parent, parentClass=None, name="test", dstreamName=""):
    def __init__(self):
      self._tio = parent._tio
      self._dstreamName = dstreamName
    def __call__(self, samples=1, duration=None):
      return self._tio.dstream(self._dstreamName, samples, duration)
    def subscribe(self):
      return self._tio.dstream_subscribe(self._dstreamName)
    def unsubscribe(self):
      return self._tio.dstream_unsubscribe(self._dstreamName)
    if dstreamName is not "":
      cls = type(name,(), {'__init__':__init__, '__call__':__call__, 'subscribe':subscribe, 'unsubscribe':unsubscribe })
    else:
      cls = type(name,(), {'__init__':__init__})
    clsInstance = cls()
    setattr(parentClass, name, clsInstance)

  def _add_dstream_path(self, path="that.stream"):
    parts = path.split('.')
    parent = self
    for part in parts[:-1]:
      if part not in vars(parent).keys():
        self._add_dstream_method(parentClass=parent, name=part)
      parent = parent.__dict__[part]
    self._add_dstream_method(parentClass=parent, name=parts[-1], dstreamName=path)

  def _add_dstreams(self):
    for dstream in self._tio.dstreams:
      self._add_dstream_path(path=dstream['name'])


if __name__ == "__main__":
  device = Device()
  device._interact()