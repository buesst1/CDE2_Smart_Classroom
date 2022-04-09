import math
from time import monotonic, sleep
from adafruit_ble import BLERadio
from adafruit_ble.advertising.standard import ProvideServicesAdvertisement
from adafruit_ble.services.nordic import UARTService
from analogio import AnalogIn
from digitalio import DigitalInOut
from digitalio import Direction
from digitalio import Pull
import adafruit_dht
import adafruit_scd30
import board
import busio 
import json
import alarm


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

    def Is_Connected(self):
        return self.__ble.connected

    def Read_Message_Sync(self, timeout_s = 4) -> str:
        """
        This method reads incoming data

        params:
        timeout_ms (int) -> reading has to finish within timeout_ms
        end_char (char) -> end character
        max_num_of_received_chars (int) -> max number of characters to be reiceved to avoid an overflow of ram
        """

        if not self.__ble.connected:
            raise Exception("not connected to a device")

        monotonic_time_s = monotonic()

        #wait until bytes arrived
        while self.__uart.in_waiting < 1:
            if not self.__ble.connected:
                raise Exception("connection lost")

            elif (monotonic() - monotonic_time_s) > timeout_s:
                raise Exception("Timeout occured")

        bytes_ = self.__uart.readline()  #read a byte -> returns b'' if nothing was read.

        if bytes_ == None:
            raise Exception("Connection failed")

        message = str(bytes_.decode("utf-8"))
        message = message.rstrip("\n")
        message = message.rstrip("\r")

        return message 
            
    def Write_Message_Sync(self, message: str):
        msg = message + "\n"
        for msg_snippets in msg:
            buffer = str.encode(msg_snippets, "utf-8")

            self.__uart.write(buffer)
            sleep(0.0001)
            
class SCD30_Sensor:
    def __init__(self, i2c_address = 0x61):
        self.__i2c = busio.I2C(board.SCL, board.SDA, frequency=1000)  # for FT232H, use 1KHz
        self.__scd = adafruit_scd30.SCD30(self.__i2c, address=i2c_address)
        self.__scd.measurement_interval = 25 #set measurement intervall to 25s

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

class Light_Sensor:
    def __init__(self, pin=board.A2):
        """
        m,q calculated with diagram from SEN-09088.pdf
        """

        self.__analogRead = AnalogIn(pin)

        self.__m = 100 / 0.0002395 #according to datasheet: typ 239.5 uA at 100lux
        self.__q = 0 #according to datasheet: 0lux -> max 10nA

    def __Read_Current_Ampere(self, R1_res_ohms=68000):
        ref_voltage = self.__analogRead.reference_voltage
        voltage_R1 = (ref_voltage / 65536) * self.__analogRead.value #calculate voltage on pin

        current_R1 = voltage_R1 / R1_res_ohms #calculate current through sensor (voltage over R1 / R1 (68kOhm))

        return current_R1

    def Get_Light_Strength_Lux(self):
        try:
            current_A = self.__Read_Current_Ampere()
        
            return self.__m * current_A + self.__q

        except Exception as ex:
            print(ex)
        
class Battery_Voltage:
    def __init__(self, pin: board = board.A0, voltage_divider_ratio = 0.5):
        self.__analogRead = AnalogIn(pin)
        self.__divider_ratio = voltage_divider_ratio
        self.__ref_voltage = self.__analogRead.reference_voltage

    def Read_Voltage(self):
        return ((self.__ref_voltage / 65536) * self.__analogRead.value) / self.__divider_ratio #calculate voltage on battery

class Magnetic_Sensors:
    def __init__(self, pinS1=board.D5, pinS2=board.D6, pinS3=board.D9, pinS4=board.D10, pinS5=board.D11) -> None:
        self.__sensor1 = DigitalInOut(pinS1)
        self.__sensor1.direction = Direction.INPUT
        self.__sensor1.pull = Pull.UP

        self.__sensor2 = DigitalInOut(pinS2)
        self.__sensor2.direction = Direction.INPUT
        self.__sensor2.pull = Pull.UP

        self.__sensor3 = DigitalInOut(pinS3)
        self.__sensor3.direction = Direction.INPUT
        self.__sensor3.pull = Pull.UP

        self.__sensor4 = DigitalInOut(pinS4)
        self.__sensor4.direction = Direction.INPUT
        self.__sensor4.pull = Pull.UP

        self.__sensor5 = DigitalInOut(pinS5)
        self.__sensor5.direction = Direction.INPUT
        self.__sensor5.pull = Pull.UP

    def Read_Sensors(self) -> tuple:
        """
        This methods reads all Sensors and returns a tuple of the sensor states [0] = state of sensor1 -> True (Logical 1 on pin)
        """
        
        return (self.__sensor1.value, self.__sensor2.value, self.__sensor3.value, self.__sensor4.value, self.__sensor5.value)

class Sensors(object):
    BatteryVoltage = "Battery_Voltage"
    SCD30_Sensor = "CO2_Sensor"
    MagneticSensors = "Magnetic_Sensors"
    LightSensor = "Light_Sensor"

class Error(object):
    PhysicalConnectionerror = "physical_connection_error" #cannot communiacte with device
    ReadFailure = "read_failed" #cannot read measurement

