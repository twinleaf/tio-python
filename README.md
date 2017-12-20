# Python Twinleaf I/O

This package implements a communications protocol in python to work with Twinleaf sensors using Twinleaf I/O (TIO) as the communications layer. Data from the sensors is received via PUB messages and sensor parameters may be changed using REQ/REP messages. 

![itio](doc/itio.gif)

![itio](doc/tio_monitor.gif)

macOS and linux are supported platforms. Windows is a work in progress.

On macOS, the devices' serial port enumerates as /dev/cu.usbserial-XXXXXX. On Linux it would be /dev/ttyUSBx.

The python tools can connect directly to the serial port or through a TCP proxy (see tio-tools).