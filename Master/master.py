import socket
import ssl
import _bleio
import adafruit_ble
from adafruit_ble.advertising.standard import Advertisement

class SSL:
    def __init__(self) -> None:
        self.HOST = 'solarBroom.com'
        self.PORT = 443

    def __Send_Read(self, message:str):
        context = ssl.create_default_context()
        with socket.create_connection((self.HOST, self.PORT)) as sock:
            with context.wrap_socket(sock, server_hostname=self.HOST) as ssock:
    
                ssock.write(str.encode(message, encoding="utf-8"))

                return ssock.read()



# CircuitPython <6 uses its own ConnectionError type. So, is it if available. Otherwise,
# the built in ConnectionError is used.
connection_error = ConnectionError
if hasattr(_bleio, "ConnectionError"):
    connection_error = _bleio.ConnectionError

# PyLint can't find BLERadio for some reason so special case it here.
ble = adafruit_ble.BLERadio()  # pylint: disable=no-member

while True:
    print("scanning")
    found_addr = set()
    for advertisement in ble.start_scan(Advertisement, timeout=5):
        addr = advertisement.address

        if addr not in found_addr:
            found_addr.add(addr)

            name_raw = advertisement.complete_name

            if not name_raw:
                continue

            name = name_raw.strip("\x00")

            print(f"Device with name: {name} and address: {addr} found")

    print("scan done")


