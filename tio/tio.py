#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf IO (tio) - A serialization for instrumentation
Copyright 2017 Twinleaf LLC
License: MIT

A simple protocol for working with sensors through single-port/serial connections.
"""

import socket
import struct
import random
import urllib.parse
import signal # Timeout; NB: not OK for multithreaded applications

TL_PTYPE_NONE       = 0
TL_PTYPE_INVALID    = 0
TL_PTYPE_LOG        = 1 # Log messages
TL_PTYPE_RPC_REQ    = 2 # RPC request
TL_PTYPE_RPC_REP    = 3 # RPC reply
TL_PTYPE_RPC_ERROR  = 4 # RPC error
TL_PTYPE_STREAMDESC = 5 # Description of data in a stream
TL_PTYPE_USER       = 6
TL_PTYPE_STREAM0    = 128

TL_RPC_ERRORS = [ \
  'TL_RPC_ERROR_NONE'      , #  0 No error condition
  'TL_RPC_ERROR_UNDEFINED' , #  1 No error code for this error, check message
  'TL_RPC_ERROR_NOTFOUND'  , #  2 Call to a nonexistent (or disabled) RPC
  'TL_RPC_ERROR_MALFORMED' , #  3 Malformed req packet
  'TL_RPC_ERROR_ARGS_SIZE' , #  4 Arguments have the wrong size
  'TL_RPC_ERROR_INVALID'   , #  5 Arguments values invalid
  'TL_RPC_ERROR_READ_ONLY' , #  6 Attempted to assign a value to RO variable
  'TL_RPC_ERROR_WRITE_ONLY', #  7 Attempted to read WO variable
  'TL_RPC_ERROR_TIMEOUT'   , #  8 Internal timeout condition
  'TL_RPC_ERROR_BUSY'      , #  9 Busy to perform this operation. try again
  'TL_RPC_ERROR_STATE'     , # 10 Wrong state to perform this operation.
  'TL_RPC_ERROR_LOAD'      , # 11 Error loading conf.
  'TL_RPC_ERROR_LOAD_RPC'  , # 12 Error auto RPCs after load.
  'TL_RPC_ERROR_SAVE'      , # 13 Error preparing conf to save.
  'TL_RPC_ERROR_SAVE_WR'   , # 14 Error saving conf to eeprom
  'TL_RPC_ERROR_INTERNAL'  , # 15 Firmware internal error.
  'TL_RPC_ERROR_NOBUFS'    , # 16 No buffers available to complete operation
  'TL_RPC_ERROR_USER'      , # 17 Start value to define per-RPC error codes
]


UINT8_T =      0x10
INT8_T =       0x11
UINT16_T =     0x20
INT16_T =      0x21
UINT24_T =     0x30
INT24_T =      0x31
UINT32_T =     0x40
INT32_T =      0x41
UINT64_T =     0x80
INT64_T =      0x81
FLOAT32_T =    0x42
FLOAT64_T =    0x82
NONE_T =       0x00

TYPES = {
    NONE_T:    ("",  "",     0),
    UINT8_T:   ("B", "u8",   1),
    INT8_T:    ("b", "i8",   1),
    UINT16_T:  ("H", "u16",  2),
    INT16_T:   ("h", "i16",  2),
    #UINT24_T: ("",  "u24",  3),
    #INT24_T:  ("",  "i24",  3),
    UINT32_T:  ("I", "u32",  4),
    INT32_T:   ("i", "i32",  4),
    UINT64_T:  ("Q", "u64",  8),
    INT64_T:   ("q", "i64",  8),
    FLOAT32_T: ("f", "f32",  4),
    FLOAT64_T: ("d", "f64",  8),
}

TL_PACKET_MAX_SIZE = 512
TL_PACKET_MAX_ROUTING_SIZE = 8

class TLRPCException(Exception):
    pass

class session(object):
  def __init__(self, url="tcp://localhost", verbose = False):
    uri = urllib.parse.urlparse(url)
    address = uri.hostname
    port = uri.port
    if port is None:
      port = 7855
    self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    self.socket.connect((address, port))
    self.socket.settimeout(0) # Non-blocking mode
    self.rpcs = []
    self.rpcNames = {}
    self.dstreams = []
    self.dstreamNames = {}
    self.verbose = verbose

    # Timeout
    self.timeout = 2 # seconds
    signal.signal(signal.SIGALRM, self._soft_timeout_handler)

    # Query rpcs and dstreams
    # TODO: Caching!
    self.rpcList()
    self.dstreamList()
    #print(f"Found {len(self.rpcs)} RPCs and {len(self.dstreams)} data streams")


  def _soft_timeout_handler(self, signum, frame):
    raise TimeoutError()

  def flush(self):
    signal.alarm(self.timeout)
    while True:
      try:
        data = self.socket.recv(8192)
      except:
        signal.alarm(0)
        break
      if not data:
        signal.alarm(0)
        break

  def recv(self):
    try:
      header = self.socket.recv(4)
    except BlockingIOError:
      return { 'type':TL_PTYPE_NONE }
    headerFields = struct.unpack("<BBH", bytes(header) )
    payloadType, routingSize, payloadSize = headerFields
    if payloadSize > TL_PACKET_MAX_SIZE or routingSize>TL_PACKET_MAX_ROUTING_SIZE:
      return { 'type':TL_PTYPE_INVALID }
    payload = self.socket.recv(payloadSize+routingSize)
    parsedPacket = { 'type':payloadType }

    if payloadType == TL_PTYPE_LOG: # Log message
      logMessage = payload.decode('utf-8')
      parsedPacket['message'] = logMessage
      if self.verbose:
        print("LOG: " + logMessage)

    elif payloadType == TL_PTYPE_RPC_REP: # Got reply
      requestID = struct.unpack("<H", bytes(payload[:2]) )[0]
      replyPayload = payload[2:]
      parsedPacket['requestid'] = requestID
      parsedPacket['payload'] = replyPayload
      if self.verbose:
        print(f"REP (ID 0x{requestID:04x}): {replyPayload}")

    elif payloadType == TL_PTYPE_RPC_ERROR: # Got reply error
      requestID, errorCode = struct.unpack("<HH", bytes(payload[:4]) )
      errorPayload = payload[4:]
      parsedPacket['requestid'] = requestID
      parsedPacket['error'] = errorCode
      parsedPacket['payload'] = errorPayload
      if self.verbose:
        print(f"REP (ID 0x{requestID:04x}) Error {errorCode}: ")

    elif payloadType == TL_PTYPE_STREAMDESC: # Got stream description
      parsedPacket['version'] = struct.unpack("<H", bytes(payload[:2]) )[0]
      if parsedPacket['version'] == 0:
        streamDescription = struct.unpack("<HHQQIIBBHHBB", bytes(payload[:36]) )
        parsedPacket['version']            = int(streamDescription[0])
        parsedPacket['streamID']           = int(streamDescription[1])
        parsedPacket['start_ts']           = int(streamDescription[2])
        parsedPacket['sample_counter']     = int(streamDescription[3])
        parsedPacket['period_numerator']   = int(streamDescription[4])
        parsedPacket['period_denominator'] = int(streamDescription[5])
        parsedPacket['flags']              = int(streamDescription[6])
        parsedPacket['tstamp_type']        = int(streamDescription[7])
        parsedPacket['restartID']          = int(streamDescription[8])
        parsedPacket['sample_size']        = int(streamDescription[9])
        parsedPacket['dtype_code']         = int(streamDescription[10])
        parsedPacket['channels']           = int(streamDescription[11])
        parsedPacket['name'] = payload[36:].decode('utf-8')
      else:
        raise NotImplementedError(f"Version {parsedPacket['version']} not implemented")
      # Derived values
      parsedPacket['payload_type'] = parsedPacket['streamID']+128
      parsedPacket['dtype'] = TYPES[parsedPacket['dtype_code']][1]
      parsedPacket['dtype_pack'] = TYPES[parsedPacket['dtype_code']][0]
      parsedPacket['dtype_bytes'] = TYPES[parsedPacket['dtype_code']][2]
      if parsedPacket['period_denominator'] is not 0 and parsedPacket['period_numerator'] is not 0:
        parsedPacket['period'] = 1e-6*parsedPacket['period_numerator'] / parsedPacket['period_denominator']
      else:
        parsedPacket['period'] = 0
      if parsedPacket['period'] is not 0:
        parsedPacket['Fs'] = 1/parsedPacket['period']
      else:
        parsedPacket['Fs'] = 0
      self.dstreams[parsedPacket['streamID']] = parsedPacket
      self.dstreamNames[parsedPacket['name']] = parsedPacket['streamID']
      if self.verbose:
        print(f"DSD (ID {parsedPacket['streamID']}): {parsedPacket['name']}")

    elif payloadType >= TL_PTYPE_STREAM0: # Data stream
      sampleNumber = struct.unpack("<I", bytes(payload[0:4]) )[0]
      data = payload[4:]
      parsedPacket['sampleNumber'] = sampleNumber
      parsedPacket['rawdata'] = data
      if self.verbose:
        print(f"Data stream #{payloadType}, Sample #{sampleNumber}")

    else:
      if self.verbose:
        print("ERROR: Unknown packet type")

    return parsedPacket

  def send_req(self, topic = "dev.desc", payload = None):
    if type(topic) is str:
      topic = topic.encode('utf-8')
    requestID = random.randint(0,0xFFFF)
    methodID = len(topic) + 0x8000 # Set high bit and use length for named method
    requestHeader = struct.pack("<HH", requestID, methodID )
    msg = requestHeader + topic
    if payload is not None:
      msg += payload
    header = struct.pack("<BBH", TL_PTYPE_RPC_REQ, 0, len(msg) )
    msg = header + msg
    self.socket.send(msg)
    if self.verbose:
      print(f"REQ (ID 0x{requestID:04x}): {topic}")
    return requestID

  def recv_rep(self, requestID = None):
    signal.alarm(self.timeout)
    while True:
      parsedPacket = self.recv()
      if parsedPacket['type'] == TL_PTYPE_RPC_REP \
          or parsedPacket['type'] == TL_PTYPE_RPC_ERROR:
        if requestID is None or requestID == parsedPacket['requestid']:
          # Got something; turn off timeout
          signal.alarm(0)
          if parsedPacket['type'] == TL_PTYPE_RPC_ERROR:
            raise TLRPCException( TL_RPC_ERRORS[parsedPacket['error']] )
          if parsedPacket['payload'] == b'':
            return None
          else:
            return parsedPacket['payload']

  def rpc(self, topic = "dev.desc", payload = None, flush=True):
    self.flush()
    requestID = self.send_req(topic, payload)
    try: 
      return self.recv_rep(requestID)
    except TLRPCException as rpc_error:
      print( f"RPC ERROR {topic}: {rpc_error}" )

  def rpc_val(self, topic = "dstream.list", rpcType = FLOAT32_T, value = None):
    if value is not None:
      reqPayload = struct.pack("<"+TYPES[rpcType][0], value)
    else:
      reqPayload = None
    reply = self.rpc(topic, reqPayload)
    if reply is not None:
      if len(reply) > 0:
        return struct.unpack("<"+TYPES[rpcType][0], reply)[0]
    return None

  def rpc_string(self, topic = "dev.desc", payload = None):
    if payload is not None and payload is not "":
      payload = payload.encode('utf-8')
    return self.rpc(topic, payload).decode('utf-8')
  
  def rpcList(self):
    self.rpcs = []
    rpcCount = self.rpc_val("rpc.list", UINT32_T)
    for rpcNumber in range(rpcCount):
      rpcInfo = self.rpc("rpc.listinfo", struct.pack("<"+TYPES[UINT32_T][0], rpcNumber))
      rpcType = rpcInfo[0]
      rpcFlags = rpcInfo[1]
      rpcName = rpcInfo[2:].decode('utf-8')
      rpcMetadataValid = rpcFlags & 0x80 == 0x80
      rpcWritable = rpcFlags & 0x1 == 0x1
      rpcReadable = rpcFlags & 0x2 == 0x2
      rpcStored = rpcFlags & 0x4 == 0x4
      self.rpcNames[rpcName] = rpcNumber
      self.rpcs += [{
        "name":rpcName, 
        "datatype":rpcType, 
        "r":rpcReadable, 
        "w":rpcWritable, 
        "valid":rpcMetadataValid, 
        "stored":rpcStored
      }]
      #print(f"{rpcNumber}: {rpcName}, {rpcType}, {rpcReadable}, {rpcWritable}, {rpcMetadataValid}")
    #self.rpcs.sort(key=lambda x:x['name'])
    return self.rpcs

  def dstreamList(self):
    dstreamCount = self.rpc_val("dstream.list", UINT32_T)
    self.dstreams = [None] * dstreamCount
    for dstreamNumber in range(dstreamCount):
      self.rpc_val("dstream.senddesc", UINT16_T, dstreamNumber)
      #print(f"DS{dstreamNumber}: {self.dstreams[dstreamNumber]['name']}")
    return self.dstreams

  def dstream_samples(self, topic, samples = 10):
    dstreamInfo = self.dstreams[self.dstreamNames[topic]]
    channels = dstreamInfo['channels']
    data_flat = []
    while True:
      parsedPacket = self.recv()
      if parsedPacket['type'] == dstreamInfo['payload_type']:
        packet_samples = int(len(parsedPacket['rawdata']) / dstreamInfo['dtype_bytes'])
        data_flat += struct.unpack("<"+packet_samples*dstreamInfo['dtype_pack'], bytes(parsedPacket['rawdata']) )
        if int(len(data_flat)/channels) >= samples: 
          break
    data_flat = data_flat[:channels*samples] # truncate at specified point
    data = [[row for row in data_flat[column::channels]] for column in range(channels)] # group data by channel
    if samples == 1:
      data = [datum[0] for datum in data]
    if len(data) == 1:
      data = data[0]
    return data

  def dstream_subscribe(self, topic):
    dstreamInfo = self.dstreams[self.dstreamNames[topic]]
    self.rpc_val('dstream.subscribe', UINT16_T, dstreamInfo['streamID'])

  def dstream_unsubscribe(self, topic):
    dstreamInfo = self.dstreams[self.dstreamNames[topic]]
    self.rpc_val('dstream.unsubscribe', UINT16_T, dstreamInfo['streamID'])

  def dstream(self, topic, samples = 1, duration = None, autoSubscribe = True):
    if autoSubscribe:
      self.dstream_subscribe(topic)
    dstreamInfo = self.dstreams[self.dstreamNames[topic]]
    if duration is not None:
      samples = int(duration * dstreamInfo['Fs'])
    data = self.dstream_samples(topic, samples)
    if autoSubscribe:
      self.dstream_unsubscribe(topic)
    return data


if __name__ == "__main__":
  vm4 = Device()
  #vm4.dstream_enable('gmr.cal', True)
  data = vm4.dstream('gmr.cal', duration = 0.1)
  print(data)
