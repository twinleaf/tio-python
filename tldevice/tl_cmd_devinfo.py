"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com
    OriginalDate: March 2017
"""

import struct
import yaml
import tio
from .tl_cmd_conf import *

class TwinleafDevFirmwareInfoController(object):
  def __init__(self, dev):
    self._dev = dev

  def rev(self):
    return self._dev._tio.rpc('dev.firmware.rev').decode('utf-8')

  def tstamp(self):
    return self._dev._tio.rpc_val('dev.firmware.tstamp', rpcType = tio.UINT32_T)

  def osver(self):
    return self._dev._tio.rpc_val('dev.firmware.osver', rpcType = tio.UINT16_T)


class TwinleafDevInfoController(object):
  def __init__(self, dev):
    self._dev = dev
    self.conf = TwinleafConfigController(dev)
    self.firmware = TwinleafDevFirmwareInfoController(dev)

  def lock(self, value = None):
    return self._dev._tio.rpc_val('dev.lock', rpcType = tio.UINT8_T, value = value)

  def unlock(self, value = None):
    return self._dev._tio.rpc_val('dev.unlock', rpcType = tio.UINT8_T, value = value)

  def systime(self):
    return self._dev._tio.rpc_val('dev.systime', rpcType = tio.UINT64_T)

  def loglevel(self, value = None):
    return self._dev._tio.rpc_val('dev.loglevel', rpcType = tio.UINT8_T, value = value)

  def name(self):
    return self._dev._tio.rpc('dev.name').decode('utf-8')

  def desc(self):
    return self._dev._tio.rpc('dev.desc').decode('utf-8')

  def serial(self):
    return self._dev._tio.rpc('dev.serial').decode('utf-8')

  def revision(self):
    return self._dev._tio.rpc_val('dev.revision', rpcType = tio.UINT16_T)

  def uid(self):
    return self._dev._tio.rpc('dev.uid').hex()

  def mcu_id(self):
    return self._dev._tio.rpc('dev.mcu.id').hex()

  def session(self):
    return self._dev._tio.rpc('dev.session').hex()



# Test
"""
csb.dev.lock()
csb.dev.unlock()
csb.dev.systime()
csb.dev.loglevel()
csb.dev.name()
csb.dev.id()
csb.dev.version_major()
csb.dev.version_minor()
csb.dev.desc()
csb.dev.uid()
csb.dev.mcu_id()
csb.dev.session()

csb.dev.firmware.rev()
csb.dev.firmware.tstamp()
csb.dev.firmware.osver()

csb.dev.port.id()
csb.dev.port.boot_mode()
csb.dev.port.mode()
csb.dev.port.outputs()
csb.dev.port.inputs()
csb.dev.port.discover()


"""