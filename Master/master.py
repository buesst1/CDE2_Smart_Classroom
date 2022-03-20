from ast import While
from datetime import datetime
import socket
import ssl
from time import sleep
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

    def __Connect_ToAllAvailableDevices(self, device_advertisements: dict) -> list:
        """
        This method tries to connect to all advertizements

        returns:
        keys from advertizements that was unable to connect to
        """
        
        failed_devices = [] #device names that was unable to connect to are stored here

        for advertizement_key in list(device_advertisements.keys()):
            advertizement = device_advertisements[advertizement_key]
        
            try:
                if UARTService not in advertizement.services:
                    raise Exception("UART not available for this device")

                self.__ble.connect(advertizement)

            except Exception as ex:
                print(f"Was unable to connect to {advertizement_key}:\n{ex}")

        return failed_devices

    def __Request_Measurements_from_all_connections(self, start_read_timeout_s=4) -> Tuple:
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
                    uart.timeout = start_read_timeout_s

                    uart.write(str.encode("measure_request\n", encoding="utf-8"))

                    message = ""
                    while True:
                        #wait until bytes arrived
                        while uart.in_waiting < 1:
                            if not connection.connected:
                                raise Exception("connection lost")

                        byte_ = uart.read(1)

                        if byte_ == None:
                            raise Exception("Connection failed")

                        received_char = str(byte_.decode("utf-8"))

                        if received_char:
                            if received_char != "\n":
                                message += received_char

                            else:
                                json_responses.append(json.loads(message)) 

                                break
                    

                except Exception as ex:
                    print(f"Exception occured in Request_Measurements_from_all_connections: {ex}")

                try:
                    connection.disconnect()

                except:
                    pass
                

        return (start_time, json_responses)
                
    def Start_Request(self):
        #if we dont have all advertizements of all registered devices -> search for devices
        adverts = self.__Scan_For_Advertizements()
        
        connection_unavailable_deviceNames = self.__Connect_ToAllAvailableDevices(adverts)

        for device_name in connection_unavailable_deviceNames:
            self.__device_advertisements.pop(device_name, None) #remove device from available dict

        timeStamp, jsons = self.__Request_Measurements_from_all_connections()

        return (timeStamp, jsons)

ble = BLE(["MainSensor"])
while True:
    print(ble.Start_Request())

    sleep(10)
