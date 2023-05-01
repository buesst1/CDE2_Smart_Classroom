from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import threading
import socket
import ssl
import os
from time import monotonic, sleep
import smtplib
import yaml
import requests

class Error(object):
    PhysicalConnectionerror = "physical_connection_error" #cannot communiacte with device
    ReadFailure = "read_failed" #cannot read measurement
    BleFailure = "BLE_error" #cannot connect to microcontroller over ble
    BatLowVoltage = "Battery_Low_Voltage" #battery is on a critical voltage level

class SSL:
    def __init__(self, host="0.0.0.0", port = 443) -> None:
        """
        Init ssl

        params:
        host: host ip
        port: port
        """
        
        self.HOST = host
        self.PORT = port

        self.__dirname = os.path.dirname(__file__)

        self.__input_jsons = [] #all jsons received stored here

        #start listener thread
        self.__listener_thread = threading.Thread(target=self.__listener, daemon=True)
        self.__listener_thread.start()    

    def __listener(self):
        """
        Start listener
        """
        
        while True:
            try:
                #create ssl socket and start listening
                context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
                context.load_cert_chain(self.__dirname + r'/SSL/certificate.crt', self.__dirname + r'/SSL/certificate.key') #load certificate

                bindsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
                bindsocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                bindsocket.bind((self.HOST, self.PORT))
                bindsocket.listen(5)

                while True:
                    try:
                        print("listening")
                        newsocket, fromaddr = bindsocket.accept() #wait for incoming connection
                        print("accepted")
                        connstream = context.wrap_socket(newsocket, server_side=True) # <- stuck here
                        print("socket wrapped")
                        connstream.settimeout(5) #set read/write timeout to 5 seconds
                        print("timeout set")
                        newsocket.close() #close original socket
                        print("accepted socket closed")
                        
                        print("start client handling")
                        self.__handle_client(connstream)
                        print("Client handled")

                    except Exception as ex:
                        #close eventual open newsocket
                        try:
                            newsocket.close()
                        except:
                            pass

                        print(f"Exception occured during accepting and handling client: {ex}")

                    finally:

                        #close connection
                        try:
                            connstream.shutdown(socket.SHUT_RDWR)
                        except Exception as ex:
                            print(f"Exception occured in shutdown connection: {ex}")

                        try:
                            connstream.close()
                        except Exception as ex:
                            print(f"Exception occured in close connection: {ex}")

                        print("connection closed")
                    

            except Exception as ex:

                #close eventually open bindsocket
                try:
                    bindsocket.close()
                except:
                    pass

                print(f"Critical error in listener thread: {ex}")

    def __read_from_conn(self, conn:ssl.SSLSocket) -> str:
        """
        read message from connection
        returns: received string 
        
        this method can raise an error

        returns:
        answer as string
        """

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
                    return message

                else: #otherwise add char to message
                    message += chr

    def __handle_client(self, conn:ssl.SSLSocket):
        """
        Handle a connected client (master)
        """
        
        try:
            answer = "" #message stored here

            try:
                answer = self.__read_from_conn(conn) #read message from master

            except Exception as ex:
                print(f"Error occured during reading data from master: {ex}")

                conn.sendall(str.encode("failed\n"))

                return
            
            try:

                splitted_msg = answer.split("~") #split message
                
            except:
                conn.sendall(str.encode("failed\n"))
                
                return

            #check data structure
            if splitted_msg[0] == "data":

                #process received data successful
                if self.__handle__jsons(splitted_msg[1]):
                    conn.sendall(str.encode("confirmed\n")) #return a positive confirmation to master

                else: #processing failed
                    conn.sendall(str.encode("failed\n")) #return a negative confirmation to master

            else: #wrong structure
                conn.sendall(str.encode("failed\n")) #return a negative confirmation to master
                raise Exception("unknown command received: {answer}")

        except Exception as ex:
            print(f"Exception occured during handling client: {ex}")

    def __handle__jsons(self, stringified_jsons:str) -> bool:
        """
        This method processes and stores the received measurements
        """
        
        try:
            all_jsons = stringified_jsons.split(";") #separate all received measurements (jsons)

            #decode json from strings
            json_files = []
            for str_json in all_jsons:
                json_files.append(json.loads(str_json)) 

            return self.__store_jsons(json_files) #store jsons in list

        except Exception as ex:
            print(f"Exeption occured during handling jsons: {ex}")
            return False

    def __store_jsons(self, jsons_list:list) -> bool:
        """
        This method extends all mesurements to list
        """
        
        try:
            self.__input_jsons.extend(jsons_list)
            return True

        except Exception as ex:
            print(f"Execption occured during saving jsons: {ex}")
            return False

    def Get_jsonBuffer(self):
        """
        This method gets all received measurements and deletes them afterwards
        """

        return [self.__input_jsons.pop(0) for item in list(self.__input_jsons)] #get all items from list and remove them at the same time

