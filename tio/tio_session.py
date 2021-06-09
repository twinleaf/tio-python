#!/usr/bin/env python3
# coding: utf-8
"""
Twinleaf IO (tio) - A serialization for instrumentation
Copyright 2017-2019 Twinleaf LLC
License: MIT

A simple protocol for working with sensors through single-port/serial connections.
"""

import serial
import socket
import threading
import struct
import urllib.parse
import time
import queue
import slip
import hexdump
import logging
import pickle
import tempfile
import os
from .tio_protocol import *

class TLRPCException(Exception):
    pass

class TIOSession(object):
  def __init__(self, url="tcp://localhost", verbose=False, connectingMessage = True, rpcs=[], stateCache = True, send_router=None, specialize=True, timeout=False):

    if verbose:
      logLevel = logging.DEBUG
    else:
      logLevel = logging.ERROR
    logging.basicConfig(level=logLevel)
    self.logger = logging.getLogger('tio-session')

    # Connect to either TCP socket or serial port
    self.uri = urllib.parse.urlparse(url)
    if self.uri.scheme in ["tcp", "udp"]:
      if self.uri.port is None:
        self.port = 7855
      else:
        self.port = self.uri.port
      routingStrings = self.uri.path.split('/')[1:]
      if self.uri.scheme == "tcp":
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.connect((self.uri.hostname, self.port))
      elif self.uri.scheme == "udp":
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        #self.socket.bind(("", self.port))
      if timeout:
        self.socket.settimeout(1.0)
    elif self.uri.scheme == "router":
      self.send_router = send_router
      self.recv_queue = queue.Queue(maxsize=1000)
      routingStrings = self.uri.path.split('/')[1:]
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

    # routingStrings is a list of integers [], [0], or [0,1]
    routingStrings = filter(lambda a: a != '', routingStrings)
    try:
      self.routing = [ int(address) for address in routingStrings ]
      self.routing = self.routing[::-1] # First child node is outermost routing byte 
    except:
      raise Exception(f'Bad routing path: {routingString}')

    # Used if the routing isn't to us
    self.recv_router = None

    # Init TIO protocol state
    self.protocol = TIOProtocol(routing = self.routing, verbose=verbose)

    # Initialize queues and threading controls
    self.pub_queue = queue.Queue(maxsize=1000)
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

    # Don't specialize if you don't have a solid connection yet (ie in multi device sync)
    self.specialized = False
    if specialize:
      self.specialize(rpcs=rpcs, stateCache=stateCache, connectingMessage=connectingMessage)

  def specialize(self, rpcs=[], stateCache=True, connectingMessage=True):
    # Startup RPCs
    for topic, rpcType, value in rpcs:
      if type(rpcType) is str: # Find type from dict of types
        rpcType = list(TYPES.keys())[ [entry[1] for entry in TYPES.values()].index(rpcType) ]
      if rpcType == NONE_T:
        self.rpc(topic, value.encode('utf-8'))
      else:
        if rpcType == FLOAT32_T or rpcType == FLOAT64_T:
          value = float(value)
        else:
          value = int(value)
        self.rpc_val(topic, rpcType, value)

    # Do a quick first name check
    self.desc = self.rpc('dev.desc').decode('utf-8')
    self.name = self.rpc('dev.name').decode('utf-8')
    if connectingMessage:
      print(f"{self.name} - {self.desc}")

    # Query rpcs and streams
    
    # Try to load from cache!
    cacheFilename = self.desc.replace('/','-')+".pickle"
    pickleCacheDir = os.path.join(tempfile.gettempdir(), 'com.twinleaf.tio.python.cache')
    pickleCacheFile = os.path.join(pickleCacheDir, cacheFilename)
    if os.path.isfile(pickleCacheFile) and stateCache:
      with open(pickleCacheFile, "rb") as f:
        [protocolState, rpcState] = pickle.load(f)
      # Perform other qualification checks!
      [self.rpcs, self.rpcNames] = rpcState
      self.protocol.stateImport(protocolState)
      self.data_send_all() # We should get up-to-date metadata, primarily for getting the absolute time.
    else:
      # RPCs are stashed here
      self.rpcs = []
      self.rpcNames = {}
      self.data_send_all() # Do this first so that we get all the data info while the RPCs are coming in.
      self.rpcList()
      waited = 0
      while self.protocol.streams==[]: 
        time.sleep(0.5) # Wait to make sure all the send_all info came through
        waited += 1
        if waited >= 8:
          break
          # raise IOError("Did not get stream info after data.send_all.")
      rpcState = [self.rpcs, self.rpcNames]
      protocolState = self.protocol.stateExport()
      if not os.path.exists(pickleCacheDir):
        os.makedirs(pickleCacheDir)
      with open(pickleCacheFile, "wb") as f:
        pickle.dump( [protocolState, rpcState], f)
        self.logger.debug(f"Saved RPC cache")
    self.logger.info(f"Found {len(self.rpcs)} RPCs and {len(self.protocol.sources)} data sources")

    self.specialized = True

  def close(self):
    # TODO: Notify threads to quit
    pass

  def recv_thread(self):
    while True:
      try:
        decoded_packet = self.recv() # Blocks
      except IOError as e:
        # for now, just exit, TODO: reconnect?
        # probably some I/O problem such as disconnected USB serial
        #print("\x1Bc") # fix up after interactive python crash, TODO
        self.logger.error(f"Error: {e}")
        import os
        os._exit(0)
      # Handle stream
      if decoded_packet['type'] == TL_PTYPE_STREAM0:
        try:
          self.pub_queue.put(decoded_packet, block=False)
        except queue.Full:
          self.pub_queue.get() # Toss a packet
          self.pub_queue.put(decoded_packet, block=False)
        # except queue.Empty:
        #   self.logger.error(f"No response. Timeout.")
        #   import os
        #   os._exit(0)
      # Handle RPCs
      elif decoded_packet['type'] == TL_PTYPE_RPC_REP or decoded_packet['type'] == TL_PTYPE_RPC_ERROR:
        try:
          self.rep_queue.put(decoded_packet, block=False)
        except queue.Full:
          self.rep_queue.get() # Toss a packet
          self.rep_queue.put(decoded_packet, block=False)
          self.logger.error("Tossing an unclaimed REP!")
      elif decoded_packet['type'] == TL_PTYPE_OTHER_ROUTING:
        if self.recv_router is not None:
          self.recv_router(decoded_packet['routing'],decoded_packet['raw'])

  def send_thread(self):
    while True:
      # Blocks
      try:
        self.send(self.req_queue.get(timeout=0.5))
      except queue.Empty:
        pass
      # Send heartbeat; need to regulate this somewhat
      #print("❤️")
      self.send(self.protocol.heartbeat())

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

  def recv_udp_packet(self):
    try:
      d = self.socket.recvfrom(512)
      packet = d[0]
      address = d[1]
    except BlockingIOError:
      return b''
    if len(packet) < 4:
      return b''
    headerFields = struct.unpack("<BBH", packet[0:4] )
    payloadType, routingSize, payloadSize = headerFields
    if payloadSize > TL_PACKET_MAX_SIZE or routingSize>TL_PACKET_MAX_ROUTING_SIZE:
      return b''
    return packet

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
          #print(len(self.buffer))
          if len(self.buffer)>2000:
            self.warn_overload()
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
    elif self.uri.scheme == "udp":
      self.socket.sendto(packet,(self.uri.hostname, self.port))
    elif self.uri.scheme == "router":
      self.send_router(packet)
    else:
      self.serial.write(slip.encode(packet))

  def recv(self):
    if self.uri.scheme == "tcp":
      packet = self.recv_tcp_packet()
    elif self.uri.scheme == "udp":
      packet = self.recv_udp_packet()
    elif self.uri.scheme == "router":
      packet = self.recv_queue.get()
    else:
      packet = self.recv_slip_packet()
    try:
      # Filter routing here? TODO
      return self.protocol.decode_packet(packet)
    except Exception as error:
      self.logger.debug('Error decoding packet:');
      hexdump.hexdump(packet)
      self.logger.exception(error)
      return { 'type':TL_PTYPE_INVALID }

  def send_req(self, topic = "dev.desc", payload = None):
    msg, requestID = self.protocol.req(topic, payload)
    self.req_queue.put(msg)
    return requestID

  def recv_rep(self, requestID = None):
    parsedPacket = self.rep_queue.get(timeout=3.0)
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
      if rpcType == STRING_T:
        reqPayload = value.encode('utf-8')
      else:
        reqPayload = struct.pack("<"+TYPES[rpcType][0], value)
    else:
      reqPayload = None
    reply = self.rpc(topic, reqPayload)
    if reply is not None:
      if returnRaw:
        return reply
      if len(reply) > 0:
        if rpcType == STRING_T:
          return reply.decode('utf-8')
        else:
          return struct.unpack("<"+TYPES[rpcType][0], reply)[0]
    return None

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
      self.logger.debug(f"{rpcNumber}: {rpcName}, type: {rpcType}, read: {rpcReadable}, write: {rpcWritable}, valid metadata: {rpcMetadataValid}")
    #self.rpcs.sort(key=lambda x:x['name'])
    return self.rpcs

  def data_send_all(self):
    self.rpc("data.send_all")

  def source_active(self, topic, set=None):
    if set is not None:
      self.rpc_val(topic+".data.active", UINT8_T, int(set))
    else:
      #return bool(self.rpc_val(topic+".data.active", UINT8_T))
      return topic in self.protocol.columnsByName.keys()

  def stream_read_raw(self, samples = 1, duration=None, flush=True, timeaxis=False):
    if flush:
      self.pub_flush()
    data = []
    while True:
      parsedPacket = self.pub_queue.get()
      if parsedPacket['type'] == TL_PTYPE_STREAM0:
        if timeaxis:
          time, row = self.protocol.stream_data(parsedPacket, timeaxis=timeaxis)
          data += [ [ time ] + list(row) ]
        else:
          data += [ self.protocol.stream_data(parsedPacket, timeaxis=timeaxis) ]
        if len(data) == samples:
          break
    if samples == 1:
      data = data[0]
    return data

  def stream_read_topic_raw(self, topic, samples = 10, timeaxis=False):
    streamInfo = self.protocol.columnsByName[topic]
    column = streamInfo['stream_column_start']
    channels = streamInfo['source_channels']
    data_flat = []
    times = []
    while True:
      parsedPacket = self.pub_queue.get()
      if parsedPacket['type'] == TL_PTYPE_STREAM0:
        if timeaxis:
          time,row = self.protocol.stream_data(parsedPacket, timeaxis=timeaxis)
          data_row = row[column:column+channels]
          data_flat += data_row
          if data_row != []:
            times += [time]
        else:
          row = self.protocol.stream_data(parsedPacket, timeaxis=timeaxis)          
          data_flat += row[column:column+channels]
        if int(len(data_flat)/channels) >= samples: 
          break
    data_flat = data_flat[:channels*samples] # truncate at specified point
    data = [[row for row in data_flat[column::channels]] for column in range(channels)] # group data by channel
    if timeaxis:
      data = [times] + data
    if samples == 1:
      data = [datum[0] for datum in data]
    if len(data) == 1:
      data = data[0]
    return data

  def stream_read_topic(self, topic, samples = 1, duration = None, autoActivate=True, flush=True, timeaxis=False):
    if autoActivate:
      wasActive = self.source_active(topic)
      if not wasActive:
        self.source_active(topic, True)
    if duration is not None:
      samples = int(duration * self.protocol.sources[topic]['Fs'])
    if flush:
      self.pub_flush()
    data = self.stream_read_topic_raw(topic, samples, timeaxis=timeaxis)
    if autoActivate and not wasActive:
      self.source_active(topic, False)
    return data

  def stream_topic_columnnames(self, topic):
    streamInfo = self.protocol.columnsByName[topic]
    column = streamInfo['stream_column_start']
    channels = streamInfo['source_channels']
    columnnames = self.protocol.columns[column:column+channels-1]
    return columnnames

  def source_rate(self, topic):
    streamInfo = self.protocol.columnsByName[topic]
    return streamInfo['stream_Fs']
    # streamInfo = self.protocol.sources[topic]
    # return streamInfo['Fs']

  def pub_warn_overload(self):
    if self.pub_queue.qsize() > .95*self.pub_queue.maxsize:
      self.warn_overload()

  def warn_overload(self):
    self.logger.error("Buffer overfow. Python didn't keep up with the incoming data rate.")
    self.logger.error("Option 1: Reduce the data rate; for 10 Hz add '--rpc data.rate:f32:10'")
    self.logger.error("Option 2: Reduce the data rate; for 10 Hz add '--rpc gmr.data.decimation:u32:80'")
    self.logger.error("Option 3: Use the tio proxy to offload the SLIP decoding: https://github.com/twinleaf/tio-tools")
    import os
    os._exit(0)





