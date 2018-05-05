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
import os

parser = argparse.ArgumentParser(prog='tio_logfile', 
                                 description='Unpack raw TIO log files (.tio format).')

parser.add_argument("logfile", 
                    nargs='?', 
                    default='Log 000000.tio',
                    help='Filename like "Log 000000.tio"')
parser.add_argument('-v', 
                    action="store_true",
                    default=False,
                    help='Verbose output for debugging')
parser.add_argument('--raw', 
                    action="store_true",
                    default=False,
                    help='Display output for each line')
args = parser.parse_args()

logLevel = logging.ERROR
if args.v:
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
      logger.error('Packet too big');
      break
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
      
      if args.raw:
        print(parsedPacket)

      if parsedPacket['type'] == tio.TL_PTYPE_STREAM0:
        row = sensors[routing].dstream_timed_data(parsedPacket)
        if row !=[]:
          rowsamples = len(row)
          rowstring = "\t".join(map(str,row))
          # Add blanks to pack out when absent data
          rowstring += "\t"*(len(sensors[routing].columns)+1-rowsamples) # +1 for time column
          rowstring += "\n"
          #print(rowstring)
          tempfiles[routing].write(rowstring)

for fd in tempfiles:
  fd.close()

# Now write out combined file
tempfiles = []
for routing in range(4):
  fd = open(tempfilenames[routing], 'r')
  tempfiles += [ fd ]

with open(outputfile,'w') as fout:
  headerstring=""
  for sensor in sensors:
    routingstring="/".join(map(str,list(sensor.routingBytes)))+"/"
    if len(sensor.columns)>0:
      for column in ["time"]+sensor.columns:
        headerstring+= routingstring+column+"\t"
  fout.write(headerstring[:-1]+"\n")

  while True:
    line = ""
    for fd in tempfiles:
      linesegment = fd.readline()
      if linesegment != "":
        line += linesegment[:-1]+"\t"
    if line == "":
      break
    line = line[:-1]+"\n"
    fout.write(line)

# close and delete temporary files
for fd in tempfiles:
  fd.close()
for tempfile in tempfilenames:
  os.remove(tempfile)

