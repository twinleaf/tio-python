#!/usr/bin/env python3
"""
..
    Copyright: 2018-2021 Twinleaf LLC
    Author: kornack@twinleaf.com

Parse native format logged data.

Assumes no SLIP encoding.

"""

import tio
import argparse
import hexdump
import logging
import struct
import time
import os

def main():
  
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
  parser.add_argument('--separate', 
                      action="store_true",
                      default=False,
                      help='Do not merge the parsed files.')
  
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
          routingString = "/"
          if routingSize > 0:
            routingBytes = payload[-routingSize:]
            routingString += "/".join(map(str,list(routingBytes)))+"/"
            # If there's more than one file, prefix the routing name with the filename
          if len(filenames) > 1:
            routingString = os.path.basename(filename[:-4]) + routingString
          if routingString not in routes:
            routes += [routingString]
            sensors[routingString] = tio.TIOProtocol(verbose = args.vp, routing=list(routingBytes))
            tempfilenames[routingString] = outputfile[:-4]+f"-{list(routingBytes)}.tsv"
            tempfiles[routingString] = open(tempfilenames[routingString], 'w')
    
          try:
            parsedPacket = sensors[routingString].decode_packet(packet)
          except Exception as error:
            logger.debug('Error decoding packet:');
            hexdump.hexdump(packet)
            logger.exception(error)
          
          if args.raw:
            print(parsedPacket)
    
          if parsedPacket['type'] == tio.TL_PTYPE_STREAM0:
            row = sensors[routingString].stream_data(parsedPacket, timeaxis=True)
            if row !=[]:
              time,data = row
              if routingString not in firsttimes.keys():
                # This is the first row
                firsttimes[routingString] = time
                datarates[routingString] = sensors[routingString].streams[0]['stream_Fs'] 
                # Write out columns
                headerString = ""
                if len(sensors[routingString].columns)>0:
                  for column in ["time"]+sensors[routingString].columns:
                    headerString += routingString+column+"\t"
                  tempfiles[routingString].write(headerString[:-1]+"\n")
              rowsamples = len(data)
              rowstring = str(time)+"\t"
              rowstring += "\t".join(map(str,data))
              # Add blanks to pack out when absent data
              rowstring += "\t"*(len(sensors[routingString].columns)+1-rowsamples) # +1 for time column
              rowstring = rowstring[:-1]+"\n"
              tempfiles[routingString].write(rowstring)
  
  for fd in tempfiles.values():
    fd.close()
  
  print(f"Found data streams from routes:")
  [print(f"- {route}") for route in routes]
  
  if args.separate:
    exit
  
  # Remove routes that don't have valid start times
  for idx,route in enumerate(list(routes)): # copy the routes
    if route not in firsttimes.keys():
      print(f"NB: Not merging from route {route} because the timing metadata is missing.")
      tempfiles.pop(route)
      tempfilenames.pop(route)
      sensors.pop(route)
      routes.remove(route)

  
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
    for route, thisfirsttime in firsttimes.items():
      if thisfirsttime < 1000000000:
        print(f"NB: Not merging from route {routes[idx]} because its starting time {thisfirsttime} s does not appear to have a global timestamp.")
        tempfiles.pop(route)
        tempfilenames.pop(route)
        sensors.pop(route)
        # firsttimes.pop(route)
        datarates.pop(route)
        routes.remove(route)
      # else:
        # print(f"Found metadata for route {route} with starting time {thisfirsttime}.")
  
  # discardedTime = max(firsttimes.values()) - min(firsttimes.values())
  # if discardedTime > 0:
  #   print(f"NB: Discarding up to the first {discardedTime} seconds of data to merge the logs")
  
  # If there are streams with widely varying data rates, then set aside the streams with low rates
  slowerThreshold = args.sth
  dataratemax = max(datarates.values())
  for idx, datarate in enumerate(datarates.values()):
    if datarate < dataratemax / slowerThreshold:
      print(f"NB: Not merging from route {routes[idx]} because its data rate {datarate} Hz < dominant rate {dataratemax} Hz / {slowerThreshold}." )
      tempfiles.pop(routes[idx])
      tempfilenames.pop(routes[idx])
      sensors.pop(routes[idx])
      firsttimes.pop(routes[idx])
      routes.pop(idx)
  
  print(f"Merging data streams from routes:")
  [print(f"- {route} starting {firsttimes[route]}") for route in routes]
  
  # Now write out combined file
  tempfilelist = []
  for routingString in routes:
    fd = open(tempfilenames[routingString], 'r')
    tempfilelist += [ fd ]
  
  with open(outputfile,'w') as fout:
    headerString=""
    for fd in tempfilelist:
      headerString += fd.readline()[:-1] + "\t"
    headerString = headerString[:-1]+"\n"
    fout.write(headerString)
  
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
  
if __name__ == "__main__":
  main()
