from time import sleep
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from analogio import AnalogIn
import adafruit_dht
import adafruit_scd30
import board
import busio 
import supervisor
import json


class blueTooth:
    def __init__(self, deviceName: str, start_read_timeout_s=10):
        self.__ble = BLERadio()
        self.__ble.name = deviceName

        self.__uart = UARTService()
        self.__uart.timeout = start_read_timeout_s

        self.__advertisement = ProvideServicesAdvertisement(self.__uart)

    def Advertise_Until_Connected_Sync(self):
        """
        This method advertizes and waits until a device connected to feather
        """
        
        self.__ble.start_advertising(self.__advertisement) #start advertising

        #wait until connected
        while not self.__ble.connected:
            continue

        self.__ble.stop_advertising() #stop advertising

    def Wait_For_Connection_Sync(self):
        """
        This method will wait until a client has connected
        """

        #wait for connection
        while not self.__ble.connected:
            continue

    def Is_Connected(self):
        return self.__ble.connected

    def Read_Message_Sync(self) -> str:
        """
        This method reads incoming data

        params:
        timeout_ms (int) -> reading has to finish within timeout_ms
        end_char (char) -> end character
        max_num_of_received_chars (int) -> max number of characters to be reiceved to avoid an overflow of ram
        """

        if not self.__ble.connected:
            raise Exception("not connected to a device")

        #wait until bytes arrived
        while self.__uart.in_waiting < 1:
            if not self.__ble.connected:
                raise Exception("connection lost")

        bytes_ = self.__uart.readline()  #read a byte -> returns b'' if nothing was read.

        if bytes_ == None:
            raise Exception("Connection failed")

        message = str(bytes_.decode("utf-8"))
        message = message.rstrip("\n")
        message = message.rstrip("\r")

        return message 
            
    def Write_Message_Sync(self, message: str):
        buffer = str.encode(message + "\n", "utf-8")
        self.__uart.write(buffer)

    def Send_Message_Sync(self, message: str, end_char = '*'):
        pass

    def Clear_Buffer(self):
        self.__uart.reset_input_buffer()

class SCD30_Sensor:
    def __init__(self, i2c_address = 0x61):
        self.__i2c = busio.I2C(board.SCL, board.SDA, frequency=1000)  # for FT232H, use 1KHz
        self.__scd = adafruit_scd30.SCD30(self.__i2c, address=i2c_address)

        self.__temp_celcius = None
        self.__relHum_percent = None
        self.__co2_ppm = None

    def __readSensors(self):
        if self.__scd.data_available:
            self.__temp_celcius = float(self.__scd.temperature)
            self.__relHum_percent = float(self.__scd.relative_humidity)
            self.__co2_ppm = float(self.__scd.CO2)

    def Read_CO2_PPM(self) -> float:
        self.__readSensors()

        if self.__co2_ppm == None:
            raise Exception("SCD30_Sensor: CO2: No data available")

        return self.__co2_ppm

    def Read_Rel_Hum_Percent(self) -> float:
        self.__readSensors()

        if self.__relHum_percent == None:
            raise Exception("SCD30_Sensor: Humidity: No data available")

        return self.__relHum_percent
    
    def Read_Temp_Celcius(self) -> float:
        self.__readSensors()

        if self.__temp_celcius == None:
            raise Exception("SCD30_Sensor: Temperature: No data available")

        return self.__temp_celcius

class DHT_Temperature_Sensor:
    def __init__(self, pin: board):
        self.__dhtDevice = adafruit_dht.DHT11(pin)

    def Read_Temp_Celcius(self):
        counter = 0
        while (True):

            try:
                return self.__dhtDevice.temperature
            except:
                pass


            counter += 1

            if counter >= 10:
                raise Exception("Sensor failed to read")

    def Read_Humidity_Percent(self):
        counter = 0
        while (True):

            try:
                return self.__dhtDevice.humidity

            except:
                pass


            counter += 1

            if counter >= 10:
                raise Exception("Sensor failed to read")

