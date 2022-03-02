import socket
import ssl
from time import sleep

from numpy import byte

hostname = 'solarbroom.com'
context = ssl.create_default_context()

with socket.create_connection((hostname, 8443)) as sock:
    with context.wrap_socket(sock, server_hostname=hostname) as ssock:
        ssock.write(str.encode("test", encoding="utf-8"))

        ssock.read()