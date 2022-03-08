from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from analogio import AnalogIn
import adafruit_dht
import adafruit_scd30
import board
import busio 
import time


class blueTooth:
    def __init__(self, deviceName: str, end_char = "*"):
        self.__ble = BLERadio()
        self.__ble.name = deviceName
        self.__uart = UARTService()
        self.__advertisement = ProvideServicesAdvertisement(self.__uart)
        
        self.__end_char = end_char

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

    def Read_Message_Sync(self, max_num_of_received_chars = 10) -> str:
        """
        This method reads incoming data

        params:
        timeout_ms (int) -> reading has to finish within timeout_ms
        end_char (char) -> end character
        max_num_of_received_chars (int) -> max number of characters to be reiceved to avoid an overflow of ram
        """
        
        message = "" #received stored here

        startTime = time.monotonic() #store time for timeout

        while True:
            if not self.__ble.connected:
                raise ConnectionAbortedError()

            one_byte = self.__uart.read(1).decode("utf-8")  #read a byte -> returns b'' if nothing was read.

            #if a byte received
            if one_byte:
                if one_byte != self.__end_char : #if data (no endchar) received
                    message +=  one_byte

                    #if received message is too long
                    if len(message) > max_num_of_received_chars:
                        raise OverflowError()

                else: #endchar received
                    return message

    def Send_Message_Sync(self, message: str, end_char = '*'):
        pass

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





ble = blueTooth("BLE Device 1")

scd30 = SCD30_Sensor()

dht = DHT_Temperature_Sensor(board.D5)

light_sensor = Light_Sensor(board.A2)

while True:
    try:
        print(light_sensor._Read_Resistance_Ohms())
    except Exception as ex:
        print("An exception occured: ", ex)

    time.sleep(2)
    