class Light_Sensor:
    def __init__(self, pin: board):
        self.__analogRead = AnalogIn(pin)

    def _Read_Resistance_Ohms(self):
        ref_voltage = self.__analogRead.reference_voltage
        voltage_R1 = (ref_voltage / 65536) * self.__analogRead.value #calculate voltage on pin
        voltage_Sensor = ref_voltage - voltage_R1

        current = voltage_R1 / 68000 #calculate current through sensor (voltage over R1 / R1 (68kOhm))

        R_Sensor = voltage_Sensor / current #calcualte resistance of sensor

        return R_Sensor

class Sensors(object):
    SCD30_Sensor = "CO2_Sensor"
    DHT_Sensor = "DHT_Sensor"

class Error(object):
    PhysicalConnectionerror = "physical_connection_error" #cannot communiacte with device
    ReadFailure = "read_failed" #cannot read measurement

class Manager:
    def __init__(self, sensors: list, deviceName: str, time_until_advertize_s = 15):
        """
        parameter:
        sensors (list of Sensors to activate)
        """

        self.__sensors = sensors
        self.__deviceName = deviceName
        self.__ble = blueTooth(deviceName)
        self.__time_until_advertize_s = time_until_advertize_s

        #init sensor classes

        self.__scd_30_sensor = None
        self.__dht_sensor = None

        self.__Init_Sensors()

    def __Init_Sensors(self):
        if Sensors.SCD30_Sensor in self.__sensors:
            try:
                self.__scd_30_sensor = SCD30_Sensor()
            except:

                self.__scd_30_sensor = Error.PhysicalConnectionerror

        if Sensors.DHT_Sensor in self.__sensors:
            try:
                self.__dht_sensor = DHT_Temperature_Sensor()
            except:
                self.__dht_sensor = Error.PhysicalConnectionerror

    def Wait_For_Connection_sync(self):
        """
        This function waits for a bluetooth connection and starts advertizing after a specific period of time
        """
        
        now = supervisor.ticks_ms()

        connected = False
        while(((supervisor.ticks_ms() - now) / 1000) <= self.__time_until_advertize_s):
            #has a bluetooth connection
            if self.__ble.Is_Connected():
                connected = True
                break

            sleep(1) #wait a second

        #if not connected -> start advertizing
        if not connected:
            self.__ble.Advertise_Until_Connected_Sync()
        
    def Read_Message_From_BLE(self):
        return self.__ble.Read_Message_Sync()

    def Write_Message_To_BLE(self, message: str):
        self.__ble.Write_Message_Sync(message)

    def Read_Measures(self) -> dict:
        measure_dict = {}
        measure_dict["deviceName"] = self.__deviceName

        sensors = {}

        #if sensor active
        if self.__scd_30_sensor != None:
            scd_30_sensor = {}

            if self.__scd_30_sensor != Error.PhysicalConnectionerror: 
                measurements = {}

                try:
                    measurements["SCD_30_CO2"] = self.__scd_30_sensor.Read_CO2_PPM()
                except:
                    measurements["SCD_30_CO2"] = Error.ReadFailure

                try:
                    measurements["SCD_30_HUM"] = self.__scd_30_sensor.Read_Rel_Hum_Percent()
                except:
                    measurements["SCD_30_HUM"] = Error.ReadFailure

                try:
                    measurements["SCD_30_TEMP"] = self.__scd_30_sensor.Read_Temp_Celcius()
                except:
                    measurements["SCD_30_TEMP"] = Error.ReadFailure

                scd_30_sensor["measurements"] = measurements

            else:
                scd_30_sensor["measurements"] = Error.PhysicalConnectionerror

            sensors["scd_30_sensor"] = scd_30_sensor
            

        measure_dict["sensors"] = sensors

        return measure_dict

    def Clear_InBuffer(self):
        self.__ble.Clear_Buffer()

manager = Manager([Sensors.SCD30_Sensor], "MainSensor")

while True:
    manager.Clear_InBuffer()
    
    manager.Wait_For_Connection_sync() #wait for a ble connection
    
    print("Connected")

    #try handle command
    try:
        pass

    except Exception as ex:
        print(f"Exception in handle command: {ex}")

    message = manager.Read_Message_From_BLE()

    print("\r" in message)

    if message == "measure_request":

        stringified_json = json.dumps(manager.Read_Measures())

        print(stringified_json)

        manager.Write_Message_To_BLE(stringified_json)

    else:
        raise Exception("Unknown command received")

    sleep(5) #sleep 5 sec 

    