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
from microcontroller import watchdog
from watchdog import WatchDogMode

def Write_To_Log_File(clssName:str, text:str):
    """
    Write text to log file 
    format: 'monotonic time': 'className': 'text'
    """
    
    timestamp = monotonic()
    with open("/log.txt", "a+") as fd:
        fd.write(str(timestamp) + ": " + clssName + ": " + text + "\n")
        fd.flush()

class blueTooth:
    def __init__(self, deviceName: str, start_read_timeout_s=10.0):
        """
        Initialize bluetooth interface

        parameters:
        deviceName: name inside advertizement
        start_read_timeout_s: uart timeout
        """
        
        Write_To_Log_File("blueTooth", "init started")
        self.__ble = BLERadio()
        self.__ble.name = deviceName

        self.__uart = UARTService()
        self.__uart.timeout = start_read_timeout_s

        self.__advertisement = ProvideServicesAdvertisement(self.__uart)
        Write_To_Log_File("blueTooth", "init ble finished")

    def Advertise_Until_Connected_Sync(self):
        """
        This method advertizes and waits until a device connected to feather
        """

        #as long as not connected
        Write_To_Log_File("blueTooth", "advertizing started")
        while not self.__ble.connected:
            #try start advertizing
            try:
                self.__ble.start_advertising(self.__advertisement) 
            except:
                pass

            sleep(1) #sleep a second 

        self.__ble.stop_advertising() #stop advertising
        Write_To_Log_File("blueTooth", "advertizing stopped")

    def Is_Connected(self):
        return self.__ble.connected

    def Read_Message_Sync(self, timeout_s = 4.0) -> str:
        """
        This method reads incoming data

        params:
        timeout_ms (int) -> reading has to finish within timeout_ms
        """

        Write_To_Log_File("blueTooth", "message reading started")

        if not self.__ble.connected:
            raise Exception("not connected to a device")

        monotonic_time_s = monotonic()

        #wait until bytes arrived
        while self.__uart.in_waiting < 1:
            if not self.__ble.connected:
                raise Exception("connection lost")

            elif (monotonic() - monotonic_time_s) > timeout_s: #if looping for too long
                raise Exception("Timeout occured")

        bytes_ = self.__uart.readline()  #read a byte -> returns b'' if nothing was read.

        if bytes_ == None:
            raise Exception("Connection failed")

        message = str(bytes_.decode("utf-8"))
        message = message.rstrip("\n")
        message = message.rstrip("\r")

        Write_To_Log_File("blueTooth", "message successfully read")

        return message 
            
    def Write_Message_Sync(self, message: str):
        """
        This method writes message to master

        params:
        message: string that will be sent to master
        """
        
        Write_To_Log_File("blueTooth", "start writing message")

        msg = message + "\n" #add delimiter

        #write message to master with a delay of 100ns (this delay prevents master from bluetooth buffer overload)
        for msg_snippets in msg:
            buffer = str.encode(msg_snippets, "utf-8")

            self.__uart.write(buffer)
            sleep(0.0001)

        Write_To_Log_File("blueTooth", "successfully written message")
            
