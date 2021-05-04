#!/usr/bin/env python3
"""
..
    Copyright: 2018-9 Twinleaf LLC
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
                    type=str,
                    nargs='+', 
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
parser.add_argument('--sth', 
                    type=float,
                    default=10,
                    help='Factor by which slower streams are excluded from merge')
args = parser.parse_args()

logLevel = logging.ERROR
if args.v:
  logLevel = logging.DEBUG
logging.basicConfig(level=logLevel)
logger = logging.getLogger('tio-logfile')

# First read through and generate individual files for each stream.
routes=[]
sensors={}
tempfilenames = {}
tempfiles = {}
firsttimes = {}
datarates = {}
lines = 0

filenames = args.logfile
for filename in filenames:
  if filename[-4:]==".tio":
    outputfile = filename[:-4]+".tsv"
  else:
    outputfile = filename+".tsv"
  with open(filename,'rb') as f:
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
        routingBytes = b''
        if routingSize > 0:
          routingBytes = payload[-routingSize:]
        if routingBytes not in routes:
          routes += [routingBytes]
          sensors[routingBytes] = tio.TIOProtocol(verbose = args.vp, routing=list(routingBytes))
          tempfilenames[routingBytes] = outputfile[:-4]+f"-{list(routingBytes)}.tsv"
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
          row = sensors[routingBytes].stream_data(parsedPacket, timeaxis=True)
          if row !=[]:
            time,data = row
            if routingBytes not in firsttimes.keys():
              firsttimes[routingBytes] = time
            if routingBytes not in datarates.keys():
              datarates[routingBytes] = sensors[routingBytes].streams[0]['stream_Fs'] 
            rowsamples = len(data)
            rowstring = str(time)+"\t"
            rowstring += "\t".join(map(str,data))
            # Add blanks to pack out when absent data
            rowstring += "\t"*(len(sensors[routingBytes].columns)+1-rowsamples) # +1 for time column
            rowstring = rowstring[:-1]+"\n"
            tempfiles[routingBytes].write(rowstring)

for fd in tempfiles.values():
  fd.close()

try:
  firsttime = max(firsttimes.values())
except:
  raise Exception("No metadata in sample enough to get a first sample. Sample for longer?")
if firsttime>0:
  print(f"Writing (merged) log starting at {firsttime} s.")

# If there are files with global timestamps, then set aside the files with local timestamps
# heuristic for whether there are valid unix timestamps
if firsttime>1000000000: # Sat Sep 08 2001 21:46:40 UTC-0400 (EDT)
  # Find all the files that use local time and remove them from merging
  for idx, thisfirsttime in enumerate(firsttimes.values()):
    if thisfirsttime < 1000000000:
      routestr = "/".join(map(str,list(routes[idx])))+"/"
      print(f"NB: Not merging from route {routestr} because its starting time {thisfirsttime} s does not appear to have a global timestamp.")
      tempfiles.pop(routes[idx])
      tempfilenames.pop(routes[idx])
      sensors.pop(routes[idx])
      # firsttimes.pop(routes[idx])
      datarates.pop(routes[idx])
      routes.pop(idx)

# discardedTime = max(firsttimes.values()) - min(firsttimes.values())
# if discardedTime > 0:
#   print(f"NB: Discarding up to the first {discardedTime} seconds of data to merge the logs")

# If there are streams with widely varying data rates, then set aside the streams with low rates
slowerThreshold = args.sth
dataratemax = max(datarates.values())
for idx, datarate in enumerate(datarates.values()):
  if datarate < dataratemax / slowerThreshold:
    routestr = "/".join(map(str,list(routes[idx])))+"/"
    print(f"NB: Not merging from route {routestr} because its data rate {datarate} Hz < dominant rate {dataratemax} Hz / {slowerThreshold}." )
    tempfiles.pop(routes[idx])
    tempfilenames.pop(routes[idx])
    sensors.pop(routes[idx])
    firsttimes.pop(routes[idx])
    routes.pop(idx)

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
        columnstring = routingstring+column+"\t"
        headerstring += columnstring
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
        try:
          time = float(linesegment.split('\t')[0])
        except:
          raise IndexError("Could not find time alignment among streams")
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

