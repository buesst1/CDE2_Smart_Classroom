from datetime import datetime
import socket
import ssl
from time import monotonic, sleep
import _bleio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from adafruit_ble import BLEConnection
import adafruit_ble
import json
import os
from iterators import TimeoutIterator

#log file appender
log_fileName = str(os.path.dirname(os.path.realpath(__file__))) + "/log.txt" #full path to cache script
def Write_To_Log_File(clssName:str, text:str):
    """
    Write text to log file 
    format: 'monotonic time': 'clssName': 'text'
    """
    
    timestamp = monotonic()
    with open(log_fileName, "a+") as fd:
        fd.write(str(timestamp) + ": " + clssName + ": " + text + "\n")
        fd.flush()

class SSL:
    def __init__(self, host= 'solarbroom.com', port= 443) -> None:
        self.HOST = host
        self.PORT = port
    
    def __read_from_conn(self, conn:ssl.SSLSocket):
        """
        read message from connection
        returns: received string 
        
        this method can raise an error
        """

        Write_To_Log_File("SSL", "start reading from connection")

        message = "" #message stored here
        while True:
            data = conn.recv(buflen=1024) #read 1024 bytes

            #if no data received
            if data == b"":
                raise Exception(f"No data received.\nAlready read data.\n{message}")

            #decode received bytes and store characters in message (check if endchar received)
            for chr in bytes.decode(data):
                #if endchar received -> return message
                if chr == "\n":
                    Write_To_Log_File("SSL", "sucessfully read from connection")

                    return message

                else: #otherwise add char to message
                    message += chr

    def __Send_Read(self, message:str) -> str:
        """
        Sends message and reives answer -> if a failure occures: None is returned
        """

        #try creating socket
        try:
            Write_To_Log_File("SSL", "start creating binding socket")

            bindsocket = socket.create_connection((self.HOST, self.PORT), timeout=5)
            bindsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            Write_To_Log_File("SSL", "successfully created binding socket")

            print("BindingSocket successfully created")

        except Exception as ex:
            #close eventual open bindsocket
            try:
                bindsocket.close()
            except:
                pass
            
            Write_To_Log_File("SSL", f"exception occured in create binding socket: {ex}")

            print(f"Exception occured during creating bindingSocket: {ex}")
            return None

        #try create sslcontext
        try:
            Write_To_Log_File("SSL", "start wrapping socket")

            context = ssl._create_unverified_context()            
            conn = context.wrap_socket(bindsocket, server_hostname=self.HOST)
            bindsocket.close() #close original socket

            conn.settimeout(5) #set read/write timeout to 5 seconds

            Write_To_Log_File("SSL", "socket successfully wrapped")

            print("SSLSocket successfully created")

        except Exception as ex:
            #close eventual open bindsocket
            try:
                bindsocket.close()
            except:
                pass

            #close eventual open sslsocket
            try:
                conn.close()
            except:
                pass

            Write_To_Log_File("SSL", f"wrapping socket failed: {ex}")

            print(f"Building ssl connection failed: {ex}")    
            return None


        ##send receive message##

        answer = "" #answer from server stored here
        returnNone = False #true if error occured and None should be returned

        #send data to server and expect answer
        try:
            message_bytes = str.encode(message + "\n") #convert to bytes

            print(f"Sending message: {message_bytes}")

            Write_To_Log_File("SSL", "start sending text to server")
            conn.sendall(message_bytes)
            Write_To_Log_File("SSL", "text successfully sent to server")

            print("Message Sent")

            try:
                Write_To_Log_File("SSL", "start reading from server")
                answer = self.__read_from_conn(conn)
                Write_To_Log_File("SSL", "successfully read data from server")

                print(f"Answer received: {answer}")

            except Exception as ex:
                returnNone = True #set flag

                Write_To_Log_File("SSL", f"exception occured in read_from_conn: {ex}")

                print(f"Exception occured during receiving answer from server: {ex}")

        except Exception as ex:
            returnNone = True #set flag

            Write_To_Log_File("SSL", f"exception occured in send data to server: {ex}")

            print(f"Exception occured during sending data to server: {ex}")

        finally:
            
            #close connection
            try:
                conn.shutdown(socket.SHUT_RDWR)
            except Exception as ex:
                print(f"Exception occured in shutdown connection: {ex}")

            try:
                conn.close()
            except Exception as ex:
                print(f"Exception occured in close connection: {ex}")

               
        if returnNone: #error occured and None should be returned
            return None
        else: #data sent successfully
            return answer

    def __Write(self, message: str) -> bool:
        try:
            received = self.__Send_Read(message)

            if received == None: #exception during sending/receiving data
                return False

            elif received == "confirmed": #server stored data successfully
                return True

            elif received == "failed": #data failed to store
                return False

            else:
                raise Exception("unknown confirmation message received")

        except Exception as ex:
            print(f"Unable to send message to server: {ex}")
            return False

    def Send_Jsons(self, jsons:list) -> bool:

        stringified_jsons = []
        for json_ in jsons:
            stringified_jsons.append(json.dumps(json_))

        jsons_appended = ";".join(stringified_jsons)

        return self.__Write("data~"+jsons_appended)
            
