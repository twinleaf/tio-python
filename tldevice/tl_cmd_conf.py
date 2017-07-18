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
    return self._dev._tio.rpc('conf.save')

  def load(self):
    """Reads settings from EEPROM."""
    return self._dev._tio.rpc('conf.load')

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
      'Device': self._dev.dev.desc(), 
      'Firmware': self._dev.dev.mcu_fw_rev(), 
      'ID': self._dev.dev.mcu_id(),
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
    document = yaml.load(stream)
    #print('Read configuration from file %s"' % filename)

    configuration = {}
    functions = self._enum()
    functionValues = self.download(filename = None)

    mcu_fw_rev = self._dev.dev.mcu_fw_rev()
    dev_desc = self._dev.dev.desc()
    mcu_id = self._dev.dev.mcu_id()

    if document['Device'] != dev_desc:
        print(dev_desc, document['Device'])
        raise Exception(f"Device mismatch: device is '{dev_desc}'; file is '{document['Device']}'.")

    if document['Firmware'] != mcu_fw_rev:
        print(f"Firmware mismatch: device is {mcu_fw_rev}; file is {document['Firmware']}")

    if document['ID'] != mcu_id:
        print(f"ID mismatch: device is {mcu_id}; file is {document['ID']}")

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

