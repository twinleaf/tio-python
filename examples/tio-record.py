#!/usr/bin/env python3
"""
..
    Copyright: 2022 Twinleaf LLC
    Author: newby@twinleaf.com

Log raw data from TCP port.

"""

import argparse
import socket

parser = argparse.ArgumentParser(prog='tio-record', 
                                 description='Log raw data from TCP port.')
parser.add_argument("file", 
                    type=argparse.FileType('wb'),
                    nargs='?', 
                    default='log.tio',
                    help='filename to store data')
parser.add_argument("-v","--verbosity",
                    type=int,
                    default = 1,
                    help='verbosity; 0 = silent')
args = parser.parse_args()

if args.verbosity>0:
  import halo

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 7855))

if args.verbosity>0:
  spinner = halo.Halo(text=f'Recording to file {args.file.name}', spinner='dots')
  spinner.start()
  spinner.succeed()
  stored = 0
  spinner.start()

with args.file as file:
  while True:
    data = s.recv(1024)
    file.write(data)
    if args.verbosity>0:
      stored += len(data)
      spinner.text = f"Recorded {stored} bytes."

if args.verbosity>0:
  spinner.stop()
s.close()
