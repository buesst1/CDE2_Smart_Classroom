from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import json
import threading
import socket
import ssl
import os
from time import sleep
import smtplib
import yaml

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

                    data = conn.recv(1)
                else:
                    break

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
            print (f'Something went wrong...: {ex}')

    def __get_error_trace_back(self, json_stringified:json, bat_voltage_lowError_threshold:float = 3.5):
        """
        bat_voltage_lowError_threshold -> you will get a warning as soon as you are lower or equal that threshold
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
                                if float(measurementData) <= bat_voltage_lowError_threshold:
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

    def Send_Email_on_jsons_with_error(self, jsons:list):
        for json_ in jsons:
            traced_errors = self.__get_error_trace_back(json_)
            
            #error occured
            if len(list(traced_errors.keys())) > 0:

                message = f"Bei der Messung vom {traced_errors.pop('timestamp')}\nist/sind folgende(r) Fehler aufgetreten:\n\n\n{yaml.dump(traced_errors)}"

                self.Send_Email(self.__receipents, "Smart Classroom Error/Warning Report", message)


if __name__ == '__main__':      
    server = SSL()

    with open(os.path.dirname(__file__) + "/creditals", "r") as fd:
        creditals = fd.read().split("\n")

    email = Email(creditals[0], creditals[1], ["tobias.buess2001@gmail.com"])

    print("Start mainLoop")
    while True:
        jsons = server.Get_jsonBuffer()

        if(len(jsons) > 0):
            email.Send_Email_on_jsons_with_error(jsons)

        sleep(1)

    



