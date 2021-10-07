#!/usr/bin/env python3
# coding: utf-8

import tldevicesync

tio = tldevicesync.DeviceSync()

ss = tldevicesync.SyncStream([tio.vmr0.data,tio.vmr1.data])
print("\t".join(map(str,ss.columnnames())))
for x in range (5):
	row = next(ss.iter())
	print("\t".join(map(str,row)))

ss = tldevicesync.SyncStream([tio.vmr0.vector,tio.vmr1.vector])
print("\t".join(map(str,ss.columnnames())))
for x in range (5):
	row = next(ss.iter())
	print("\t".join(map(str,row)))
