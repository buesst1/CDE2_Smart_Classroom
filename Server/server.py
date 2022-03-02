import socket
import ssl
import os


HOST = "localhost"
PORT = 443
dirname = os.path.dirname(__file__)

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(dirname + r'\SSL\certificate.crt', dirname + r'\SSL\certificate.key')

with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
    sock.bind((HOST, PORT))
    sock.listen(5)
    with context.wrap_socket(sock, server_side=True) as ssock:
        conn, addr = ssock.accept()

        print(conn.read().decode(encoding="utf-8"))

        conn.write(str.encode("test", encoding="utf-8"))


