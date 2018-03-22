#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf IO (tio) - A serialization for instrumentation
Copyright 2017 Twinleaf LLC
License: MIT

A simple protocol for working with sensors through single-port/serial connections.
"""

import serial
import socket
import threading
import struct
import random
import urllib.parse
import time
import math
import queue
import slip
import hexdump
import logging

TL_PTYPE_NONE       = 0
TL_PTYPE_INVALID    = 0
TL_PTYPE_LOG        = 1 # Log messages
TL_PTYPE_RPC_REQ    = 2 # RPC request
TL_PTYPE_RPC_REP    = 3 # RPC reply
TL_PTYPE_RPC_ERROR  = 4 # RPC error
TL_PTYPE_HEARTBEAT  = 5 # NOP heartbeat
TL_PTYPE_TIMEBASE   = 6 # Update to a timebase's parameters
TL_PTYPE_SOURCE     = 7 # Update to a source's parameters
TL_PTYPE_DSTREAM    = 8 # Update to a dstream's parameters
TL_PTYPE_USER       = 64
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
  def __init__(self, url="tcp://localhost", verbose=False, connectingMessage = True, commands=[]):

    if verbose:
      logLevel = logging.DEBUG
    else:
      logLevel = logging.ERROR
    logging.basicConfig(level=logLevel)
    self.logger = logging.getLogger('tio')

    # Connect to either TCP socket or serial port
    self.uri = urllib.parse.urlparse(url)
    if self.uri.scheme == "tcp":
      if self.uri.port is None:
        port = 7855
      else:
        port = self.uri.port
      routingStrings = self.uri.path.split('/')[1:]
      self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      self.socket.connect((self.uri.hostname, port))
      self.socket.settimeout(0) # Non-blocking mode
    else:
      # Try treating as serial
      # Deal with non-standard url for routing
      # linux: /dev/tty0/0/1
      # mac: /dev/cu.usbmodem1421/0/1
      # windows: COM1/0/1
      spliturl = url.split('/')
      try:
        if spliturl[0].upper().startswith('COM'): # Windows
          url = spliturl[0]
          routingStrings = spliturl[1:]
        elif spliturl[1].lower()=='dev': # *nix
          url = '/'.join(spliturl[:3])
          routingStrings = spliturl[3:]
        else:
          raise
      except:
        raise Exception("Unknown url format.")
      self.buffer = bytearray()
      self.serial = serial.serial_for_url(url, baudrate=115200, timeout=1)
      self.serial.reset_input_buffer()

    routingStrings = filter(lambda a: a != '', routingStrings)
    try:
      self.routing = [ int(address) for address in routingStrings ]
    except:
      raise Exception(f'Bad routing path: {routingString}')
    self.routingBytes = bytearray(self.routing)

    # Initialize queues and threading controls
    self.pub_queue = queue.Queue(maxsize=100)
    self.req_queue = queue.Queue(maxsize=1)
    self.rep_queue = queue.Queue(maxsize=1)
    self.lock = threading.Lock()
    self.alive = True

    # Launch socket management thread
    self.socket_recv_thread = threading.Thread(target=self.recv_thread)
    self.socket_recv_thread.daemon = True
    self.socket_recv_thread.name = 'recv-thread'
    self.socket_recv_thread.start()
    self.socket_send_thread = threading.Thread(target=self.send_thread)
    self.socket_send_thread.daemon = True
    self.socket_send_thread.name = 'send-thread'
    self.socket_send_thread.start()
      
    # TIO state
    self.rpcs = []
    self.rpcNames = {}
    self.timebases = []
    self.sources = {}
    self.dstreamInfo = None
    self.streams = []
    self.columns = []
    self.columnsByName = {}
    self.rowunpackByBytes = {}

    # Startup commands
    for command, payload in commands:
      self.rpc(command, payload.encode('utf-8') )
      #time.sleep(0.1)

    # Do a quick first name check
    desc = self.rpc('dev.desc').decode('utf-8')
    if connectingMessage:
      print(f"{desc}")

    # Query rpcs and dstreams
    # TODO: Caching!
    self.rpcList()
    self.data_send_all()
    self.logger.info(f"Found {len(self.rpcs)} RPCs and {len(self.sources)} data sources")

  def recv_thread(self):
    while True:
      try:
        packet = self.recv()
      except IOError as e:
        # for now, just exit, TODO: reconnect?
        # probably some I/O problem such as disconnected USB serial
        print("\x1Bc") # fix up after interactive python crash, TODO
        self.logger.error(f"Error: {e}")
        import os
        os._exit(0)
      if packet['type'] == TL_PTYPE_STREAM0:
        if self.routing == packet['routing']:
          try:
            self.pub_queue.put(packet, block=False)
          except queue.Full:
            self.pub_queue.get() # Toss a packet
            self.pub_queue.put(packet, block=False)
          # except queue.Empty:
          #   self.logger.error(f"No response. Timeout.")
          #   import os
          #   os._exit(0)
      elif packet['type'] == TL_PTYPE_RPC_REP or packet['type'] == TL_PTYPE_RPC_ERROR:
        if self.routing == packet['routing']:
          try:
            self.rep_queue.put(packet, block=False)
          except queue.Full:
            self.rep_queue.get() # Toss a packet
            self.rep_queue.put(packet, block=False)
            self.logger.error("Tossing an unclaimed REP!")


  def send_thread(self):
    while True:
      # Blocks
      self.send(self.req_queue.get())

  def pub_flush(self):
    while not self.pub_queue.empty():
      try:
        self.pub_queue.get(block=False)
      except:
        break

  def recv_tcp_packet(self):
    try:
      header = bytes(self.socket.recv(4))
    except BlockingIOError:
      return b''
    if len(header) != 4:
      raise IOError("Lost connection")
    headerFields = struct.unpack("<BBH", header )
    payloadType, routingSize, payloadSize = headerFields
    if payloadSize > TL_PACKET_MAX_SIZE or routingSize>TL_PACKET_MAX_ROUTING_SIZE:
      return b''
    payload = bytes(self.socket.recv(payloadSize+routingSize))
    return header+payload

  def recv_slip_packet(self):
    while self.alive and self.serial.is_open:
      try:
        # read all that is there or wait for one byte (blocking)
        data = self.serial.read(self.serial.in_waiting or 1)
      except serial.SerialException as e:
        raise IOError(f"serial error: {e}")
      else:
        if data:
          self.buffer.extend(data)
          while slip.SLIP_END_CHAR in self.buffer:
            packet, self.buffer = self.buffer.split(slip.SLIP_END_CHAR, 1)
            try:
              return slip.decode(packet)
            except slip.SLIPEncodingError as error:
              self.logger.debug(error);
              #hexdump.hexdump(packet)
              #self.logger.exception(error)
              return b""

  def send(self, packet):
    if self.uri.scheme == "tcp":
      self.socket.send(packet)
    else:
      self.serial.write(slip.encode(packet))

  def recv(self):
    if self.uri.scheme == "tcp":
      packet = self.recv_tcp_packet()
    else:
      packet = self.recv_slip_packet()
    try:
      return self.decode_packet(packet)
    except Exception as error:
      self.logger.debug('Error decoding packet:');
      hexdump.hexdump(packet)
      self.logger.exception(error)
      return { 'type':TL_PTYPE_INVALID }

  def decode_packet(self, packet):
    if len(packet)<4:
      return { 'type':TL_PTYPE_NONE }

    # Parse header
    header = packet[0:4]
    payload = packet[4:]
    headerFields = struct.unpack("<BBH", header )
    payloadType, routingSize, payloadSize = headerFields
    if payloadSize > TL_PACKET_MAX_SIZE or routingSize>TL_PACKET_MAX_ROUTING_SIZE:
      return { 'type':TL_PTYPE_INVALID }

    parsedPacket = { 'type':payloadType }

    # Strip routing
    if routingSize > 0:
      routingBytes = payload[-routingSize:] 
      payload = payload[:-routingSize]
      parsedPacket['routing'] = list(routingBytes)
    else:
      parsedPacket['routing'] = []

    if payloadType == TL_PTYPE_STREAM0: # Data stream 0
      sampleNumber = struct.unpack("<I", bytes(payload[0:4]) )[0]
      data = payload[4:]
      parsedPacket['sampleNumber'] = sampleNumber
      parsedPacket['rawdata'] = data
      #self.logger.debug(f"Data stream #{payloadType}, Sample #{sampleNumber}")

    elif payloadType == TL_PTYPE_LOG: # Log message
      logMessage = payload.decode('utf-8')
      parsedPacket['message'] = logMessage
      self.logger.info("LOG: " + logMessage)

    elif payloadType == TL_PTYPE_RPC_REP: # Got reply
      requestID = struct.unpack("<H", bytes(payload[:2]) )[0]
      replyPayload = payload[2:]
      parsedPacket['requestid'] = requestID
      parsedPacket['payload'] = replyPayload
      self.logger.debug(f"REP (ID 0x{requestID:04x}): {replyPayload}")

    elif payloadType == TL_PTYPE_RPC_ERROR: # Got reply error
      requestID, errorCode = struct.unpack("<HH", bytes(payload[:4]) )
      errorPayload = payload[4:]
      parsedPacket['requestid'] = requestID
      parsedPacket['error'] = errorCode
      parsedPacket['payload'] = errorPayload
      self.logger.debug(f"REP (ID 0x{requestID:04x}) Error {errorCode} ")

    elif payloadType == TL_PTYPE_TIMEBASE:
      timebaseDescription = struct.unpack("<HBBQLLLfBBBBBBBBBBBBBBBB", bytes(payload[:44]) )
      parsedPacket['timebase_id']              = int(timebaseDescription[0])
      parsedPacket['timebase_source']          = int(timebaseDescription[1])
      parsedPacket['timebase_epoch']           = int(timebaseDescription[2])
      parsedPacket['timebase_start_time']      = int(timebaseDescription[3])
      parsedPacket['timebase_period_num_us']   = int(timebaseDescription[4])
      parsedPacket['timebase_period_denom_us'] = int(timebaseDescription[5])
      parsedPacket['timebase_flags']           = int(timebaseDescription[6])
      parsedPacket['timebase_stability_ppb']   = float(timebaseDescription[7])*1e9
      parsedPacket['timebase_src_params']      = timebaseDescription[8:8+16]

      # Derive period
      if parsedPacket['timebase_period_denom_us'] is not 0 \
        and parsedPacket['timebase_period_num_us'] is not 0:
         parsedPacket['timebase_period_us'] = parsedPacket['timebase_period_num_us'] \
                                            / parsedPacket['timebase_period_denom_us']
         parsedPacket['timebase_Fs'] = 1e6/parsedPacket['timebase_period_us']
      else:
         parsedPacket['timebase_period_us'] = math.nan
         parsedPacket['timebase_Fs'] = math.nan
      
      if len(self.timebases) < parsedPacket['timebase_id']:
        self.timebases[parsedPacket['timebase_id']] = parsedPacket
      elif len(self.timebases) == parsedPacket['timebase_id']:
        self.timebases += [parsedPacket]
    
      self.logger.debug(f"timebase {parsedPacket['timebase_id']}: "+
              f"{parsedPacket['timebase_Fs']} Hz")

      self.streamCompile()

    elif payloadType == TL_PTYPE_SOURCE: # Got source description
      streamDescription = struct.unpack("<HHLLIHHB", bytes(payload[:21]) )
      parsedPacket['source_id']         = int(streamDescription[0])
      parsedPacket['source_timebase_id']= int(streamDescription[1])
      parsedPacket['source_period']     = int(streamDescription[2])
      parsedPacket['source_offset']     = int(streamDescription[3])
      parsedPacket['source_fmt']        = int(streamDescription[4])
      parsedPacket['source_flags']      = int(streamDescription[5])
      parsedPacket['source_channels']   = int(streamDescription[6])
      parsedPacket['source_type']       = int(streamDescription[7])
      description                        = payload[21:].decode('utf-8').split("\t")
      parsedPacket['source_name'] = description[0]
      parsedPacket['source_column_names'] = [""]
      parsedPacket['source_title'] = ""
      parsedPacket['source_units'] = ""
      parsedPacket['source_other_desc'] = ""
      if len(description) >= 2:
        parsedPacket['source_column_names'] = description[1].split(",")
      if len(description) >= 3:
        parsedPacket['source_title'] = description[2]
      if len(description) >= 4:
        parsedPacket['source_units'] = description[3]
      if len(description) >= 5:
        parsedPacket['source_other_desc'] = description[4:]

      # Derived values
      parsedPacket['source_dtype']      = TYPES[parsedPacket['source_type']][1]
      parsedPacket['source_dtype_pack'] = TYPES[parsedPacket['source_type']][0]
      parsedPacket['source_dtype_bytes']= TYPES[parsedPacket['source_type']][2]
      
      self.streamCompile()
      
      self.sources[parsedPacket['source_name']] = parsedPacket
      self.logger.debug(f"source {parsedPacket['source_id']}: {description}")
      self.logger.debug(f"source {parsedPacket['source_id']}: {parsedPacket['source_name']} {parsedPacket['source_title']} ({parsedPacket['source_units']})")

    elif payloadType == TL_PTYPE_DSTREAM: # Got dstream description
      streamDescription = struct.unpack("<HHLLQHH", bytes(payload[:24]) )
      parsedPacket['dstream_id']               = int(streamDescription[0])
      parsedPacket['dstream_timebase_id']      = int(streamDescription[1])
      parsedPacket['dstream_period']           = int(streamDescription[2])
      parsedPacket['dstream_offset']           = int(streamDescription[3])
      parsedPacket['dstream_sample_number']    = int(streamDescription[4])
      parsedPacket['dstream_total_components'] = int(streamDescription[5])
      parsedPacket['dstream_flags']            = int(streamDescription[6])

      self.logger.debug(f"dstream {parsedPacket['dstream_id']}: timebase {parsedPacket['dstream_timebase_id']}, sources {parsedPacket['dstream_total_components']}")

      if parsedPacket['dstream_id'] == 0: # Only support dstream 0
        self.dstreamInfo = parsedPacket
        if len(payload)>24:
          self.streams = []
          for i, stream in enumerate(range(self.dstreamInfo['dstream_total_components'])):
            streamDescription = struct.unpack("<HHLL", bytes(payload[24+stream*12:24+(stream+1)*12]) )
            streamInfo = {}
            streamInfo['stream_source_id']    = int(streamDescription[0])
            streamInfo['stream_flags']         = int(streamDescription[1])
            streamInfo['stream_period']        = int(streamDescription[2])
            streamInfo['stream_offset']        = int(streamDescription[3])
            self.streams += [streamInfo]
            self.logger.debug(f"dstream {parsedPacket['dstream_id']} component {i}: source {streamInfo['stream_source_id']}, period {streamInfo['stream_period']}")

          self.streamCompile()

    else:
      self.logger.error("ERROR: Unknown packet type")

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
    header = struct.pack("<BBH", TL_PTYPE_RPC_REQ, len(self.routingBytes), len(msg) )
    msg = header + msg + self.routingBytes
    self.req_queue.put(msg)
    self.logger.debug(f"REQ (ID 0x{requestID:04x}): {topic.decode('utf-8')}({payload})")
    return requestID

  def recv_rep(self, requestID = None):
    parsedPacket = self.rep_queue.get(timeout=1)
    if requestID is None or requestID == parsedPacket['requestid']:
      if parsedPacket['type'] == TL_PTYPE_RPC_ERROR:
        raise TLRPCException( TL_RPC_ERRORS[parsedPacket['error']] )
      if parsedPacket['payload'] == b'':
        return None
      else:
        return parsedPacket['payload']

  def rpc(self, topic = "dev.desc", payload = None):
    requestID = self.send_req(topic, payload)
    try: 
      return self.recv_rep(requestID)
    except TLRPCException as e:
      self.logger.error(f"RPC ERROR {topic}: {e}" )
      raise
    except queue.Empty as e:
      self.logger.error(f"RPC TIMEOUT {topic}: {e}" )
      raise

  def rpc_val(self, topic = "data.source.list", rpcType = FLOAT32_T, value = None, returnRaw = False):
    if value is not None:
      reqPayload = struct.pack("<"+TYPES[rpcType][0], value)
    else:
      reqPayload = None
    reply = self.rpc(topic, reqPayload)
    if reply is not None:
      if returnRaw:
        return reply
      if len(reply) > 0:
        return struct.unpack("<"+TYPES[rpcType][0], reply)[0]
    return None

  def rpc_string(self, topic = "dev.desc", payload = None):
    if payload is not None and payload is not "":
      payload = payload.encode('utf-8')
    return self.rpc(topic, payload).decode('utf-8')
  
  def rpcList(self):
    self.rpcs = []
    rpcCount = self.rpc_val("rpc.list", UINT16_T)
    for rpcNumber in range(rpcCount):
      rpcInfo = self.rpc_val("rpc.listinfo", UINT16_T, rpcNumber, returnRaw = True)
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
      #self.logger.info(f"{rpcNumber}: {rpcName}, {rpcType}, {rpcReadable}, {rpcWritable}, {rpcMetadataValid}")
    #self.rpcs.sort(key=lambda x:x['name'])
    return self.rpcs

  def data_send_all(self):
    self.rpc("data.send_all")

  def sourceInfoFromID(self, id):
    for source in self.sources.values():
      if source['source_id'] == id:
        return source
    return {} # Not found

  def source_active(self, topic, set=None):
    if set is not None:
      self.rpc_val(topic+".data.active", UINT8_T, int(set))
    else:
      #return bool(self.rpc_val(topic+".data.active", UINT8_T))
      return topic in self.columnsByName.keys()

  def streamCompile(self):
    self.columns = []
    self.columnsByName = {}
    column = 0
    rowBytes = 0
    rowPack = "<"
    if self.timebases == [] or len(self.sources) == 0:
      return
    if self.dstreamInfo is not None:
      period_us = self.timebases[self.dstreamInfo['dstream_timebase_id']]['timebase_period_us'] \
                * self.dstreamInfo['dstream_period']
    for stream in self.streams:
      sourceInfo = self.sourceInfoFromID(stream['stream_source_id'])
      if sourceInfo == {}:
        return
      stream.update( sourceInfo )
      stream['stream_column_start'] = column
      stream['stream_period_us'] = period_us * stream['stream_period']
      stream['stream_Fs'] = 1e6/stream['stream_period_us']
      self.sources[stream['source_name']]['Fs'] = stream['stream_Fs']

      self.columnsByName[ stream['source_name'] ] = stream

      for i in range(stream['source_channels']):
        column += 1
        columnName = stream['source_name']
        if len(stream['source_column_names']) > 1:
          columnName += "."+stream['source_column_names'][i]
        self.columns += [ columnName ] 
        rowBytes += stream['source_dtype_bytes']
        rowPack  += stream['source_dtype_pack']

      self.rowunpackByBytes[rowBytes] = rowPack

      self.logger.debug(
        f"stream columns {stream['stream_column_start']}-"+
        f"{stream['stream_column_start']+stream['source_channels']-1}: "+
        f"{stream['source_name']} "+
        f"@ {stream['stream_Fs']} Hz")
    self.logger.debug(f"stream columns: {self.columns}")


  def dstream_read_raw(self, rows = 1, duration=None, flush=True):
    if flush:
      self.pub_flush()
    data = []
    while True:
      parsedPacket = self.pub_queue.get()
      if parsedPacket['type'] == TL_PTYPE_STREAM0:
        packet_bytes = int(len(parsedPacket['rawdata']))
        data += [struct.unpack( self.rowunpackByBytes[packet_bytes], parsedPacket['rawdata'] )]
        if len(data) == rows:
          break
    if rows == 1:
      data = data[0]
    return data

  def dstream_read_topic_raw(self, topic, samples = 10):
    streamInfo = self.columnsByName[topic]
    column = streamInfo['stream_column_start']
    channels = streamInfo['source_channels']
    data_flat = []
    while True:
      parsedPacket = self.pub_queue.get()
      if parsedPacket['type'] == TL_PTYPE_STREAM0:
        packet_bytes = int(len(parsedPacket['rawdata']))
        row = struct.unpack( self.rowunpackByBytes[packet_bytes], parsedPacket['rawdata'] )
        data_flat += row[column:column+channels]
        if int(len(data_flat)/channels) >= samples: 
          break
    data_flat = data_flat[:channels*samples] # truncate at specified point
    data = [[row for row in data_flat[column::channels]] for column in range(channels)] # group data by channel
    if samples == 1:
      data = [datum[0] for datum in data]
    if len(data) == 1:
      data = data[0]
    return data

  def dstream_read_topic(self, topic, samples = 1, duration = None, autoActivate=True, flush=True):
    if autoActivate:
      wasActive = self.source_active(topic)
      if not wasActive:
        self.source_active(topic, True)
    if duration is not None:
      samples = int(duration * self.sources[topic]['Fs'])
    if flush:
      self.pub_flush()
    data = self.dstream_read_topic_raw(topic, samples)
    if autoActivate and not wasActive:
      self.source_active(topic, False)
    return data


