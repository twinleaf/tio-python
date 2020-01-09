"""
..
Copyright 2020 Twinleaf LLC
License: MIT
"""

from typing import List
import tio
import struct

def rpc_capture_block(self, index:int = 0, blocksize:int=256, size:int=32768, typecode:str="L") -> List[float]:
  capture = []
  blocks = int(size/blocksize)
  entriesPerBlock = int(blocksize/struct.Struct('<'+typecode).size)
  packcode = "<"+str(entriesPerBlock)+typecode
  for blockindex in range(blocks):
    block = self._tio.rpc_val('capture.block', rpcType = tio.UINT16_T, value=blockindex, returnRaw = True)
    capture += struct.unpack(packcode, block)
  return capture


