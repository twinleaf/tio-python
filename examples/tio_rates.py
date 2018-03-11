#!/usr/bin/env python3
"""
..
    Copyright: 2018 Twinleaf LLC
    Author: kornack@twinleaf.com

Print stream and source information.

"""

import tldevice

def rateReport(dev):
  timebase_id = dev._tio.dstreamInfo['dstream_timebase_id']
  print(f"Stream 0: timebase ID: {timebase_id}"
       +f", components: {dev._tio.dstreamInfo['dstream_total_components']}"
       +f", period: {dev._tio.dstreamInfo['dstream_period']}")
  print(f"Timebase {timebase_id} rate: {dev._tio.timebases[timebase_id]['timebase_Fs']:.2f} Hz"
       +f" ({dev._tio.timebases[timebase_id]['timebase_period_num_us']}/{dev._tio.timebases[timebase_id]['timebase_period_denom_us']} µs)"
       +f", epoch: {dev._tio.timebases[timebase_id]['timebase_epoch']}"
       +f", stability: {dev._tio.timebases[timebase_id]['timebase_stability_ppb']:.0f} ppb")
  for i, column in enumerate(dev._tio.streams):
    print(f"Component {i}: {column['source_name']} ({column['source_title']}), period {column['source_period']}, {column['stream_Fs']:.2f} Hz")

if __name__ == "__main__":
  import argparse
  parser = argparse.ArgumentParser(prog='tio_rates', 
                                   description='Live Twinleaf I/O Data Stream Monitor.')
  parser.add_argument("url", 
                      nargs='?', 
                      default='tcp://localhost/',
                      help='URL: tcp://localhost')
  args = parser.parse_args()
  device = tldevice.Device(url=args.url)
  rateReport(device)