class Database:
    def __init__(self, userName='SENSOR_DATALAKE2', password='smarTclassrooM2Da') -> None:
        """
        Init database class
        """
        
        self.__userName = userName
        self.__password = password

    def __post(self, 
        timeStamp:datetime, 
        device1humidity:float=None, device1co2:float=None, device1temp:float=None, device1light:float=None, device1battery:float=None,
        device2humidity:float=None, device2co2:float=None, device2temp:float=None, device2light:float=None, device2battery:float=None,
        device3humidity:float=None, device3co2:float=None, device3temp:float=None, device3light:float=None, device3battery:float=None,
        device3window1a:bool=None, device3window2b:bool=None, device3window3a:bool=None, device3window4b:bool=None, device3window5a:bool=None,
    )-> bool:
        """
        This method send data to server backend 
        
        returns:
        successful -> true
        successful -> false
        """
    
        def convert_nullable_float(value): #converts nullable float to string
            if value == None:
                return None

            return str(value)

        def convert_nullable_bool(value): #converts nullable bool to string
            if value == None:
                return None

            if (value == True):
                return 1

            elif(value == False):
                return 0

        data_dict = {
            "inserttime": timeStamp.strftime("%d-%b-%Y %I:%M:%S %p"),
            "device1humidity": convert_nullable_float(device1humidity),
            "device1co2": convert_nullable_float(device1co2),
            "device1temp": convert_nullable_float(device1temp),
            "device2humidity": convert_nullable_float(device2humidity),
            "device2co2": convert_nullable_float(device2co2),
            "device2temp": convert_nullable_float(device2temp),
            "device3humidity": convert_nullable_float(device3humidity),
            "device3co2": convert_nullable_float(device3co2),
            "device3temp": convert_nullable_float(device3temp),
            "device3window1a": convert_nullable_bool(device3window1a),
            "device3window2b": convert_nullable_bool(device3window2b),
            "device3window3a": convert_nullable_bool(device3window3a),
            "device3window4b": convert_nullable_bool(device3window4b),
            "device3window5a": convert_nullable_bool(device3window5a),
            "device1light": convert_nullable_float(device1light),
            "device2light": convert_nullable_float(device2light),
            "device3light": convert_nullable_float(device3light),
            "device1battery": convert_nullable_float(device1battery),
            "device2battery": convert_nullable_float(device2battery),
            "device3battery": convert_nullable_float(device3battery),
        }

        r = requests.post('https://glusfqycvwrucp9-db202202211424.adb.eu-zurich-1.oraclecloudapps.com/ords/sensor_datalake2/sens/any_sensor_data_entry/',auth=(self.__userName, self.__password), data=json.loads(json.dumps(data_dict)))

        if r.ok:
            return True

        return False

    def Send_single_measurement(self, measurement:json):
        """
        This method tries to send a single measurement
        """

        try:
            inserttime = None
            device1humidity = None
            device1co2 = None
            device1temp = None
            device2humidity = None
            device2co2 = None
            device2temp = None
            device3humidity = None
            device3co2 = None
            device3temp = None
            device3window1a = None
            device3window2b = None
            device3window3a = None
            device3window4b = None
            device3window5a = None
            device1light = None
            device2light = None
            device3light = None
            device1battery = None
            device2battery = None
            device3battery = None

            measurement_json = json.loads(measurement)

            data:json = measurement_json["data"]

            inserttime = datetime.strptime(measurement_json["timeStamp"], "%d/%m/%Y %H:%M:%S") #get timestamp of measurement

            #iterate over device
            for deviceName in list(data.keys()):

                deviceData = data[deviceName]

                if deviceData != Error.BleFailure: #device has no ble error
                    
                    #iterate over sensor
                    for sensorName in list(deviceData.keys()):

                        sensorData = deviceData[sensorName]

                        if sensorData != Error.PhysicalConnectionerror: #sensor has no physical connection error
                            
                            #iterate over sensor measurements
                            for measurementName in list(sensorData.keys()):

                                measurementData = sensorData[measurementName]

                                if measurementData != Error.ReadFailure: #if no read failure occured

                                    #assign data to variable
                                    if deviceName == "Device1":
                                        if sensorName == "scd_30_sensor":
                                            if measurementName == "SCD_30_CO2":
                                                device1co2 = float(measurementData)

                                            elif measurementName == "SCD_30_HUM":
                                                device1humidity = float(measurementData)

                                            elif measurementName == "SCD_30_TEMP":
                                                device1temp = float(measurementData)

                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")

                                        elif sensorName == "light_sensor":
                                            if measurementName == "LS_lightStrength":
                                                device1light = float(measurementData)

                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")
                                            
                                        elif sensorName == "battery_voltage":
                                            if measurementName == "bat_voltage":
                                                device1battery = float(measurementData)
                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")
                                        else:
                                            print(f"Unknown sensorName name fom device: {deviceName} received: {sensorName}")

                                    elif deviceName == "Device2":
                                        if sensorName == "scd_30_sensor":
                                            if measurementName == "SCD_30_CO2":
                                                device2co2 = float(measurementData)

                                            elif measurementName == "SCD_30_HUM":
                                                device2humidity = float(measurementData)

                                            elif measurementName == "SCD_30_TEMP":
                                                device2temp = float(measurementData)

                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")

                                        elif sensorName == "light_sensor":
                                            if measurementName == "LS_lightStrength":
                                                device2light = float(measurementData)

                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")

                                        elif sensorName == "battery_voltage":
                                            if measurementName == "bat_voltage":
                                                device2battery = float(measurementData)
                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")    
                                        
                                        else:
                                            print(f"Unknown sensorName name fom device: {deviceName} received: {sensorName}")

                                    elif deviceName == "Device3":
                                        if sensorName == "scd_30_sensor":
                                            if measurementName == "SCD_30_CO2":
                                                device3co2 = float(measurementData)

                                            elif measurementName == "SCD_30_HUM":
                                                device3humidity = float(measurementData)

                                            elif measurementName == "SCD_30_TEMP":
                                                device3temp = float(measurementData)

                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")

                                        elif sensorName == "light_sensor":
                                            if measurementName == "LS_lightStrength":
                                                device3light = float(measurementData)

                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")

                                        elif sensorName == "magnetic_sensors":
                                            if measurementName == "MS_S1":
                                                device3window1a = bool(measurementData)

                                            elif measurementName == "MS_S2":
                                                device3window2b = bool(measurementData)

                                            elif measurementName == "MS_S3":
                                                device3window3a = bool(measurementData)

                                            elif measurementName == "MS_S4":
                                                device3window4b = bool(measurementData)

                                            elif measurementName == "MS_S5":
                                                device3window5a = bool(measurementData)

                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")
                                            
                                        elif sensorName == "battery_voltage":
                                            if measurementName == "bat_voltage":
                                                device3battery = float(measurementData)
                                            else:
                                                print(f"Unknown measurementName name fom device: {deviceName} form sensor: {sensorName} received: {measurementName}")

                                        else:
                                            print(f"Unknown sensorName name fom device: {deviceName} received: {sensorName}")

                                    else:
                                        print(f"Unknown device name received: {deviceName}")

            return self.__post(
                                inserttime, 
                                device1humidity, device1co2, device1temp, device1light, device1battery,
                                device2humidity, device2co2, device2temp, device2light, device2battery,
                                device3humidity, device3co2, device3temp, device3light, device3battery,
                                device3window1a, device3window2b, device3window3a, device3window4b, device3window5a
                            )

        except Exception as ex:
            print(f"Exception occured during sensing data to database: {ex}")
            return False

