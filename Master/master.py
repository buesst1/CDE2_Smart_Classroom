from datetime import datetime
from math import fabs
import socket
import ssl
from time import monotonic, sleep, time
import _bleio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_ble import BLEConnection
import json
import os

class SSL:
    def __init__(self, host= 'solarBroom.com', port= 443) -> None:
        self.HOST = host
        self.PORT = port

    def __Send_Read(self, message:str) -> str:
        context = ssl.create_default_context()
        with socket.create_connection((self.HOST, self.PORT)) as sock:
            with context.wrap_socket(sock, server_hostname=self.HOST) as ssock:
    
                ssock.write(str.encode(message, encoding="utf-8"))

                return ssock.read().decode(encoding="utf-8")

    def __Write(self, message: str) -> bool:
        try:
            received = self.__Send_Read()

            if received != "confirmed":
                raise Exception("unknown confirmation message received")

            return True

        except Exception as ex:
            print(f"Unable to send message to server: {ex}")
            return false

    def Send_Jsons(self, jsons:list) -> bool:

        stringified_jsons = []
        for json_ in jsons:
            stringified_jsons.append(json.dumps(json_))

        jsons_appended = "ʮ".join(stringified_jsons)

        return self.__Write("data~"+jsons_appended)
            
class Cache:
    def __init__(self, relative_fileName = "cache") -> None:
        self.__script_dir = os.path.dirname(__file__) #<-- absolute dir the script is in
        self.__full_fileName = str(self.__script_dir) + "/" + relative_fileName #full path to cache script

        self.__cache_cleanup()#delete invalid data

    def __cache_cleanup(self):
        try:
            #read content of caches
            with open(self.__full_fileName, "r") as fd:
                content:str = fd.read()

            #check if strings are valid jsons
            json_files = []
            for json_string in content.split("\n"):
                if len(json_string) > 0:
                    try:
                        json_files.append(json.loads(json_string))
                    except:
                        print("Measurement lost during cache cleanup...")

            #clear cache
            with open(self.__full_fileName, 'w'):
                pass

            #append jsons to cache
            with open(self.__full_fileName, 'a') as fd:
                for json_file in json_files:
                    fd.write(json.dumps(json_file) + "\n")

        except Exception as ex:
            print(f"Cache cleanup encountered an error: {ex}")

    def Cache_Append_Json(self, json_file:json) -> bool:
        try:
            #append jsons to cache
            with open(self.__full_fileName, 'a') as fd:
                fd.write(json.dumps(json_file) + "\n")

            return True

        except Exception as ex:
            print(f"Cache append encountered an error: {ex}")
            return False

    def Cache_Read(self) -> list or None:
        try:
            #read content of caches
            with open(self.__full_fileName, "r") as fd:
                content:str = fd.read()

            #check if strings are valid jsons and store them
            json_files = []
            for json_string in content.split("\n"):
                if len(json_string) > 0:
                    try:
                        json_files.append(json.loads(json_string))
                    except:
                        print("Measurement lost during cache reading...")

            return json_files   

        except Exception as ex:
            print(f"Cache read encountered an error: {ex}")
            return None

    def Cache_Clear(self) -> bool:
        try:
            #clear cache
            with open(self.__full_fileName, 'w'):
                pass

        except Exception as ex:
            print(f"Cache clear encountered an error: {ex}")

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

    def __TryConnect_ToDevice(self, device_advertisements: ProvideServicesAdvertisement) -> list:
        """
        This method tries to connect to all advertizements

        returns:
        keys from advertizements that was unable to connect to
        """

        try:
            if UARTService not in device_advertisements.services:
                raise Exception("UART not available for this device")

            return self.__ble.connect(device_advertisements)

        except Exception as ex:
            print(f"Was unable to connect to device:\n{ex}")
            return None
        
    def __Disconnect_FromDevice_Save(self, connection: BLEConnection):
        try:
            connection.disconnect()

        except:
            pass

    def __Request_Measurements_from_connection(self, connection: BLEConnection, start_read_timeout_s=4) -> list:
        """
        This method requests all measurements from all devices

        returns:
        tuple(time of request start as datetime, all received json responses as list)
        """
        
        json_response: json = None

        try:
            if UARTService not in connection:
                raise Exception("UART not available for this device")

            uart:UARTService = connection[UARTService]
            uart.timeout = start_read_timeout_s

            uart.write(str.encode("measure_request\n", encoding="utf-8"))

            message = ""
            while True:
                #wait until bytes arrived
                while uart.in_waiting < 1:
                    if not connection.connected:
                        raise Exception("connection lost")

                byte_:bytes = uart.read(1)

                if byte_ == None:
                    raise Exception("Connection timeout")

                received_char = str(byte_.decode("utf-8"))

                if received_char:
                    if received_char != "\n":
                        message += received_char

                    else:
                        json_response = json.loads(message)
                        break
            
        except Exception as ex:
            print(f"Exception occured in __Request_Measurements_from_connection: {ex}")

        return json_response
                
    def Start_Request(self):
        jsons:json = json.dumps({deviceName:"BLE_error" for deviceName in self.__device_names}) #create json 

        adverts = self.__Scan_For_Advertizements()

        timeStamp = datetime.now() #get current time
        for deviceName in list(adverts.keys()):
            ad = adverts[deviceName]

            connection = self.__TryConnect_ToDevice(ad)

            if (connection != None):
                answer = self.__Request_Measurements_from_connection(connection)

                self.__Disconnect_FromDevice_Save() #disconnect if a connection was opened

                #getting data was successful
                if answer != None:
                    jsons[deviceName] = answer

            else:
                print(f"Was unable to connect to {deviceName}")

            

        return (timeStamp, jsons)

server = SSL()
ble = BLE(["MainSensor"])
cache = Cache()

while True:
    #wait 10s
    timestamp = monotonic()
    while (monotonic() - timestamp) < 10:
        sleep(1)


    #start measurement
    all_jsons = [] #all measurements are stored here

    #start a ble request
    start_Time, jsons = ble.Start_Request()
    new_measurement = json.dumps({"timeStamp":start_Time, "data":jsons})  

    #read cached jsons
    cached_jsons = cache.Cache_Read() 

    #append jsons
    all_jsons.append(new_measurement) 

    if cached_jsons != None:
        all_jsons.extend(cached_jsons)
    
    #if jsons sent successfully
    if server.Send_Jsons(all_jsons):
        if not cache.Cache_Clear():#clear cache
            raise Exception("cache could not be cleared")

    else:
        if not cache.Cache_Append_Json(new_measurement):
            raise Exception("cache could not be extended")

    sleep(10)
