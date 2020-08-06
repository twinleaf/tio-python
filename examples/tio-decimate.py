#!/usr/bin/env python3
# coding: utf-8
"""
Send command to slow down the data rate.
"""

import serial

# url = 'COM6'
url = '/dev/cu.usbserial-DM01LNO6'

s = serial.serial_for_url(url, baudrate=115200, timeout=1)
packet = bytearray(b'data.rate 10\r')
s.write(packet)
