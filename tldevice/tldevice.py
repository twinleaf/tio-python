#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf Generic Device Control
Copyright 2017 Twinleaf LLC
License: MIT

"""

import tio
from .tl_cmd_devinfo import *
from .tl_cmd_data import *
import types

class Device():
  def __init__(self, url="tcp://localhost", verbose=False, commands=[]):
    self._tio = tio.session(url, verbose=verbose, commands=commands)
    self.dev = TwinleafDevInfoController(self)
    self._add_pstreams()
    self._add_rpcs()
    if self._tio.pstreams != {}:
      self.data = TwinleafDataController(self)
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

  def _add_pstream_method(parent, parentClass=None, name="test", pstreamName=""):
    def __init__(self):
      self._tio = parent._tio
      self._pstreamName = pstreamName
    def __call__(self, samples=1, duration=None):
      return self._tio.dstream_read_topic(self._pstreamName, samples, duration)
    #def rate(self):
    #  return self._tio_pstream_rate(self._dstreamName)
    if pstreamName is not "":
      cls = type(name,(), {'__init__':__init__, '__call__':__call__}) #, 'rate':rate
    else:
      cls = type(name,(), {'__init__':__init__})
    clsInstance = cls()
    setattr(parentClass, name, clsInstance)

  def _add_pstream_path(self, path="that.stream"):
    parts = path.split('.')
    parent = self
    for part in parts[:-1]:
      if part not in vars(parent).keys():
        self._add_pstream_method(parentClass=parent, name=part)
      parent = parent.__dict__[part]
    self._add_pstream_method(parentClass=parent, name=parts[-1], pstreamName=path)

  def _add_pstreams(self):
    for pstream in self._tio.pstreams.values():
      self._add_pstream_path(path=pstream['pstream_name'])

if __name__ == "__main__":
  device = Device()
  device._interact()