class Email:
    def __init__(self, userName:str, password:str, receipents:list) -> None:
        """
        Init email class
        """
        
        self.__password = password
        self.__userName = userName
        self.__receipents = receipents
        
    def Send_Email(self, target_emails:list, subject:str, message:str):
        """
        This method sens an email to some receipents

        params:
        target_emails: list of email addresses that will receive the mail
        subject: subject of email
        message: message of email
        """
        
        try:
            msg = MIMEMultipart()
            msg['From'] = self.__userName
            msg['To'] = ', '.join(target_emails)
            msg['Subject'] = subject
            msg.attach(MIMEText(message, 'plain'))

            #Create SMTP session for sending the mail
            session = smtplib.SMTP_SSL('smtp.gmail.com', 465)
            session.login(self.__userName, self.__password) #login with mail_id and password
            text = msg.as_string()
            session.sendmail(self.__userName, target_emails, text)
            session.quit()
            print('Mail Sent')

        except Exception as ex:
            print (f'Something went wrong sending an Email: {ex}')

    def Send_Status_email(self, traced_errors_list:list):
        """
        Sends a status email with containing error messages 
        """
        
        if len(traced_errors_list) > 0: #there are errors in list

            message = "Bei folgenden Messungen ist/sind folgende(r) Fehler aufgetreten:\n\n"

            for traced_errors in traced_errors_list:
                message += f"Zeitstempel: {traced_errors.pop('timestamp')}\n{yaml.dump(traced_errors)}\n\n"

            self.Send_Email(self.__receipents, "Statusmeldung: Smart Classroom Error/Warning Report", message)

        else: #no errors in list
            self.Send_Email(self.__receipents, "Statusmeldung: OK", "Es sind soweit keine Fehler aufgetreten")

    def Send_MasterTimeout_email(self):
        """
        This method sends an email containing the message of a master timeout
        """
        
        self.Send_Email(self.__receipents, "Statusmeldung: Master Info", "Vom Master wurde eine längere Zeit keine Daten mehr empfangen...")

    def Send_MasterReconnect_email(self):
        """
        This method sends an email containing the message of a master reconnect
        """
        
        self.Send_Email(self.__receipents, "Statusmeldung: Master Info", "Verbindung zum Master wurde wieder hergestellt")

