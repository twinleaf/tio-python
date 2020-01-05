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

  def hash(self):
    return self._dev._tio.rpc('dev.firmware.hash').decode('utf-8')

  def serial(self):
    return self._dev._tio.rpc('dev.firmware.serial').decode('utf-8')


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

  def desc(self):
    return self._dev._tio.rpc('dev.desc').decode('utf-8')

  def name(self, value = None):
    return self._dev._tio.rpc_val('dev.name', rpcType = tio.STRING_T, value = value)

  def model(self):
    return self._dev._tio.rpc('dev.model').decode('utf-8')

  def revision(self):
    return self._dev._tio.rpc_val('dev.revision', rpcType = tio.UINT16_T)

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