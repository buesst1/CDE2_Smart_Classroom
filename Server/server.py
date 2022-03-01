from OpenSSL import crypto, SSL
from ast import While
import socket
import ssl
import pathlib

HOST = "127.0.0.1"
PORT = 443
file_path = str(pathlib.Path(__file__).parent.resolve())


def cert_gen(
    emailAddress="tobias.buess2001@gmail.com",
    commonName="smartClassroom",
    countryName="CH",
    localityName="Wenslingen",
    stateOrProvinceName="Baselland",
    organizationName="FHNW",
    organizationUnitName="FHNW",
    serialNumber=0,
    validityStartInSeconds=0,
    validityEndInSeconds=10*365*24*60*60,
    KEY_FILE = "private.key",
    CERT_FILE="selfsigned.crt"):

    #can look at generated file using openssl:
    #openssl x509 -inform pem -in selfsigned.crt -noout -text
    # create a key pair
    k = crypto.PKey()
    k.generate_key(crypto.TYPE_RSA, 4096)
    # create a self-signed cert
    cert = crypto.X509()
    cert.get_subject().C = countryName
    cert.get_subject().ST = stateOrProvinceName
    cert.get_subject().L = localityName
    cert.get_subject().O = organizationName
    cert.get_subject().OU = organizationUnitName
    cert.get_subject().CN = commonName
    cert.get_subject().emailAddress = emailAddress
    cert.set_serial_number(serialNumber)
    cert.gmtime_adj_notBefore(0)
    cert.gmtime_adj_notAfter(validityEndInSeconds)
    cert.set_issuer(cert.get_subject())
    cert.set_pubkey(k)
    cert.sign(k, 'sha512')
    with open(CERT_FILE, "wt") as f:
        f.write(crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode("utf-8"))
    with open(KEY_FILE, "wt") as f:
        f.write(crypto.dump_privatekey(crypto.FILETYPE_PEM, k).decode("utf-8"))

context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
context.load_cert_chain(certfile = "selfsigned.crt", keyfile = "private.key")

def main():
    while True:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM, 0) as sock:
            sock.bind((HOST, PORT))
            sock.listen(5)

            with context.wrap_socket(sock, server_side=True) as ssock:
                conn, addr = ssock.accept()

main()


