#!/usr/bin/env python3

from setuptools import setup

setup(name='tio',
    version='0.1.0',
    description='Helper libraries and utils for Twinleaf\'s tio-based devices',
    url='https://code.twinleaf.com/open-source/tio-python',
    author='Thomas Kornack',
    author_email='kornack@twinleaf.com',
    license='MIT',
    install_requires=[
        "PyYAML",
        "pyserial",
        "blessings",
    ],
    packages=[
        'tio',
        'slip',
        'tldevice',
    ],
    scripts=[
        'examples/itio.py'
    ],
    zip_safe=False)
