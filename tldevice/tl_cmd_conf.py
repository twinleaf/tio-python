"""
..
    Copyright: 2017 Twinleaf LLC
    Author: kornack@twinleaf.com
    OriginalDate: March 2017
"""

import struct
import yaml
import tio

class TwinleafConfigController(object):
  def __init__(self, dev):
    self._dev = dev

  def save(self):
    """Commits settings to EEPROM."""
    return self._dev._tio.rpc('dev.conf.save')

  def load(self):
    """Reads settings from EEPROM."""
    return self._dev._tio.rpc('dev.conf.load')

  def _enum(self):
    """
    Returns a list of (item_type, item_prefix) that are stored on device
    """
    enum_list = []
    for rpc in self._dev._tio.rpcs:
      if rpc['stored']:
        enum_list += [(rpc['name'],rpc['datatype'])]
    return enum_list

  def download(self, filename = "config.yaml"):
    """
    Reads all values that are saved to EEPROM
    """
    configuration = {}
    functions = self._enum()
    for function, function_type in functions:
      value = self._dev._tio.rpc_val(function, rpcType=function_type)
      configuration[function] = value
    document = {
      'Name': self._dev.dev.name(),
      'Revision': self._dev.dev.revision(),
      'Serial': self._dev.dev.serial(),
      'Firmware': self._dev.dev.firmware.serial(), 
    }
    document['Configuration'] = configuration
    if filename:
      stream = open(filename, 'w')
      yaml.dump(document, stream, default_flow_style=False)
      print('Wrote configuration to file %s' % filename)
    return configuration

  def upload(self, filename="config.yaml"):
    """
    Writes values from file to device
    """
    stream = open(filename, 'r')
    document = yaml.load(stream, Loader=yaml.SafeLoader)

    configuration = {}
    functions = self._enum()
    functionValues = self.download(filename = None)

    dev_name = self._dev.dev.name()
    revision = self._dev.dev.revision()
    serial = self._dev.dev.serial()
    firmware = self._dev.dev.firmware.serial()

    if document['Name'] != dev_name:
      raise Exception(f"Device mismatch: device is '{dev_name}'; file is '{document['Name']}'.")

    if document['Revision'] != revision:
      print(f"ID mismatch: device is {revision}; file is {document['Revision']}")

    if document['Serial'] != serial:
      print(f"ID mismatch: device is {serial}; file is {document['Serial']}")

    if document['Firmware'] != firmware:
      print(f"Firmware mismatch: device is {firmware}; file is {document['Firmware']}")

    for function in document['Configuration'].keys():
      if function not in functionValues.keys():
        print(f'Skipping configuration for {function}; variable not available on device.')

    for function, function_type in functions:
      if function in list(document['Configuration'].keys()):
        valueConfig = document['Configuration'][function]
        valueDevice = functionValues[function]
        if valueDevice == valueConfig:
          print(f'Skipping configuration for {function}; value {valueConfig} not changed.')
        else:
          try: 
            self._dev._tio.rpc_val(function, function_type, valueConfig)
            print(f'Changing configuration for {function} from {valueDevice} to {valueConfig}.')
          except:
            print(f'Error changing configuration for {function} from {valueDevice} to {valueConfig}.')
      else:
        print(f'Skipping configuration for {function}; value not provided (is it a new variable on device?).')

