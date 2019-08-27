#!/usr/bin/env python3
# coding: utf-8

import tldevicesync

tio = tldevicesync.DeviceSync()

syncStreams = tio.syncStreamsStart([tio.vmr0.vector,tio.vmr1.vector])
data = tio.syncStreamsRead(syncStreams, samples=3)
print(data)