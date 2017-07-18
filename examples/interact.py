#!/usr/bin/env python3
"""
Twinleaf vector magnetometer tumble calibrator
License: Twinleaf LLC, all rights reserved
Author: Thomas Kornack <kornack@twinleaf.com>
"""

import tldevice
device = tldevice.Device("tcp://localhost")
device._interact()
