#!/usr/bin/env python3
"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com

Log data!

"""

import tio
import argparse
import hexdump
import logging
import struct
import time

parser = argparse.ArgumentParser(prog='tio_logfile', 
                                 description='Unpack raw TIO log files (.tio format).')

parser.add_argument("logfile", 
                    nargs='?', 
                    default='Log 000000.tio',
                    help='filename like "Log 000000.tio"')
parser.add_argument("output", 
                    nargs='?', 
                    default='log.tsv',
                    help='Log filename: log.tsv')
args = parser.parse_args()

verbose = True

logLevel = logging.ERROR
if verbose: # Quiet
  logLevel = logging.DEBUG
logging.basicConfig(level=logLevel)
logger = logging.getLogger('tio-logfile')


routing =[0]

protocol = tio.TIOProtocol(verbose = False, routing=[0])

with open(args.logfile,'rb') as f:
  while True:
    header = bytes(f.read(4))
    if len(header) < 4:
      break

    headerFields = struct.unpack("<BBH", header )
    payloadType, routingSize, payloadSize = headerFields
    if payloadSize > tio.TL_PACKET_MAX_SIZE or routingSize > tio.TL_PACKET_MAX_ROUTING_SIZE:
      logger.debug('Packet too big');
      hexdump.hexdump(packet)
    else:
      payload = bytes(f.read(payloadSize+routingSize))
      packet = header+payload

      try:
        parsedPacket = protocol.decode_packet(packet)
      except Exception as error:
        logger.debug('Error decoding packet:');
        hexdump.hexdump(packet)
        logger.exception(error)
      print(parsedPacket)
      if parsedPacket['type'] == tio.TL_PTYPE_STREAM0:
        row = protocol.dstream_data(parsedPacket)
        #print(row)
    time.sleep(0.25)
