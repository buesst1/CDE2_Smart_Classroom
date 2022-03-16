#installation von os und libraries (siehe guide: https://learn.adafruit.com/circuitpython-ble-libraries-on-any-computer/getting-python-on-your-host-computer)
->das installierte betriebssystem lautet: Raspberry pi OS Lite (aktiviere ssh over usb mit wifi: https://desertbot.io/blog/ssh-into-pi-zero-over-usb https://desertbot.io/blog/setup-pi-zero-w-headless-wifi)
-sudo apt-get update
-sudo apt-get upprade
-sudo apt install python3-pip -> pip3 installieren (nie sudo pip3 verwenden (libraries können beschädigt werden))

->libraries installieren
-pip3 install --upgrade adafruit-blinka-bleio adafruit-circuitpython-ble -> installation von ble libraries

->benutzer zu bluetooth group hinzufügen
-sudo usermod -a -G bluetooth $USER
-sudo reboot

#weitere nützliche tools
->um dateien über ssh an den rpi zu senden kann folgender command im cmd verwendet werden:
-pscp source_file_name userid@server_name:/path/destination_file_name -> beispiel: pscp C:\Users\tobia\OneDrive\Dokumente\GitHub\CDE2_Smart_Classroom\Master\master.py pi@raspberrypi.local:/home/pi/master.py

