#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf IO (tio) - A serialization for instrumentation
Copyright 2018 Twinleaf LLC
License: MIT

A simple protocol for working with sensors through single-port/serial connections.
"""

import struct
import random
import math
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
TL_PTYPE_STREAM     = 8 # Update to a stream's parameters
TL_PTYPE_USER       = 64
TL_PTYPE_STREAM0    = 128
TL_PTYPE_OTHER_ROUTING = -1

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
	'TL_RPC_ERROR_RANGE'     , # 17 Value outside allowed range
  'TL_RPC_ERROR_USER'      , # 18 Start value to define per-RPC error codes
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
STRING_T =     0x03
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

class TIOProtocol(object):
  def __init__(self, routing=[], verbose=False):

    self.routingBytes = bytearray(routing)

    logLevel = logging.ERROR
    if verbose:
      logLevel = logging.DEBUG
    logging.basicConfig(level=logLevel)
    routingKey = '/'.join(map(str,routing))
    self.logger = logging.getLogger('tio-protocol'+routingKey)

    # State
    self.timebases = {}
    self.sources = {}
    self.streamInfo = None
    self.streams = []
    self.lastSampleNumber = None

    # State compiled from above
    self.columns = []
    self.columnsByName = {}
    self.rowunpackByBytes = {}

  def stateExport(self):
    return [self.timebases, self.sources, self.streamInfo, self.streams]

  def stateImport(self, stateList):
    [self.timebases, self.sources, self.streamInfo, self.streams] = stateList
    self.streamCompile(self.streams)

  def decode_packet(self, packet):
    if len(packet)<4:
      return { 'type':TL_PTYPE_NONE }

    # Parse header
    header = packet[0:4]
    headerFields = struct.unpack("<BBH", header )
    payloadType, routingSize, payloadSize = headerFields
    if payloadSize > TL_PACKET_MAX_SIZE or routingSize>TL_PACKET_MAX_ROUTING_SIZE:
      return { 'type':TL_PTYPE_INVALID }

    parsedPacket = { 'type':payloadType }
    parsedPacket['raw'] = packet 

    # Strip routing
    if routingSize > 0:
      routingBytes = packet[-routingSize:]
      parsedPacket['routing'] = list(routingBytes)
    else:
      parsedPacket['routing'] = []

    # Toss packet if it's wrong routing
    if list(self.routingBytes) != parsedPacket['routing']:
      parsedPacket['type'] = TL_PTYPE_OTHER_ROUTING
      return parsedPacket

    payload = packet[4:len(packet)-routingSize]

    if payloadType == TL_PTYPE_STREAM0: # Data stream 0
      sampleNumber = struct.unpack("<I", bytes(payload[0:4]) )[0]
      data = payload[4:]
      parsedPacket['sampleNumber'] = sampleNumber
      parsedPacket['rawdata'] = data
      # self.logger.debug(f"Data stream #{payloadType}, Sample #{sampleNumber}")
      #Track sample number
      if self.lastSampleNumber is not None:
        lostPackets = sampleNumber - self.lastSampleNumber - 1
        if lostPackets:
          if lostPackets < 0:
            self.logger.debug(f"Stream was reset.")
          else:
            #self.logger.error(f"Stream dropped {lostPackets} packet(s).")
            self.logger.debug(f"Stream dropped {lostPackets} packet(s).")
      self.lastSampleNumber = sampleNumber
      try:
        self.timebases[self.streamInfo['stream_timebase_id']]
      except:
        pass

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
      parsedPacket['timebase_start_time']      = int(timebaseDescription[3])/1000000000
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
      
      self.timebases[parsedPacket['timebase_id']] = parsedPacket
    
      self.logger.debug(f"timebase {parsedPacket['timebase_id']}: "+
              f"{parsedPacket['timebase_Fs']} Hz, t0={parsedPacket['timebase_start_time']} s")

      self.streamCompile(self.streams)

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
    
      # copy existing Fs
      try:
        parsedPacket['Fs'] = self.sources[parsedPacket['source_name']]['Fs']
      except:
        pass

      self.sources[parsedPacket['source_name']] = parsedPacket
      self.streamCompile(self.streams)

      self.logger.debug(f"source {parsedPacket['source_id']}: {description}")
      self.logger.debug(f"source {parsedPacket['source_id']}: {parsedPacket['source_name']} {parsedPacket['source_title']} ({parsedPacket['source_units']})")

    elif payloadType == TL_PTYPE_STREAM: # Got stream description
      streamDescription = struct.unpack("<HHLLQHH", bytes(payload[:24]) )
      parsedPacket['stream_id']               = int(streamDescription[0])
      parsedPacket['stream_timebase_id']      = int(streamDescription[1])
      parsedPacket['stream_period']           = int(streamDescription[2])
      parsedPacket['stream_offset']           = int(streamDescription[3])
      parsedPacket['stream_sample_number']    = int(streamDescription[4])
      parsedPacket['stream_total_components'] = int(streamDescription[5])
      parsedPacket['stream_flags']            = int(streamDescription[6])

      self.logger.debug(f"stream {parsedPacket['stream_id']}: timebase {parsedPacket['stream_timebase_id']}, sources {parsedPacket['stream_total_components']}")

      if parsedPacket['stream_id'] == 0: # Only support stream 0
        self.streamInfo = parsedPacket
        if len(payload)>24:
          streams = []
          for i, stream in enumerate(range(self.streamInfo['stream_total_components'])):
            streamDescription = struct.unpack("<HHLL", bytes(payload[24+stream*12:24+(stream+1)*12]) )
            streamInfo = {}
            streamInfo['stream_source_id']     = int(streamDescription[0])
            streamInfo['stream_flags']         = int(streamDescription[1])
            streamInfo['stream_period']        = int(streamDescription[2])
            streamInfo['stream_offset']        = int(streamDescription[3])
            streams += [streamInfo]
            self.logger.debug(f"stream {parsedPacket['stream_id']} component {i}: source {streamInfo['stream_source_id']}, period {streamInfo['stream_period']}")
          self.streamCompile(streams)

    elif payloadType == TL_PTYPE_HEARTBEAT:
      # self.logger.debug(f"Heartbeat.")
      return parsedPacket

    elif payloadType > 128:
      self.logger.debug(f"Unhandled stream{payloadType-128} packet.")

    else:
      self.logger.error(f"Unknown packet type {payloadType}")
      

    return parsedPacket

  def sourceInfoFromID(self, id):
    for source in self.sources.values():
      if source['source_id'] == id:
        return source
    return {} # Not found

  def streamCompile(self, streams):
    columns = []
    columnsByName = {}
    column = 0
    rowBytes = 0
    rowPack = "<"
    if self.timebases == {} or len(self.sources) == 0:
      return
    if self.streamInfo is not None:
      period_us = self.timebases[self.streamInfo['stream_timebase_id']]['timebase_period_us'] \
                * self.streamInfo['stream_period']
    for stream in streams:
      sourceInfo = self.sourceInfoFromID(stream['stream_source_id'])
      if sourceInfo == {}:
        return
      stream.update( sourceInfo )
      stream['stream_column_start'] = column
      stream['stream_period_us'] = period_us * stream['stream_period']
      stream['stream_Fs'] = 1e6/stream['stream_period_us']
      stream['stream_start_time_sec'] = self.timebases[self.streamInfo['stream_timebase_id']]['timebase_start_time']
      self.sources[stream['source_name']]['Fs'] = stream['stream_Fs']

      columnsByName[ stream['source_name'] ] = stream

      for i in range(stream['source_channels']):
        column += 1
        columnName = stream['source_name']
        if len(stream['source_column_names']) > 1:
          columnName += "."+stream['source_column_names'][i]
        columns += [ columnName ] 
        rowBytes += stream['source_dtype_bytes']
        rowPack  += stream['source_dtype_pack']

      self.rowunpackByBytes[rowBytes] = rowPack

      self.logger.debug(
        f"stream columns {stream['stream_column_start']}-"+
        f"{stream['stream_column_start']+stream['source_channels']-1}: "+
        f"{stream['source_name']} "+
        f"@ {stream['stream_Fs']} Hz")
    self.logger.debug(f"stream columns: {columns}")

    # Set things atomically
    self.streams = streams
    self.columns = columns
    self.columnsByName = columnsByName

  def req(self, topic, payload):
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
    self.logger.debug(f"REQ (ID 0x{requestID:04x}): {topic.decode('utf-8')}({payload})")
    return msg, requestID

  def heartbeat(self):
    msg = b'' # TODO: random 32-bit session value
    header = struct.pack("<BBH", TL_PTYPE_HEARTBEAT, len(self.routingBytes), len(msg) )
    msg = header + msg + self.routingBytes
    return msg

  def stream_data(self, parsedPacket, timeaxis = False):
    packet_bytes = int(len(parsedPacket['rawdata']))
    if packet_bytes not in self.rowunpackByBytes.keys():
      self.logger.debug(f"No source information for packet")
      return []
    data = struct.unpack( self.rowunpackByBytes[packet_bytes], parsedPacket['rawdata'] )
    if timeaxis:
      time = parsedPacket['sampleNumber'] / self.streams[0]['stream_Fs']
      time += self.streams[0]['stream_start_time_sec']
      return time,data
    else:
      return data

    return (sample_time,)+data