class SCD30_Sensor:
    def __init__(self, i2c_address = 0x61):
        """
        Initializes SCD30_Sensor (co2, temperature, humidity)
        """
        
        Write_To_Log_File("SCD30_Sensor", "init started")

        self.__i2c = busio.I2C(board.SCL, board.SDA, frequency=1000)  # for FT232H, use 1KHz
        self.__scd = adafruit_scd30.SCD30(self.__i2c, address=i2c_address)
        self.__scd.measurement_interval = 25 #set measurement intervall to 25s

        #buffer variables for measurements
        self.__temp_celcius = None
        self.__relHum_percent = None
        self.__co2_ppm = None

        Write_To_Log_File("SCD30_Sensor", "init finished")

    def __readSensors(self):
        """
        This method read values from senor
        """
        
        Write_To_Log_File("SCD30_Sensor", "reading measurements started")

        #read if new values available on sensor
        if self.__scd.data_available:
            self.__temp_celcius = float(self.__scd.temperature)
            self.__relHum_percent = float(self.__scd.relative_humidity)
            self.__co2_ppm = float(self.__scd.CO2)

        Write_To_Log_File("SCD30_Sensor", "reading measurements successfully finished")

    def Read_CO2_PPM(self) -> float:
        """
        Read CO2 in parts per million
        """
        
        Write_To_Log_File("SCD30_Sensor", "read_co2 sensor started")
        self.__readSensors()

        if self.__co2_ppm == None:
            raise Exception("SCD30_Sensor: CO2: No data available")

        Write_To_Log_File("SCD30_Sensor", "read_co2 sensor successfully finished")

        return self.__co2_ppm

    def Read_Rel_Hum_Percent(self) -> float:
        """
        Read relative humidity in %
        """

        Write_To_Log_File("SCD30_Sensor", "read_humidity started")

        self.__readSensors()

        if self.__relHum_percent == None:
            raise Exception("SCD30_Sensor: Humidity: No data available")

        Write_To_Log_File("SCD30_Sensor", "read_humidity successfully finished")

        return self.__relHum_percent
    
    def Read_Temp_Celcius(self) -> float:
        """
        Read air temperature in °C
        """
        
        Write_To_Log_File("SCD30_Sensor", "read_temp started")

        self.__readSensors()

        if self.__temp_celcius == None:
            raise Exception("SCD30_Sensor: Temperature: No data available")

        Write_To_Log_File("SCD30_Sensor", "read_temp successfully finished")

        return self.__temp_celcius

class Light_Sensor:
    def __init__(self, pin=board.A2):
        """
        Initializes light sensor

        params:
        pin: board pin (analog in) where sensor is connected
        """

        Write_To_Log_File("Light_Sensor", "init started")

        self.__analogRead = AnalogIn(pin)

        self.__m = 100 / 0.0002395 #according to datasheet: typ 239.5 uA at 100lux
        self.__q = 0 #according to datasheet: 0lux -> max 10nA

        Write_To_Log_File("Light_Sensor", "init successfully finished")

    def __Read_Current_Ampere(self, R1_res_ohms=68000):
        """
        Calculate current that is flowing trough sensor
        """
        
        Write_To_Log_File("Light_Sensor", "readcurrent started")

        ref_voltage = self.__analogRead.reference_voltage #3.3V
        voltage_R1 = (ref_voltage / 65536) * self.__analogRead.value #calculate voltage on pin

        current_R1 = voltage_R1 / R1_res_ohms #calculate current through sensor (voltage over R1 / R1 (68kOhm))

        Write_To_Log_File("Light_Sensor", "readcurrent successfully finished")

        return current_R1

    def Get_Light_Strength_Lux(self):
        """
        Get light strength in lux
        """
        
        try:
            Write_To_Log_File("Light_Sensor", "get_light_strength started")

            current_A = self.__Read_Current_Ampere()

            Write_To_Log_File("Light_Sensor", "get_light_strength successfully finisehd")
        
            return self.__m * current_A + self.__q

        except Exception as ex:
            print(ex)
        
class Battery_Voltage:
    def __init__(self, pin: board = board.BATTERY, voltage_divider_ratio = 0.5):
        """
        Initialize battery voltage reader

        params:
        pin: pin (analog in) where battery is connected to
        voltage_divider_ratio: devicer ratio of voltage devicer -> 0.5 = R1 equals R2
        """
        
        Write_To_Log_File("Battery_Voltage", "init started")

        self.__analogRead = AnalogIn(pin)
        self.__divider_ratio = voltage_divider_ratio
        self.__ref_voltage = self.__analogRead.reference_voltage

        Write_To_Log_File("Battery_Voltage", "init stopped")

    def Read_Voltage(self):
        Write_To_Log_File("Battery_Voltage", "try execute a read_voltage")

        return ((self.__ref_voltage / 65536) * self.__analogRead.value) / self.__divider_ratio #calculate voltage on battery