class Cache:
    def __init__(self, relative_fileName = "cache") -> None:
        Write_To_Log_File("Cache", "init started")

        self.__script_dir = os.path.dirname(os.path.realpath(__file__)) #<-- absolute dir the script is in
        self.__full_fileName = str(self.__script_dir) + "/" + relative_fileName #full path to cache script

        self.__cache_cleanup_or_creation()#delete invalid data or create file if not existing

        Write_To_Log_File("Cache", "init stopped")

    def __cache_cleanup_or_creation(self):
        try:
            #create file if not exists
            with open(self.__full_fileName,"a+") as fd:
                pass

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
            Write_To_Log_File("Cache", "appending json started")
            #append jsons to cache
            with open(self.__full_fileName, 'a') as fd:
                fd.write(json.dumps(json_file) + "\n")

            Write_To_Log_File("Cache", "appending json successfully finished")

            return True

        except Exception as ex:
            Write_To_Log_File("Cache", f"exception occured in changing json: {ex}")

            print(f"Cache append encountered an error: {ex}")
            return False

    def Cache_Read(self) -> list or None:
        try:
            Write_To_Log_File("Cache", "read cache started")

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

            Write_To_Log_File("Cache", "read cache successfully stopped")

            return json_files   

        except Exception as ex:
            Write_To_Log_File("Cache", f"exception occured in read_cache: {ex}")

            print(f"Cache read encountered an error: {ex}")
            return None

    def Cache_Clear(self) -> bool:
        try:
            Write_To_Log_File("Cache", "start cache clear")

            #clear cache
            with open(self.__full_fileName, 'w') as fd:
                pass

            Write_To_Log_File("Cache", "cache clear successfully finished")

            return True

        except Exception as ex:
            Write_To_Log_File("Cache", f"exception occured in cache clear: {ex}")

            print(f"Cache clear encountered an error: {ex}")
            return False

