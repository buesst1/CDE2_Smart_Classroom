import json
from threading import Thread
import socket
import ssl
import os
from pyrsistent import T

from sympy import EX

class SSL:
    def __init__(self, host="0.0.0.0", port = 443) -> None:
        self.HOST = host
        self.PORT = port

        self.__dirname = os.path.dirname(__file__)
        self.__conext = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        self.__conext.load_cert_chain(self.__dirname + r'\SSL\certificate.crt', self.__dirname + r'\SSL\certificate.key')

        self.__input_jsons = []

        #start listener thread
        self.__listener_thread = Thread(target=self.__listener)
        self.__listener_thread.start()

    def __listener(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
                sock.bind((self.HOST, self.PORT))
                sock.listen()

                with self.__conext.wrap_socket(sock, server_side=True) as ssock:
                    while True:
                        try:
                            conn, addr = ssock.accept()
                            self.__handle_client(conn)

                        except Exception as ex:
                            print(f"Exception occured during accepting client: {ex}")
                        

        except Exception as ex:
            print(f"Critical error in listener thread (exit thread): {ex}")

    def __handle_client(self, conn:ssl.SSLSocket):
        try:
            message = conn.read().decode(encoding="utf-8")

            splitted_msg = message.split("~")

            if len(splitted_msg) != 2:
                conn.write(str.encode("failed", encoding="utf-8"))
                raise Exception("message has incorrect length")

            if splitted_msg[0] == "data":
                if self.__handle__jsons(splitted_msg[1]):
                    conn.write(str.encode("confirmed", encoding="utf-8"))
                else:
                    conn.write(str.encode("failed", encoding="utf-8"))

            else:
                conn.write(str.encode("failed", encoding="utf-8"))
                raise Exception("unknown command received")

        except Exception as ex:
            print(f"Exception occured during handling client: {ex}")

        finally:
            #finally close connection 
            try:
                conn.close()
            except:
                pass

    def __handle__jsons(self, stringified_jsons:str) -> bool:
        try:
            all_jsons = stringified_jsons.split("ʮ")

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





