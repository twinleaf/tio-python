#!/usr/bin/env python3
"""
itio: Interactive Twinleaf I/O 
License: MIT
Author: Thomas Kornack <kornack@twinleaf.com>
"""

import tldevice
device = tldevice.Device("tcp://localhost")
device._interact()
