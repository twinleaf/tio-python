#!/usr/bin/env python3
"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com

Parse native format logged data.

Presently assumes no SLIP encoding

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
                    help='Filename like "Log 000000.tio"')
args = parser.parse_args()

verbose = False

logLevel = logging.ERROR
if verbose: # Quiet
  logLevel = logging.DEBUG
logging.basicConfig(level=logLevel)
logger = logging.getLogger('tio-logfile')

if args.logfile[-4:]==".tio":
  outputfile = args.logfile[:-4]+".tsv"
else:
  outputfile = args.logfile+".tsv"

# Start by allocating simple routing for four sensors attached to a single hub
sensors=[]
tempfilenames = []
tempfiles = []
for routing in range(4):
  sensors += [ tio.TIOProtocol(verbose = False, routing=[routing]) ]
  tempfilename = outputfile[:-4]+f"-{routing}.tsv"
  print(tempfilename)
  tempfilenames += [ tempfilename ]
  fd = open(tempfilename, 'w')
  tempfiles += [ fd ]

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
      if routingSize > 0:
        routingBytes = payload[-routingSize:] 
      routing = int(routingBytes[0])

      try:
        parsedPacket = sensors[routing].decode_packet(packet)
      except Exception as error:
        logger.debug('Error decoding packet:');
        hexdump.hexdump(packet)
        logger.exception(error)

      #print(parsedPacket)

      if parsedPacket['type'] == tio.TL_PTYPE_STREAM0:
        row = sensors[routing].dstream_timed_data(parsedPacket)
        rowstring = "\t".join(map(str,row))+"\n"
        #print(rowstring)
        tempfiles[routing].write(rowstring)


# Now write out combined file

# close and delete temporary files
