#installation von os und libraries (siehe guide: https://learn.adafruit.com/circuitpython-ble-libraries-on-any-computer/getting-python-on-your-host-computer)
->das installierte betriebssystem lautet: Raspberry pi OS Lite (aktiviere ssh over usb mit wifi: https://desertbot.io/blog/ssh-into-pi-zero-over-usb https://desertbot.io/blog/setup-pi-zero-w-headless-wifi)
-sudo apt-get update && sudo apt-get upgrade
-sudo apt install python3-pip -> pip3/python3 installieren (nie sudo pip3 verwenden (libraries können beschädigt werden))

->libraries installieren
-pip3 install --upgrade adafruit-blinka-bleio adafruit-circuitpython-ble iterators -> installation von ble und iterators librariy

->benutzer zu bluetooth group hinzufügen
-sudo usermod -a -G bluetooth $USER
-sudo reboot

->master script an raspi senden (siehe unten)
-pscp C:\Users\tobia\OneDrive\Dokumente\GitHub\CDE2_Smart_Classroom\Master\master.py pi@raspberrypi.local:/home/pi/master.py

->Auto run hinzufügen more:(https://www.interelectronix.com/raspberry-pi-4-autostart-qt-application-during-boot.html)
-cd /etc/systemd/system && sudo nano master.service -> folgender text innerhalb der brackets unten einfügen
"
[Unit]
Description=SmartClassroom master software
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=pi
Group=pi
WorkingDirectory=/home/pi/
ExecStart=/usr/bin/python3 /home/pi/master.py

[Install]
WantedBy=multi-user.target
"

-sudo systemctl enable master.service -> enable service
-sudo systemctl disable getty@tty1 && sudo systemctl mask plymouth-start.service

->status des services abrufen
-sudo systemctl status master.service -> status abrufen




#weitere nützliche tools
->um dateien über ssh an den rpi zu senden kann folgender command im cmd verwendet werden:
-pscp source_file_name userid@server_name:/path/destination_file_name -> beispiel: pscp C:\Users\tobia\OneDrive\Dokumente\GitHub\CDE2_Smart_Classroom\Master\master.py pi@raspberrypi.local:/home/pi/master.py

