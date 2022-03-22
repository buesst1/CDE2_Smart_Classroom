import json
import threading
import socket
import ssl
import os
from time import sleep

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
            #read message
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

            print("Message received!")

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
            for json_ in jsons_list:
                print(json_)

            return True

        except Exception as ex:
            print(f"Execption occured during saving jsons: {ex}")
            return False

if __name__ == '__main__':           
    server = SSL()

    print("Start mainLoop")
    while True:
        sleep(1)
    