class BLE:
    def __init__(self, device_names: list) -> None:
        """
        params:
        device_names (list of strings): device_names of measurement devices
        """

        Write_To_Log_File("BLE", "init started")

        self.__device_names = device_names
        
        # CircuitPython <6 uses its own ConnectionError type. So, is it if available. Otherwise,
        # the built in ConnectionError is used.
        connection_error = ConnectionError
        if hasattr(_bleio, "ConnectionError"):
            connection_error = _bleio.ConnectionError

        # PyLint can't find BLERadio for some reason so special case it here.
        self.__ble = adafruit_ble.BLERadio()  # pylint: disable=no-member

        Write_To_Log_File("BLE", "init stopped")

    def __Scan_For_Advertizements(self, timeout_s=10.0) -> dict:
        """
        Scan for advertizements 

        params:
        timeout: timeout of scanning (iteratorTimeout = timeout_s + 5; scanTimeout = timeout_s)
        """
        
        measurement_device_advertizements = {} #advertizements of measurement devices are stored here

        try:
            print("scanning")
            Write_To_Log_File("BLE", "start advertizement scan")

            found_addr = set()
            it = TimeoutIterator(self.__ble.start_scan(ProvideServicesAdvertisement, timeout=timeout_s), timeout_s + 5) #TimeoutIterator used because of: self.__ble.start_scan does not yield anything if nothign is found 
            for advertisement in it: 
                
                #timeout received
                if advertisement == it.get_sentinel():
                    Write_To_Log_File("BLE", "timeout occured during scanning advertizements")

                    print("Iterator timed out... interrupt")
                    break

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
                        Write_To_Log_File("BLE", f"Device with name: {name} and address: {addr} found")

        except Exception as ex:
            print(f"Exception occured in __Scan_For_Advertizements: {ex} ->  restarting bluetooth")
            Write_To_Log_File("BLE", f"Exception occured in __Scan_For_Advertizements: {ex} ->  restarting bluetooth")

            os.system("sudo /etc/init.d/bluetooth  restart")

        self.__Stop_Scan_Save()

        print("scan done")

        Write_To_Log_File("BLE", "scan successfully stopped")

        return measurement_device_advertizements

    def __Stop_Scan_Save(self):
        try:
            self.__ble.stop_scan()
        except:
            pass

    def __TryConnect_ToDevice(self, device_advertisements: ProvideServicesAdvertisement, timeout=10.0) -> list:
        """
        This method tries to connect to all advertizements

        returns:
        keys from advertizements that was unable to connect to
        """

        try:
            Write_To_Log_File("BLE", "connect to device started")

            if UARTService not in device_advertisements.services:
                raise Exception("UART not available for this device")

            Write_To_Log_File("BLE", "successfully tried to device (does not mean that we have successfully connected)")

            return self.__ble.connect(device_advertisements, timeout=timeout)

        except Exception as ex:
            Write_To_Log_File("BLE", f"exception occured in try_connect_to_device: {ex}")
            print(f"Was unable to connect to device:\n{ex}")
            return None

    def __Disconnect_FromDevice_Save(self, connection: BLEConnection):
        try:
            connection.disconnect()

        except:
            pass

    def __Request_Measurements_from_connection(self, connection: BLEConnection, start_read_timeout_s=4.0) -> list:
        """
        This method requests all measurements from all devices

        returns:
        tuple(time of request start as datetime, all received json responses as list)
        """
        
        json_response: json = None

        try:
            Write_To_Log_File("BLE", "request measurement from connection started")

            if UARTService not in connection:
                raise Exception("UART not available for this device")

            uart:UARTService = connection[UARTService]
            uart.timeout = start_read_timeout_s

            uart.write(str.encode("measure_request\n", encoding="utf-8"))

            message = ""
            while True:
                #wait until bytes arrived -> raise exception if no data arrived for too long
                time_ = monotonic()
                while uart.in_waiting < 1:
                    if not connection.connected:
                        raise Exception("connection lost")

                    if monotonic() - time_ >= start_read_timeout_s:
                        raise Exception("connection timed out")

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

            Write_To_Log_File("BLE", "successfully requested measurements from connection")
            
        except Exception as ex:
            Write_To_Log_File("BLE", f"exception occured in request_measurements_from_connection: {ex}")

            print(f"Exception occured in __Request_Measurements_from_connection: {ex}")

        return json_response
                
    def Start_Request(self, max_number_of_tries:int = 5):
        jsons:json = json.loads(json.dumps({deviceName:"BLE_error" for deviceName in self.__device_names})) #create json 

        Write_To_Log_File("BLE", "start advertizement scan")
        adverts = self.__Scan_For_Advertizements()
        Write_To_Log_File("BLE", "successfully finished advertizement scan")

        timeStamp = datetime.now() #get current time
        for deviceName in list(adverts.keys()):
            ad = adverts[deviceName]

            number_of_tries = 0
            while number_of_tries < max_number_of_tries:
                print(f"Try connect to  {deviceName}")

                Write_To_Log_File("BLE", f"try connect to: {deviceName}")

                connection = self.__TryConnect_ToDevice(ad)

                if (connection != None):
                    print(f"Successfully connected to {deviceName} -> start reading")
                    Write_To_Log_File("BLE", f"Successfully connected to {deviceName} -> start reading")

                    answer = self.__Request_Measurements_from_connection(connection)

                    Write_To_Log_File("BLE", f"Finished reading from {deviceName} -> disconnect")
                    print(f"Finished reading from {deviceName} -> disconnect")

                    self.__Disconnect_FromDevice_Save(connection) #disconnect if a connection was opened

                    Write_To_Log_File("BLE", f"Disconnected from {deviceName}")
                    print(f"Disconnected from {deviceName}")

                    #getting data was successful
                    if answer != None:
                        jsons[deviceName] = answer

                        print(f"Successfully got data from {deviceName}")
                        Write_To_Log_File("BLE", f"Successfully got data from {deviceName}")

                    else:
                        Write_To_Log_File("BLE", "Successfully connected to {deviceName} but was unable to get data")
                        print(f"Successfully connected to {deviceName} but was unable to get data")
                        
                    break #end 

                else:
                    Write_To_Log_File("BLE", f"Was unable to connect to {deviceName}")
                    print(f"Was unable to connect to {deviceName}")

                number_of_tries += 1 #increment counter

        return (timeStamp, jsons)

server = SSL()
ble = BLE(["Device1", "Device2", "Device3"])
cache = Cache()

while True:
    try:
        Write_To_Log_File("Main", "sleep for 30 seconds start")
        #wait 30s
        timestamp = monotonic()
        while (monotonic() - timestamp) < 30:
            sleep(1)
        Write_To_Log_File("Main", "sleep for 30 seconds finished")

        #start measurement
        all_jsons = [] #all measurements are stored here

        #start a ble request
        Write_To_Log_File("Main", "request for data started")
        start_Time, jsons = ble.Start_Request()
        new_measurement = json.dumps({"timeStamp":start_Time.strftime("%d/%m/%Y %H:%M:%S"), "data":jsons})  
        Write_To_Log_File("Main", "successfully read data from ble and dumped to json")

        #read cached jsons
        Write_To_Log_File("Main", "start cache things")
        cached_jsons = cache.Cache_Read() 

        #append jsons
        all_jsons.append(new_measurement) 

        if cached_jsons != None:
            all_jsons.extend(cached_jsons)
        
        Write_To_Log_File("Main", "successfully stopped cache things")
        
        Write_To_Log_File("Main", "start send data to server")
        #if jsons sent successfully
        if server.Send_Jsons(all_jsons):
            Write_To_Log_File("Main", "successfully sent data to server -> delete cache")

            if not cache.Cache_Clear():#clear cache
                raise Exception("cache could not be cleared")

        else:
            Write_To_Log_File("Main", "send data to server failed -> cache data")
            print("Data Cached")

            if not cache.Cache_Append_Json(new_measurement):
                raise Exception("cache could not be extended")

    except Exception as ex:
        Write_To_Log_File("Main", f"exception occured in main loop: {ex}")
        print(f"Exception occured in MainLoop: {ex}")