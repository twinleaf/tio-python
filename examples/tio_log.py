#!/usr/bin/env python3
"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com

Log data!

"""

import tldevice
import argparse

parser = argparse.ArgumentParser(prog='tio_log', 
                                 description='Very simple logging utility.')

parser.add_argument("url", 
                    nargs='?', 
                    default='tcp://localhost/',
                    help='URL: tcp://localhost')
parser.add_argument("logfile", 
                    nargs='?', 
                    default='log.tsv',
                    help='Log filename: log.tsv')
parser.add_argument("--cmd", 
                    action='append', 
                    default=[],
                    type=lambda kv: kv.split(":"), 
                    help='Commands to be run on start; rpc:val')
args = parser.parse_args()

device = tldevice.Device(url=args.url, commands=args.cmd)

file = open(args.logfile,'w') 

print(f"Logging to {args.logfile} ...")

file.write("\t".join(map(str,device.data.stream_columns()))+"\n")

for row in device.data.stream_iter():
  # Tab delimited data
  rowstring = "\t".join(map(str,row))+"\n"
  # Write line
  file.write(rowstring)


