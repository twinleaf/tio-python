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
  def __init__(self, url="tcp://localhost", verbose=False, connectingMessage = True, commands=[], stateCache = True):

    if verbose:
      logLevel = logging.DEBUG
    else:
      logLevel = logging.ERROR
    logging.basicConfig(level=logLevel)
    self.logger = logging.getLogger('tio-session')

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

    # Init TIO protocol state
    self.protocol = TIOProtocol(routing = self.routing)

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

    # Startup commands
    for command, payload in commands:
      self.rpc(command, payload.encode('utf-8') )
      #time.sleep(0.1)

    # Do a quick first name check
    desc = self.rpc('dev.desc').decode('utf-8')
    if connectingMessage:
      print(f"{desc}")

    # Query rpcs and dstreams
    
    # Try to load from cache!
    pickleCache = os.path.join(tempfile.gettempdir(), desc)
    if os.path.isfile(pickleCache) and stateCache:
      with open(pickleCache, "rb") as f:
        [protocolState, rpcState] = pickle.load(f)
      # Perform other qualification checks!
      [self.rpcs, self.rpcNames] = rpcState
      self.protocol.stateImport(protocolState)
    else:
      # RPCs are stashed here
      self.rpcs = []
      self.rpcNames = {}
      self.rpcList()
      self.data_send_all()
      time.sleep(0.5) # Wait to make sure all the send_all info came through
      rpcState = [self.rpcs, self.rpcNames]
      protocolState = self.protocol.stateExport()
      with open(pickleCache, "wb") as f:
        pickle.dump( [protocolState, rpcState], f)
    self.logger.info(f"Found {len(self.rpcs)} RPCs and {len(self.protocol.sources)} data sources")

  def close(self):
    # TODO: Notify threads to quit
    pass

  def recv_thread(self):
    while True:
      try:
        packet = self.recv()
      except IOError as e:
        # for now, just exit, TODO: reconnect?
        # probably some I/O problem such as disconnected USB serial
        #print("\x1Bc") # fix up after interactive python crash, TODO
        self.logger.error(f"Error: {e}")
        import os
        os._exit(0)
      if packet['type'] == TL_PTYPE_STREAM0:
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
    else:
      #hexdump.hexdump(slip.encode(packet))
      self.serial.write(slip.encode(packet))

  def recv(self):
    if self.uri.scheme == "tcp":
      packet = self.recv_tcp_packet()
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
    parsedPacket = self.rep_queue.get(timeout=1.5)
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

  def source_active(self, topic, set=None):
    if set is not None:
      self.rpc_val(topic+".data.active", UINT8_T, int(set))
    else:
      #return bool(self.rpc_val(topic+".data.active", UINT8_T))
      return topic in self.protocol.columnsByName.keys()

  def dstream_read_raw(self, rows = 1, duration=None, flush=True):
    if flush:
      self.pub_flush()
    data = []
    while True:
      parsedPacket = self.pub_queue.get()
      if parsedPacket['type'] == TL_PTYPE_STREAM0:
        data += [ self.protocol.dstream_data(parsedPacket) ]
        if len(data) == rows:
          break
    if rows == 1:
      data = data[0]
    return data

  def dstream_read_topic_raw(self, topic, samples = 10):
    streamInfo = self.protocol.columnsByName[topic]
    column = streamInfo['stream_column_start']
    channels = streamInfo['source_channels']
    data_flat = []
    while True:
      parsedPacket = self.pub_queue.get()
      if parsedPacket['type'] == TL_PTYPE_STREAM0:
        row = self.protocol.dstream_data(parsedPacket) 
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

  def pub_warn_overload(self):
    if self.pub_queue.qsize() > .95*self.pub_queue.maxsize:
      self.warn_overload()

  def warn_overload(self):
    self.logger.error("As it turns out, python can't keep up with this data rate. Please reduce the data rate or use an alternative tool.")
    self.logger.error("If you aren't using the TIO proxy, please give it a try to offload the SLIP decoding: https://github.com/twinleaf/tio-tools.")
    import os
    os._exit(0)





