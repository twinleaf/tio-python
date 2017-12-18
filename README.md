# Twinleaf Sensor Control Software (Python)

This package implements a communications protocol in python to work with Twinleaf sensors using TIO as the communications layer. Data from the sensors is received via PUB messages and sensor parameters may be changed using REQ/REP messages. 

## Requirements

macOS and linux are supported platforms. Windows might work, but we haven't tried it.

The python library does not implement raw serial access. It is necessary to use the TIO serial proxy program to convert the serial stream to a TCP port. Multiple programs may connect to the proxy's TCP server. So, first install both libtio and tio-tools in a directory. Then:

  cd libtio
  make
  cd ..

  cd tio-tools
  make
  cd bin
  ./proxy /dev/cu.usbserial-XXXXXX

On macOS, the devices' serial port enumerates as /dev/cu.usbserial-XXXXXX. On Linux it would be /dev/ttyUSBx

## Example scripts

The following scripts are found in the `examples/` directory:
 
  interact.py         A quick means for reading and writing settings

