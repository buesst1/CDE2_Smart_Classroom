import socket
import ssl
from time import sleep

from numpy import byte

HOST = 'solarBroom.com'
PORT = 443

context = ssl.create_default_context()

with socket.create_connection((HOST, PORT)) as sock:
    with context.wrap_socket(sock, server_hostname=HOST) as ssock:
        ssock.write(str.encode("test", encoding="utf-8"))

        ssock.read()