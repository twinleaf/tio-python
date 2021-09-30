#!/usr/bin/env python3
# coding: utf-8

import tldevicesync

tio = tldevicesync.DeviceSync()

print(tio.vmr0.vector.columnnames())

ss = tldevicesync.SyncStream([tio.vmr0.vector,tio.vmr1.vector])

print("\t".join(map(str,ss.columnnames())))

i = 0
for row in ss.iter():
	print("\t".join(map(str,row)))
	i = i+1
	if i > 5:
		break
