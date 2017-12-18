#!/usr/bin/env python3
"""
itio: Interactive Twinleaf I/O 
License: MIT
Author: Thomas Kornack <kornack@twinleaf.com>
"""

import tldevice
import argparse

parser = argparse.ArgumentParser(prog='itio', 
                                 description='Interactive Twinleaf I/O.')

parser.add_argument("url", 
                    nargs='?', 
                    default='tcp://localhost/',
                    help='URL: tcp://localhost')
parser.add_argument("--cmd", 
                    action='append', 
                    default=[],
                    type=lambda kv: kv.split(":"), 
                    help='Commands to be run on start; rpc:val')
parser.add_argument('-v', 
                    action="store_true",
                    default=False,
                    help='Verbose output for debugging')
args = parser.parse_args()

device = tldevice.Device(url=args.url, verbose=args.v, commands=args.cmd)
device._interact()
