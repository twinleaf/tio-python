#!/usr/bin/env python3
"""
..
    Copyright: 2018 Twinleaf LLC
    Author: kornack@twinleaf.com

"""

import tldevice
import argparse
import time

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

while True:
  print(f"{device.dev.name()} EEPROM Saving...")
  device.dev.conf.save()
  time.sleep(0.5)
  print(f"{device.dev.name()} EEPROM Loading...")
  device.dev.conf.save()
  time.sleep(0.5)