class ErrorCheck:
    def __init__(self, bat_voltage_lowError_threshold:float = 3.5) -> None:
        """
        Init error check class
        """
        
        self.__bat_voltage_lowError_threshold = bat_voltage_lowError_threshold #battery voltage threshold 
        self.__error_traces = [] #errors that are collected are stored here

    def __get_error_trace_back(self, json_stringified:json):
        """
        This mehod searches for errors in a measurement and returns them as dictionary
        """
        
        device_errors = {}
        
        json_ = json.loads(json_stringified)

        time = datetime.strptime(json_["timeStamp"], "%d/%m/%Y %H:%M:%S")

        data:json = json_["data"]

        for deviceName in list(data.keys()):

            deviceData = data[deviceName]

            if deviceData != Error.BleFailure:

                for sensorName in list(deviceData.keys()):
                    sensorData = deviceData[sensorName]

                    if sensorData != Error.PhysicalConnectionerror:

                        for measurementName in list(sensorData.keys()):
                            measurementData = sensorData[measurementName]

                            if measurementData == Error.ReadFailure:
                                deviceName_ = device_errors.get(deviceName, {})
                                sensorName_ = deviceName_.get(sensorName, {})
                                sensorName_[measurementName] = Error.ReadFailure

                                deviceName_[sensorName] = sensorName_
                                device_errors[deviceName] = deviceName_
                                device_errors["timestamp"] = time

                            elif measurementName == "bat_voltage":
                                if float(measurementData) <= self.__bat_voltage_lowError_threshold:
                                    deviceName_ = device_errors.get(deviceName, {})
                                    sensorName_ = deviceName_.get(sensorName, {})
                                    sensorName_[measurementName] = f"{Error.BatLowVoltage} only {float(measurementData)}V"

                                    deviceName_[sensorName] = sensorName_
                                    device_errors[deviceName] = deviceName_
                                    device_errors["timestamp"] = time

                    else:
                        deviceName_ = device_errors.get(deviceName, {})
                        deviceName_[sensorName] = Error.PhysicalConnectionerror

                        device_errors[deviceName] = deviceName_
                        device_errors["timestamp"] = time

            else:
                device_errors[deviceName] = Error.BleFailure
                device_errors["timestamp"] = time

        return device_errors

    def CheckJsons_StoreErrors(self, jsons:list):
        """
        This method checks all measurements in json format for errors
        """
        
        #check all measurements for errors and store errors in list
        for json_ in jsons:
            error_trace_dict = self.__get_error_trace_back(json_)

            if len(list(error_trace_dict.keys())) > 0:
                self.__error_traces.append(error_trace_dict)

    def GetErrors(self):
        """
        This method gets all errors collected during last error fetch
        """

        #get errors and delete list
        error_traces_copy = self.__error_traces.copy()
        self.__error_traces.clear(); #clear all

        return error_traces_copy

