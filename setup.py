from setuptools import setup

setup(name='tio',
    version='3.5.3',
    description='Helper libraries and utils for Twinleaf I/O (TIO) devices',
    long_description="Twinleaf I/O is a serialization for kilohertz rate data from data-intensive sensors connected by serial ports or tunneled through TCP.",
    url='https://github.com/twinleaf/tio-python',
    author='Thomas Kornack',
    author_email='kornack@twinleaf.com',
    license='MIT',
    python_requires='>=3.6',
    install_requires=[
        'PyYAML',
        'pyserial',
        'blessings',
        'hexdump',
    ],
    packages=[
        'tio',
        'slip',
        'tldevice',
        'tldevicesync',
    ],
    zip_safe=False)
