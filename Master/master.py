from datetime import datetime
import socket
import ssl
from typing import Tuple
import _bleio
import adafruit_ble
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
import json

class SSL:
    def __init__(self) -> None:
        self.HOST = 'solarBroom.com'
        self.PORT = 443

    def __Send_Read(self, message:str):
        context = ssl.create_default_context()
        with socket.create_connection((self.HOST, self.PORT)) as sock:
            with context.wrap_socket(sock, server_hostname=self.HOST) as ssock:
    
                ssock.write(str.encode(message, encoding="utf-8"))

                return ssock.read()

class BLE:
    def __init__(self, device_names: list) -> None:
        """
        params:
        device_names (list of strings): device_names of measurement devices
        """

        self.__device_names = device_names

        self.__device_advertisements = {} #device advertisements are stored here as dictionoary (key: device name, value: advertisement)
        
        # CircuitPython <6 uses its own ConnectionError type. So, is it if available. Otherwise,
        # the built in ConnectionError is used.
        connection_error = ConnectionError
        if hasattr(_bleio, "ConnectionError"):
            connection_error = _bleio.ConnectionError

        # PyLint can't find BLERadio for some reason so special case it here.
        self.__ble = adafruit_ble.BLERadio()  # pylint: disable=no-member

    def __Scan_For_Advertizements(self) -> dict:

        measurement_device_advertizements = {} #advertizements of measurement devices are stored here

        print("scanning")
        found_addr = set()
        for advertisement in self.__ble.start_scan(ProvideServicesAdvertisement, timeout=5):
            addr = advertisement.address

            if addr not in found_addr:
                found_addr.add(addr)

                name_raw = advertisement.complete_name

                if not name_raw:
                    continue

                name = name_raw.strip("\x00")

                if name in self.__device_names:
                    measurement_device_advertizements[name] = advertisement
                    print(f"Device with name: {name} and address: {addr} found")

        print("scan done")

        return measurement_device_advertizements

    def __Connect_ToAllAvailableDevices(self) -> list:
        """
        This method tries to connect to all advertizements

        returns:
        keys from advertizements that was unable to connect to
        """
        
        failed_devices = [] #device names that was unable to connect to are stored here

        for advertizement_key in list(self.__device_advertisements.keys()):
            advertizement = self.__device_advertisements[advertizement_key]
        
            try:
                if UARTService not in advertizement.services:
                    raise Exception("UART not available for this device")

                self.__ble.connect(advertizement)

            except Exception as ex:
                print(f"Was unable to connect to {advertizement_key}:\n{ex}")

        return failed_devices

    def __Request_Measurements_from_all_connections(self, start_read_timeout_s=4, read_buffer_size = 10000) -> Tuple:
        """
        This method requests all measurements from all devices

        returns:
        tuple(time of request start as datetime, all received json responses as list)
        """
        
        json_responses = []
        start_time = datetime.now()

        while self.__ble.connected and any(UARTService in connection for connection in self.__ble.connections):
            for connection in self.__ble.connections:
                try:
                    if UARTService not in connection:
                        raise Exception("UART not available for this device")

                    uart = connection[UARTService]
                    uart.buffer_size = read_buffer_size

                    uart.reset_input_buffer()

                    uart.write(str.encode("measure_request\n", encoding="utf-8"))
                    uart.timeout = start_read_timeout_s

                    #wait until bytes arrived
                    while uart.in_waiting < 1:
                        if not connection.connected:
                            raise Exception("connection lost")

                    bytes_ = uart.readline()  #read a byte -> returns b'' if nothing was read.

                    if bytes_ == None:
                        raise Exception("Connection failed")

                    message = str(bytes_.decode("utf-8"))
                    message = message.rstrip("\n")
                    message = message.rstrip("\r")

                    print(message)
                    json_responses.append(json.loads(message)) 

                except Exception as ex:
                    print(f"Exception occured in Request_Measurements_from_all_connections: {ex}")

                try:
                    connection.disconnect()

                except:
                    pass
                

        return (start_time, json_responses)
                
    def Start_Request(self):
        #if we dont have all advertizements of all registered devices -> search for devices
        if set(self.__device_names) != set(self.__device_advertisements.keys()): 
            adverts = self.__Scan_For_Advertizements()

            for ad in list(adverts.keys()):
                if ad not in self.__device_advertisements.keys(): #if we found a device that we don't have an advertizement from
                    self.__device_advertisements[ad] = adverts[ad] #append new advertizement 

        
        connection_unavailable_deviceNames = self.__Connect_ToAllAvailableDevices()

        for device_name in connection_unavailable_deviceNames:
            self.__device_advertisements.pop(device_name, None) #remove device from available dict

        timeStamp, jsons = self.__Request_Measurements_from_all_connections()

        print(jsons)


ble = BLE(["MainSensor"])
ble.Start_Request()