class Magnetic_Sensors:
    def __init__(self, pinS1=board.D5, pinS2=board.D6, pinS3=board.D9, pinS4=board.D10, pinS5=board.D11) -> None:
        """
        Initialize reader for magnetic sensors

        params:
        pinS1-S5: pins where sensors are connected to
        """

        Write_To_Log_File("Magnetic_Sensors", "init started")

        #enable pull up -> sensors need to connect to ground when closed

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

        Write_To_Log_File("Magnetic_Sensors", "init stopped")

    def Read_Sensors(self) -> tuple:
        """
        This methods reads all Sensors and returns a tuple of the sensor states [0] = state of sensor1 -> True (Logical 1 on pin)
        """

        Write_To_Log_File("Magnetic_Sensors", "try execute a read_sensors")
        
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
    test = "abc"
    
    def __init__(self, sensors: list, deviceName: str):
        """
        parameter:
        sensors (list of Sensors to activate -> see readme.md)
        """

        Write_To_Log_File("Manager", "init started")

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

        Write_To_Log_File("Manager", "init finished")

    def __Init_Sensors(self):
        """
        This method creates an instance of all enabled sensors
        """
        
        Write_To_Log_File("Manager", "init_sensors started")

        #create instance if sensor is in self.__sensors
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

        Write_To_Log_File("Manager", "init_sensors successfully finished")

    def Wait_For_Connection_sync(self):
        """
        This function waits for a bluetooth connection to the master
        """
        
        self.__ble.Advertise_Until_Connected_Sync()
        
    def Read_Message_From_BLE(self):
        """
        This method reads message from an active bluetooth connection to master
        """
        
        return self.__ble.Read_Message_Sync()

    def Write_Message_To_BLE(self, message: str):
        """
        This method sends a message to an active bluetooth connection to master

        params:
        message: messate to send
        """

        self.__ble.Write_Message_Sync(message)

    def Read_Measures(self) -> dict:
        """
        This starts a read on all activated sensors
        """
        
        sensors = {}

        Write_To_Log_File("Manager", "read_measures started")


        #following code will check firstly if sensor is activated
        #secondly it will be checked if an error encountered during initialization (PhysicalConnectionerror)
        #last thing that will be ckecked is the result of the measurement (ReadFailure) if no error encountered so far, the value will be written to dictionary

        #if sensor active
        if self.__scd_30_sensor != None:
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

                sensors["scd_30_sensor"] = measurements

            else:
                sensors["scd_30_sensor"]  = Error.PhysicalConnectionerror

        #if sensor active
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
        
        #if sensor active
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

        #if sensor active
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

        Write_To_Log_File("Manager", "read_measures successfully stopped")

        return sensors


#read deviceName and sensors to activate
Write_To_Log_File("Main", "init started")

#read config in folder and read deviceName (parameter in blueTooth class) and all sensors that should be activated
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

#init watchdog and set to a threshold value of 120s
w = watchdog
w.timeout = 120
w.mode = WatchDogMode.RESET

Write_To_Log_File("Main", "init successfully finished")

while True:
    try:
        w.feed() #reset watchdog timer

        print("Wait for a connection")
        Write_To_Log_File("Main", "waiting for a connection")

        #wait for a ble connection from master
        manager.Wait_For_Connection_sync() 

        Write_To_Log_File("Main", "connected to master")
        print("Connected")

        Write_To_Log_File("Main", "read_message_from_ble started")
        message = manager.Read_Message_From_BLE() #read command from master
        Write_To_Log_File("Main", "read_message_from_ble successfully stopped")

        #switch case master command
        if message == "measure_request":

            Write_To_Log_File("Main", "measure_request command successfully recognized")

            Write_To_Log_File("Main", "try read measures and convert to json started")
            stringified_json = json.dumps(manager.Read_Measures()) #read measurements and convert to a json format
            Write_To_Log_File("Main", "try read measures and convert to json successfully stopped")

            print("Message:\n", stringified_json)

            Write_To_Log_File("Main", "start writing message to master")
            manager.Write_Message_To_BLE(stringified_json) #write measurements to master
            Write_To_Log_File("Main", "writing message to master successfully stopped")

        else:
            raise Exception("Unknown command received")
        
        #go to light sleep
        Write_To_Log_File("Main", "start with light sleep")
        time_alarm = alarm.time.TimeAlarm(monotonic_time=monotonic() + 20)
        alarm.light_sleep_until_alarms(time_alarm)
        Write_To_Log_File("Main", "wakeup from light sleep")

    except Exception as ex:
        Write_To_Log_File("Main", f"exception occured in mainloop: {ex}")
        print(f"Exception occuren in main loop: {ex}") 

    
    