class Manager:
    def __init__(self, sensors: list, deviceName: str):
        """
        parameter:
        sensors (list of Sensors to activate)
        """

        self.__sensors = sensors
        self.__sensors.append(Sensors.BatteryVoltage)#append BatteryVoltage as default

        self.__deviceName = deviceName
        self.__ble = blueTooth(self.__deviceName)

        #init sensor classes
        self.__scd_30_sensor = None
        self.__magnetic_sensor = None
        self.__light_sensor = None
        self.__battery_voltage = None

        self.__Init_Sensors()

    def __Init_Sensors(self):
        if Sensors.SCD30_Sensor in self.__sensors:
            try:
                self.__scd_30_sensor = SCD30_Sensor()
            except:
                self.__scd_30_sensor = Error.PhysicalConnectionerror

        if Sensors.MagneticSensors in self.__sensors:
            try:
                self.__magnetic_sensor = Magnetic_Sensors() 
            except Exception as ex:
                self.__magnetic_sensor = Error.PhysicalConnectionerror

        if Sensors.LightSensor in self.__sensors:
            try:
                self.__light_sensor = Light_Sensor() 
            except:
                self.__light_sensor = Error.PhysicalConnectionerror

        if Sensors.BatteryVoltage in self.__sensors:
            try:
                self.__battery_voltage = Battery_Voltage() 
            except:
                self.__battery_voltage = Error.PhysicalConnectionerror

    def Wait_For_Connection_sync(self):
        """
        This function waits for a bluetooth connection 
        """
        
        self.__ble.Advertise_Until_Connected_Sync()
        
    def Read_Message_From_BLE(self):
        return self.__ble.Read_Message_Sync()

    def Write_Message_To_BLE(self, message: str):
        self.__ble.Write_Message_Sync(message)

    def Read_Measures(self) -> dict:
        sensors = {}

        #if sensor active
        if self.__scd_30_sensor != None:
            if self.__scd_30_sensor != Error.PhysicalConnectionerror: 
                measurements = {}

                try:
                    measurements["SCD_30_CO2"] = self.__scd_30_sensor.Read_CO2_PPM()
                    #raise Exception("test")
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

                sensors["scd_30_sensor"] = measurements

            else:
                sensors["scd_30_sensor"]  = Error.PhysicalConnectionerror

        if self.__magnetic_sensor != None:
            if self.__magnetic_sensor != Error.PhysicalConnectionerror: 
                measurements = {}

                try:
                    result = self.__magnetic_sensor.Read_Sensors()

                    measurements["MS_S1"] = result[0]
                    measurements["MS_S2"] = result[1]
                    measurements["MS_S3"] = result[2]
                    measurements["MS_S4"] = result[3]
                    measurements["MS_S5"] = result[4]

                except:
                    measurements["MS_S1"] = Error.ReadFailure
                    measurements["MS_S2"] = Error.ReadFailure
                    measurements["MS_S3"] = Error.ReadFailure
                    measurements["MS_S4"] = Error.ReadFailure
                    measurements["MS_S5"] = Error.ReadFailure

                sensors["magnetic_sensors"] = measurements

            else:
                sensors["magnetic_sensors"] = Error.PhysicalConnectionerror

        if self.__light_sensor != None:
            if self.__light_sensor != Error.PhysicalConnectionerror: 
                measurements = {}

                try:
                    result = self.__light_sensor.Get_Light_Strength_Lux()

                    measurements["LS_lightStrength"] = result

                except:
                    measurements["LS_lightStrength"] = Error.ReadFailure


                sensors["light_sensor"] = measurements

            else:
                sensors["light_sensor"] = Error.PhysicalConnectionerror

        if self.__battery_voltage != None:
            if self.__battery_voltage != Error.PhysicalConnectionerror: 
                measurements = {}

                try:
                    result = self.__battery_voltage.Read_Voltage()

                    if result is None:
                        raise Exception("Battery_Voltage failed to read")

                    measurements["bat_voltage"] = result
                except:
                    measurements["bat_voltage"] = Error.ReadFailure

                sensors["battery_voltage"] = measurements

            else:
                sensors["battery_voltage"] = Error.PhysicalConnectionerror

        return sensors


#read deviceName and sensors to activate
with open("config", "r") as fd:
    lines = fd.readlines()

deviceName = lines[0].strip("\r\n")
sensors = []

for sens_str in lines[1].split(","):
    sensors.append(sens_str.strip("\r\n"))

for sensor in sensors:
    if sensor == Sensors.LightSensor:
        continue

    elif sensor == Sensors.MagneticSensors:
        continue

    elif sensor == Sensors.SCD30_Sensor:
        continue

    raise Exception("Unknown sensor in config file")

manager = Manager(sensors, deviceName)

while True:
    try:
        print("Wait for a connection")
        #wait for a ble connection
        manager.Wait_For_Connection_sync() 
    
        print("Connected")

        message = manager.Read_Message_From_BLE()

        if message == "measure_request":

            stringified_json = json.dumps(manager.Read_Measures())

            print("Message:\n", stringified_json)

            manager.Write_Message_To_BLE(stringified_json)

        else:
            raise Exception("Unknown command received")
        
        #go in light sleep
        time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + 20)
        alarm.light_sleep_until_alarms(time_alarm)

    except Exception as ex:
        print(f"Exception occuren in main loop: {ex}") 

    
    