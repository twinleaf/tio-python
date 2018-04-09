#!/usr/bin/env python3
# coding: utf-8
"""
Send packet to place device in binary mode.
"""

import serial

url = '/dev/cu.usbserial-DM00DYJN'
s = serial.serial_for_url(url, baudrate=115200, timeout=1)
packet = bytearray(b'dev.desc\r')
s.write(packet)