if __name__ == '__main__':    
    #instances
    server = SSL()
    checkError = ErrorCheck()
    db = Database()
    
    #read username and password of gmail account
    with open(os.path.dirname(__file__) + "/creditals", "r") as fd:
        creditals = fd.read().split("\n")
    email = Email(creditals[0], creditals[1], ["tobias.buess2001@gmail.com", "pjluca48@gmail.com", "yannic.lais@students.fhnw.ch"]) #email of receipents

    #constants
    status_mail_intervall_min = 60 #sends a status email in a specific intervall
    master_timeout_min = 10 #triggers an email with a masterTimeout message

    #variables
    time_last_jsons_received = monotonic()
    master_timeout_recognized = False
    measurements_database_failed = [] #failed measurements stored here
    
    print("Start mainLoop")
    old_status_mail_time = monotonic()
    while True:
        try:
            #if measurements failed to send to database
            if len(measurements_database_failed) > 0:
                measurement = measurements_database_failed.pop()

                print(f"{len(measurements_database_failed)} jsons buffered and not stored in database")

                #try update database (otherwise store again)
                if not db.Send_single_measurement(measurement):
                    measurements_database_failed.append(measurement)
                
            jsons = server.Get_jsonBuffer() #get jsons received from master

            #as soon as jsons received
            if(len(jsons) > 0):
                time_last_jsons_received = monotonic() #update time

                print(jsons)

                #master timeout triggered
                if master_timeout_recognized:
                    master_timeout_recognized = False #reset flag
                    email.Send_MasterReconnect_email()
                
                #try store measurements in database
                for measurement in jsons:
                    #try update database (otherwise store again)
                    if not db.Send_single_measurement(measurement):
                        measurements_database_failed.append(measurement)

                checkError.CheckJsons_StoreErrors(jsons) #check for errors and store it when error occured

            #as soon as intervall reached
            if monotonic() >= old_status_mail_time + (status_mail_intervall_min * 60):
                old_status_mail_time = monotonic()

                email.Send_Status_email(checkError.GetErrors())

            #if master timeout occures
            if (monotonic() >= time_last_jsons_received + (master_timeout_min * 60)) and not master_timeout_recognized:
                master_timeout_recognized = True #set flag
                email.Send_MasterTimeout_email()

            sleep(1)

        except Exception as ex:
            print(f"Exception occured in mainLoop: {ex}")

    



