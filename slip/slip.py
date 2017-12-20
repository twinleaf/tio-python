#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf Generic Device Control
Copyright 2017 Twinleaf LLC
License: MIT

"""
import binascii
import struct

SLIP_END = 0xC0
SLIP_END_CHAR = b"\xC0"
SLIP_ESC = 0xDB
SLIP_ESC_END = 0xDC
SLIP_ESC_ESC = 0xDD
SLIP_MAX_LEN = 2048

class SLIPEncodingError(IOError):
    pass

def decode(slipbuf):
  if len(slipbuf) < 4:
    raise SLIPEncodingError("Packet too short")
  msg = bytearray()
  rx_esc_next = False
  for byte in slipbuf:
    if rx_esc_next:
      rx_esc_next = False
      if byte == SLIP_ESC_END:
        msg.append(SLIP_END)
      elif byte == SLIP_ESC_ESC:
        msg.append(SLIP_ESC)
      else:
        raise SLIPEncodingError("Corrupt SLIP stream: SLIP_ESC not followed by valid escape code")
    elif byte == SLIP_ESC:
      rx_esc_next = True
    elif byte == SLIP_END:
      # Should have already been framed by SLIP_END
      #raise SLIPEncodingError("Corrupt SLIP stream: SLIP_END in packet")
      pass
    else:
      msg.append(byte)
  msg_checksum = struct.unpack("<I", msg[-4:])[0]
  msg = msg[:-4]
  checksum = binascii.crc32(msg)
  if msg_checksum != checksum:
    raise SLIPEncodingError("CRC32 invalid")
  return msg

def encode(msg):
  checksum = binascii.crc32(msg)
  msg += struct.pack("<I", checksum)
  slipbuf = bytearray()
  slipbuf.append(SLIP_END)
  for c in msg:
    if c == SLIP_END:
      slipbuf.append(SLIP_ESC)
      slipbuf.append(SLIP_ESC_END)
    elif c == SLIP_ESC:
      slipbuf.append(SLIP_ESC)
      slipbuf.append(SLIP_ESC_ESC)
    else:
      slipbuf.append(c)
  slipbuf.append(SLIP_END)
  return slipbuf

if __name__=="__main__":
  test = b"Hi\xC0Yo\xDB"
  print(test == decode(encode(test)))