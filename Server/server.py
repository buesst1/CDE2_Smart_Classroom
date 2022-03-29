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
        self.HOST = host
        self.PORT = port

        self.__dirname = os.path.dirname(__file__)

        self.__input_jsons = []

        #start listener thread
        self.__listener_thread = threading.Thread(target=self.__listener, daemon=True)
        self.__listener_thread.start()  

    def __listener(self):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(self.__dirname + r'\\SSL\\certificate.crt', self.__dirname + r'\\SSL\\certificate.key')

            bindsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0)
            bindsocket.bind((self.HOST, self.PORT))
            bindsocket.listen(5)

            while True:
                print("listening")
                newsocket, fromaddr = bindsocket.accept()
                print("accepted")

                connstream = context.wrap_socket(newsocket, server_side=True)

                try:
                    self.__handle_client(connstream)

                except Exception as ex:
                    print(f"Exception occured during accepting client: {ex}")

                finally:
                    connstream.shutdown(socket.SHUT_RDWR)
                    connstream.close()

                    print("connection closed")
                        

        except Exception as ex:
            print(f"Critical error in listener thread (exit thread): {ex}")

    def __handle_client(self, conn:ssl.SSLSocket):
        try:
            message = "" #message stored here

            #wait until bytes arrived
            data = None
            while not data:
                data = conn.recv(buflen=1)

            while data:
                if data != b"\n":
                    message += bytes.decode(data) 
                else:
                    break

                data = conn.recv(1)

            splitted_msg = message.split("~")

            if len(splitted_msg) != 2:
                conn.sendall(str.encode("failed\n"))

                raise Exception("message has incorrect length")

            if splitted_msg[0] == "data":
                if self.__handle__jsons(splitted_msg[1]):
                    conn.sendall(str.encode("confirmed\n"))

                else:
                    conn.sendall(str.encode("failed\n"))

            else:
                conn.sendall(str.encode("failed\n"))
                raise Exception("unknown command received")

        except Exception as ex:
            print(f"Exception occured during handling client: {ex}")

    def __handle__jsons(self, stringified_jsons:str) -> bool:
        try:
            all_jsons = stringified_jsons.split(";")

            #decode json from strings
            json_files = []
            for str_json in all_jsons:
                json_files.append(json.loads(str_json)) 

            return self.__store_jsons(json_files)

        except Exception as ex:
            print(f"Exeption occured during handling jsons: {ex}")
            return False

    def __store_jsons(self, jsons_list:list) -> bool:
        try:
            self.__input_jsons.extend(jsons_list)
            return True

        except Exception as ex:
            print(f"Execption occured during saving jsons: {ex}")
            return False

    def Get_jsonBuffer(self):
        jsons = self.__input_jsons.copy()

        self.__input_jsons.clear()

        return jsons

class Database:
    def __init__(self) -> None:
        pass

class Email:
    def __init__(self, userName:str, password:str, receipents:list) -> None:
        self.__password = password
        self.__userName = userName
        self.__receipents = receipents
        
    def Send_Email(self, target_emails:list, subject:str, message:str):
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
        
        #error in traced_errors
        if len(traced_errors_list) > 0:

            message = "Bei folgenden Messungen ist/sind folgende(r) Fehler aufgetreten:\n\n"

            for traced_errors in traced_errors_list:
                message += f"Zeitstempel: {traced_errors.pop('timestamp')}\n{yaml.dump(traced_errors)}\n\n"

            self.Send_Email(self.__receipents, "Statusmeldung: Smart Classroom Error/Warning Report", message)

        else:
            self.Send_Email(self.__receipents, "Statusmeldung: OK", "Es sind soweit keine Fehler aufgetreten")

    def Send_MasterTimeout_email(self):
        """
        This method sends an email containing the message of a master timeout
        """
        
        self.Send_Email(self.__receipents, "Statusmeldung: Master Timeout", "Vom Master wurde eine längere Zeit keine Daten mehr empfangen...")

class ErrorCheck:
    def __init__(self, bat_voltage_lowError_threshold:float = 3.5) -> None:
        self.__bat_voltage_lowError_threshold = bat_voltage_lowError_threshold #battery voltage threshold 
        self.__error_traces = [] #errors that are collected are stored here

    def __get_error_trace_back(self, json_stringified:json):
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
        
        for json_ in jsons:
            error_trace_dict = self.__get_error_trace_back(json_)

            if len(list(error_trace_dict.keys())) > 0:
                self.__error_traces.append(error_trace_dict)

    def GetErrors(self):
        """
        This method gets all errors collected during last error fetch
        """

        error_traces_copy = self.__error_traces.copy()
        self.__error_traces.clear(); #clear all

        return error_traces_copy

