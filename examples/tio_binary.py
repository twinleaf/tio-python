#!/usr/bin/env python3
# coding: utf-8
"""
Send packet to place device in binary mode.
"""

import serial

url = '/dev/cu.usbmodem14241'
s = serial.serial_for_url(url, baudrate=115200, timeout=1)
packet = bytearray(b'\xc0\x02\x00\x0c\x00g\x9d\x08\x80dev.desc\x86Gq~\xc0')
s.write(packet)
