from ast import While
import socket
import ssl
import pathlib

HOST = "127.0.0.1"
PORT = 443
file_path = str(pathlib.Path(__file__).parent.resolve())

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(keyfile= file_path + "/SSL/PEM.pem", keyfile=file_path + "/SSL/PEM.pem")

while True:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
        sock.bind((HOST, PORT))
        sock.listen(5)

        with context.wrap_socket(sock, server_side=True) as ssock:
            conn, addr = ssock.accept()
        


