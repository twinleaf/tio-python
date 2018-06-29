#!/usr/bin/env python3
"""
..
    Copyright: 2018 Twinleaf LLC
    Author: kornack@twinleaf.com

Repeatedly connect and report a single data point.

"""

import tldevice

while True:
  device = tldevice.Device(stateCache=False)
  if device.data.stream_columns() != []:
    datadict = {}
    for datum, column in zip(device.data.stream(), device.data.stream_columns()):
      datadict[column] = datum
    print(f"Data: {datadict}")
  device._close()

