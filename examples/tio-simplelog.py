#!/usr/bin/env python3
import tldevice
vmr = tldevice.Device()
file = open('log.tsv','w') 
for row in vmr.data.iter():
  rowstring = "\t".join(map(str,row))+"\n"
  file.write(rowstring)
