# RPI-Pico-Clock
RPI Pico NTP Clock with date and time using TM1637 displays and a DS3231 RTC


This automatically downloads the required python deps on first boot, so it will initially need internet access.

Set wif ssid and password, as well as wifi region and timezone offest in settings.py.

See the main.py for pin assignments two TM1637 displays, DS3231, and DST pin (or just connect to ground if you don't have daylight savings).
