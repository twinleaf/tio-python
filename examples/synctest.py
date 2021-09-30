#!/usr/bin/env python3
# coding: utf-8

import tldevicesync

tio = tldevicesync.DeviceSync()
ss = tldevicesync.SyncStream([tio.vmr0.data,tio.vmr1.data])

# Columns
print("\t".join(map(str,ss.columnnames())))

# Data
i = 0
for row in ss.iter():
	print("\t".join(map(str,row)))
	i = i+1
	if i > 5:
		break
