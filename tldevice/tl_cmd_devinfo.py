"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com
    OriginalDate: March 2017
"""

import struct
import yaml
import tio

class TwinleafDevInfoController(object):
  def __init__(self, dev):
    self._dev = dev

  def desc(self):
    return self._dev._tio.rpc('dev.desc').decode('utf-8')

  def name(self):
    return self._dev._tio.rpc('dev.name').decode('utf-8')

  def id(self):
    return self._dev._tio.rpc_val('dev.id', rpcType = tio.UINT16_T)

  def lock(self, value = None):
    return self._dev._tio.rpc_val('dev.lock', rpcType = tio.UINT8_T, value = value)

  def loglevel(self, value = None):
    return self._dev._tio.rpc_val('dev.loglevel', rpcType = tio.UINT8_T, value = value)

  def mcu_loglevel(self, value = None):
    return self._dev._tio.rpc_val('dev.mcu.loglevel', rpcType = tio.UINT8_T, value = value)

  def mcu_fw_rev(self):
    return self._dev._tio.rpc('dev.mcu.fw_rev').decode('utf-8')

  def mcu_fw_time(self):
    return self._dev._tio.rpc_val('dev.mcu.fw_time', rpcType = tio.UINT32_T)

  def mcu_id(self):
    return self._dev._tio.rpc('dev.mcu.id').hex()

  def systime(self):
    return self._dev._tio.rpc_val('dev.systime', rpcType = tio.UINT64_T)

  def version(self):
    return self._dev._tio.rpc_val('dev.version', rpcType = tio.UINT16_T)

  def minor_version(self):
    return self._dev._tio.rpc_val('dev.minor_version', rpcType = tio.UINT16_T)

# Test
"""
csb.dev.desc()
csb.dev.name()
csb.dev.id()
#csb.dev.lock()
csb.dev.loglevel()
csb.dev.mcu_loglevel()
csb.dev.mcu_fw_rev()
csb.dev.mcu_fw_time()
csb.dev.systime()
csb.dev.version()
csb.dev.minor_version()
"""