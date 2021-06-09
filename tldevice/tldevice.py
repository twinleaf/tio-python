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
from .tl_cmds import *
import types
import re

class Device():
  def __init__(self, url="tcp://localhost", verbose=False, rpcs=[], stateCache=True, connectingMessage = True, send_router=None, specialize=True, timeout=False):
    self._tio = tio.TIOSession(url, verbose=verbose, rpcs=rpcs, stateCache=stateCache, connectingMessage = connectingMessage, send_router=send_router, specialize=specialize, timeout=timeout)
    self.dev = TwinleafDevInfoController(self)
    if specialize:
      self._specialize()
  
  def _specialize(self):
    if not self._tio.specialized:
      self._tio.specialize()
    self._add_sources()
    self._add_rpcs()
    if self._tio.protocol.sources != {}:
      self.data = TwinleafDataController(self)
    clean = lambda varStr: re.sub('\W|^(?=\d)','_', varStr)
    self._shortname = clean(self._tio.name).lower()

  def _interact(self):
    imported_objects = {}
    imported_objects[self._shortname] = self
    #banner = f"{self._tio.desc} REPL"
    banner=""
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

  def _add_rpc_method(parent,parentClass=None,name="test", rpcName="", rpcType=tio.FLOAT32_T, callWithValue=True, driver=None):
    def  __init__(self):
      self._tio = parent._tio
      self._rpcName = rpcName
      self._rpcType = rpcType
    def rpcCallWithValue(self, value=None):
      return self._tio.rpc_val(self._rpcName, self._rpcType, value)
    def rpcCallNoValue(self):
      return self._tio.rpc_val(self._rpcName, self._rpcType)
    if rpcName is not "":
      if driver is not None:
        cls = type(name,(), {'__init__':__init__, '__call__':driver})
      elif callWithValue:
        cls = type(name,(), {'__init__':__init__, '__call__':rpcCallWithValue})
      else:
        cls = type(name,(), {'__init__':__init__, '__call__':rpcCallNoValue})
    else:
      cls = type(name,(), {'__init__':__init__})
    clsInstance = cls()
    setattr(parentClass, name, clsInstance)

  def _add_rpc_path(self,path="this.here.command", rpcType=tio.FLOAT32_T, callWithValue=True, driver=None):
    parts = path.split('.')
    parent = self
    for part in parts[:-1]:
      if part not in vars(parent).keys():
        self._add_rpc_method(parentClass=parent, name=part)
      parent = parent.__dict__[part]
    self._add_rpc_method(parentClass=parent, name=parts[-1], rpcName=path, rpcType=rpcType, callWithValue=callWithValue, driver=driver)

  def _add_rpcs(self):
    sorted_rpcs = self._tio.rpcs
    sorted_rpcs.sort(key=lambda x:x['name']) # Make sure x() is registered before x.offset()
    for rpc in sorted_rpcs:
      if rpc['valid']:
        self._add_rpc_path(path=rpc['name'], rpcType=rpc['datatype'], callWithValue=rpc['w'])
      else:
        # print(f"Invalid metadata: {rpc['name']}")
        # Look for special driver with the name of the rpc
        rpcdrivername = 'rpc_'+rpc['name'].replace('.','_')
        if rpcdrivername in globals():
          rpcdriver = globals()[rpcdrivername]
          self._add_rpc_path(path=rpc['name'], rpcType=rpc['datatype'], callWithValue=rpc['w'], driver=rpcdriver)
        else:
          self._tio.logger.debug(f"Unimplemented RPC: {rpc['name']}")

  def _add_source_method(parent, parentClass=None, name="test", sourceName=""):
    def __init__(self):
      self._tio = parent._tio
      self._sourceName = sourceName
    def __call__(self, samples=1, duration=None, flush=True, timeaxis=False):
      return self._tio.stream_read_topic(self._sourceName, samples=samples, duration=duration, flush=flush, timeaxis=timeaxis)
    def rate(self):
      return self._tio.source_rate(self._sourceName)
    def columnnames(self):
      return self._tio.stream_topic_columnnames(self._sourceName)
    if sourceName is not "":
      cls = type(name,(), {'__init__':__init__, '__call__':__call__, 'rate':rate, 'columnnames':columnnames})
    else:
      cls = type(name,(), {'__init__':__init__})
    clsInstance = cls()
    setattr(parentClass, name, clsInstance)

  def _add_source_path(self, path="that.stream"):
    parts = path.split('.')
    parent = self
    for part in parts[:-1]:
      if part not in vars(parent).keys():
        self._add_source_method(parentClass=parent, name=part)
      parent = parent.__dict__[part]
    self._add_source_method(parentClass=parent, name=parts[-1], sourceName=path)

  def _add_sources(self):
    for source in self._tio.protocol.sources.values():
      self._add_source_path(path=source['source_name'])

  def _close(self):
    self._tio.close()

if __name__ == "__main__":
  device = Device()
  device._interact()