#Firmware updated: https://learn.adafruit.com/introducing-the-adafruit-nrf52840-feather/circuitpython
#load firmare on Feather:
-> delete everything from Feather -> drag and drop: lib, boot.py, code.py, config -> adjust config file parameters to your needs (see below)

#config file configuration:
Device1: CO2_Sensor,Light_Sensor
Device2: CO2_Sensor,Light_Sensor
Device3: CO2_Sensor,Light_Sensor,Magnetic_Sensors


#Magnetic Sensors: 
    -S1 (Window1A): Pin5
    -S2 (Window2B): Pin6
    -S3 (Window3A): Pin9
    -S4 (Window4B): Pin10
    -S5 (Window5A): Pin11

->result = True: No electrical connection between Sx and GND
->result = False: Electrical connection between Sx and GND