class DataBase:
    def __init__(self, userName='SENSOR_DATALAKE2', password='smarTclassrooM2Da') -> None:
        self.__userName = userName
        self.__password = password

    def __post(self, co2a1=None, co2a2=None, co2a3=None, co2b1=None, co2b2=None, co2b3=None, co2c1=None, co2c2=None, co2c3=None, fenstera1=None, fenstera2=None, fenstera3=None, fensterb1=None, fensterb2=None, licht1=None, licht2=None):
        def data_to_string(data):
            if data != None:
                return str(data)

            return "null"
        
        data_dict = {
                        "co2a1":data_to_string(co2a1),
                        "co2a2":data_to_string(co2a2),
                        "co2a3":data_to_string(co2a3),
                        "co2b1":data_to_string(co2b1),
                        "co2b2":data_to_string(co2b2),
                        "co2b3":data_to_string(co2b3),
                        "co2c1":data_to_string(co2c1),
                        "co2c2":data_to_string(co2c2),
                        "co2c3":data_to_string(co2c3),
                        "fenstera1":data_to_string(fenstera1),
                        "fenstera2":data_to_string(fenstera2),
                        "fenstera3":data_to_string(fenstera3),
                        "fensterb1":data_to_string(fensterb1),
                        "fensterb2":data_to_string(fensterb2),
                        "licht1":data_to_string(licht1),
                        "licht2":data_to_string(licht2)
                    }

        r = requests.post('https://glusfqycvwrucp9-db202202211424.adb.eu-zurich-1.oraclecloudapps.com/ords/sensor_datalake2/sens/any_sensor_data_entry/',auth=(self.__userName, self.__password), data=data_dict)

        #success
        if r.status_code == 200:
            return True
        
        #failed
        return False
        
    def __send_single_measurement(measurement:json):
        co2a1=None, 
        co2a2=None, 
        co2a3=None, 
        co2b1=None, 
        co2b2=None, 
        co2b3=None, 
        co2c1=None, 
        co2c2=None, 
        co2c3=None, 
        fenstera1=None, 
        fenstera2=None, 
        fenstera3=None, 
        fensterb1=None, 
        fensterb2=None, 
        licht1=None, 
        licht2=None

        data:json = measurement["data"]

        time = datetime.strptime(measurement["timeStamp"], "%d/%m/%Y %H:%M:%S")

        for deviceName in list(data.keys()):

            deviceData = data[deviceName]

            if deviceData != Error.BleFailure:

                for sensorName in list(deviceData.keys()):
                    sensorData = deviceData[sensorName]

                    if sensorData != Error.PhysicalConnectionerror:

                        for measurementName in list(sensorData.keys()):
                            measurementData = sensorData[measurementName]

                            if measurementData != Error.ReadFailure:
                                measurementData


if __name__ == '__main__':    
    #instances
    server = SSL()
    checkError = ErrorCheck()

    with open(os.path.dirname(__file__) + "/creditals", "r") as fd:
        creditals = fd.read().split("\n")
    email = Email(creditals[0], creditals[1], ["tobias.buess2001@gmail.com"]) #, "pjluca48@gmail.com"

    #constants
    status_mail_intervall_min = 1 #sends a status email in a specific intervall
    master_timeout_min = 1 #triggers an email with a masterTimeout message

    #variables
    time_last_jsons_received = monotonic()
    master_timeout_mail_sent = False
    
    print("Start mainLoop")
    old_status_mail_time = monotonic()
    while True:

        try:
            jsons = server.Get_jsonBuffer()

            #as soon as jsons received
            if(len(jsons) > 0):
                time_last_jsons_received = monotonic()
                master_timeout_mail_sent = False #reset flag

                #update database
                print(jsons)

                checkError.CheckJsons_StoreErrors(jsons) #check for errors

            #as soon as intervall reached
            if monotonic() >= old_status_mail_time + (status_mail_intervall_min * 60):
                old_status_mail_time = monotonic()

                email.Send_Status_email(checkError.GetErrors())

            #if master timeout occures
            if (monotonic() >= time_last_jsons_received + (master_timeout_min * 60)) and not master_timeout_mail_sent:
                master_timeout_mail_sent = True #set flag
                email.Send_MasterTimeout_email()

            sleep(1)

        except Exception as ex:
            print(f"Exception occured in mainLoop: {ex}")

    



