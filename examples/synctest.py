#!/usr/bin/env python3
import time
import tldevicesync
import sys
import blessings

def get(d, keys):
    if "." in keys:
        key, rest = keys.split(".", 1)
        if key in d:
          return get(d[key], rest)
        else:
          return None
    else:
      if keys in d:
        return d[keys]
      else:
        None

rpc = [
  ['vector.data.decimation', 'i32', '40'],
  ]
tio = tldevicesync.DeviceSync(connectionTime=5, rpcs=rpc)

devices = [tio.vmr0, tio.vmr1]
streams = ['vector', 'accel']
ss = tldevicesync.SyncStream(devices=devices,streams=streams)
    
term = blessings.Terminal()
fields = ['time', 'vector.x', 'vector.y', 'vector.z', 'accel.x', 'accel.y', 'accel.z', 'gyro.x', 'gyro.y', 'gyro.z', 'bar', 'therm']
for row in ss.iter():
  for name, device in row.items():
    sys.stdout.write(f"\r\n{term.clear_eol}{name}")
    for field in fields:
      data = get(device, field)
      sys.stdout.write(f"\r\n {field}: {data or ''}")
  sys.stdout.write(f"\r\n")
  sys.stdout.write(term.clear_eos)
  sys.stdout.write(term.move_up*(1+len(row)*(len(fields)+3)))