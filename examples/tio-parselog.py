#!/usr/bin/env python3
"""
..
    Copyright: 2018 Twinleaf LLC
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
parser.add_argument('-vp', 
                    action="store_true",
                    default=False,
                    help='Extra verbose protocol output for debugging')
parser.add_argument('--raw', 
                    action="store_true",
                    default=False,
                    help='Display output for each line')
parser.add_argument('--lines', 
                    action="store",
                    default=None,
                    help='Limit number of packets to process')
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
routes=[]
sensors={}
tempfilenames = {}
tempfiles = {}
firsttimes = {}

lines = 0
with open(args.logfile,'rb') as f:
  while True:
    lines += 1
    if args.lines is not None:
      if lines > int(args.lines):
        break
    header = bytes(f.read(4))
    if len(header) < 4:
      break

    headerFields = struct.unpack("<BBH", header )
    payloadType, routingSize, payloadSize = headerFields
    if payloadSize > tio.TL_PACKET_MAX_SIZE or routingSize > tio.TL_PACKET_MAX_ROUTING_SIZE:
      logger.error('Packet too big');
      raise
    else:
      payload = bytes(f.read(payloadSize+routingSize))
      packet = header+payload
      if routingSize > 0:
        routingBytes = payload[-routingSize:] 
      if routingBytes not in routes:
        routes += [routingBytes]
        sensors[routingBytes] = tio.TIOProtocol(verbose = args.vp, routing=list(routingBytes))
        tempfilenames[routingBytes] = outputfile[:-4]+f"-{routingBytes}.tsv"
        tempfiles[routingBytes] = open(tempfilenames[routingBytes], 'w')

      try:
        parsedPacket = sensors[routingBytes].decode_packet(packet)
      except Exception as error:
        logger.debug('Error decoding packet:');
        hexdump.hexdump(packet)
        logger.exception(error)
      
      if args.raw:
        print(parsedPacket)

      if parsedPacket['type'] == tio.TL_PTYPE_STREAM0:
        row = sensors[routingBytes].stream_timed_data(parsedPacket)
        if row !=[]:
          if routingBytes not in firsttimes.keys():
            firsttimes[routingBytes] = row[0]
          rowsamples = len(row)
          rowstring = "\t".join(map(str,row))
          # Add blanks to pack out when absent data
          rowstring += "\t"*(len(sensors[routingBytes].columns)+1-rowsamples) # +1 for time column
          rowstring += "\n"
          #print(rowstring)
          tempfiles[routingBytes].write(rowstring)

for fd in tempfiles.values():
  fd.close()

firsttime = max(firsttimes.values())
if firsttime>0:
  print(f"Lopping off data until {firsttime} seconds!")

# Now write out combined file
tempfilelist = []
for routingBytes in routes:
  #print(tempfilenames)
  #print(routingBytes)
  fd = open(tempfilenames[routingBytes], 'r')
  tempfilelist += [ fd ]

with open(outputfile,'w') as fout:
  headerstring=""
  for routingBytes in routes:
    routingstring="/".join(map(str,list(routingBytes)))+"/"
    if len(sensors[routingBytes].columns)>0:
      for column in ["time"]+sensors[routingBytes].columns:
        headerstring+= routingstring+column+"\t"
  fout.write(headerstring[:-1]+"\n")

  while True:
    line = ""
    for fd in tempfilelist:
      linesegment = fd.readline()
      try:
        time = float(linesegment.split('\t')[0])
      except:
        break
      while time <= firsttime:
        linesegment = fd.readline()
        time = float(linesegment.split('\t')[0])
      if linesegment != "":
        line += linesegment[:-1]+"\t"
    if line == "":
      break
    line = line[:-1]+"\n"
    fout.write(line)

# close and delete temporary files
for fd in tempfilelist:
  fd.close()
for tempfile in tempfilenames.values():
  os.remove(tempfile)

