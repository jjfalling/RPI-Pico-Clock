# assumes gw runs ntp
# restart required after channging dst switch

#TODO:
# - update tz offset without rebooting
# - finish ds3231 rtc support

import ntptime
import network
import time
from machine import Pin
import rp2
import mip
import os
from settings import CONFIG
import micropython

led = Pin("LED", Pin.OUT)
tz_switch = led = Pin(22, Pin.IN, Pin.PULL_UP) # connect switch to ground

def init_displays():
    # define display pins here
    tm_clock = tm1637.TM1637(clk=Pin(19), dio=Pin(18))
    tm_date = tm1637.TM1637(clk=Pin(21), dio=Pin(20))
    clear_display(tm_clock, tm_date)
    return tm_clock, tm_date


def clear_display(tm_clock, tm_date):
    tm_clock.write([0, 0, 0, 0])
    tm_date.write([0, 0, 0, 0])
    
# from https://forum.micropython.org/viewtopic.php?t=8112#p68368
def file_or_dir_exists(filename):
    try:
        os.stat(filename)
        return True
    except OSError:
        return False


def update_ntp():
    global last_ntp_update
    try:
        ntptime.settime()
        last_ntp_update = time.time()
        now = time.localtime()
        # update rtc
        # ds.datetime(now[0], now[1], now[2], now[3], now[4], now[5])
        print("Local time after synchronization：%s" % str(now))
    except Exception as e:
        print("NTP udate failed: {}".format(e))
        try:
            clear_display(tm_clock, tm_date)
            tm_clock.show("ERR")
            tm_date.show("NTP")
        except:
            pass
        time.sleep(5)
    return

# try to display boot msg, if display lib is installed
try:
    import tm1637
    tm_clock, tm_date = init_displays()
    tm_clock.show("BOOT")
    tm_date.show("-ING")
    
except Exception as err:
    pass

ssid = CONFIG['wifi_ssid']
password = CONFIG['wifi_password']
rp2.country(CONFIG['wifi_country'])
sys_timezone = CONFIG['timezone']  # tz offset w/o daylight savings
ntp_server = CONFIG['ntp_server']

if tz_switch.value():
    sys_timezone += 1

# blink on boot
time.sleep(0.25)
led.high()
time.sleep(0.25)
led.low()

wlan = network.WLAN(network.STA_IF)
wlan.active(True)
wlan.connect(ssid, password)
# Wait for connect or fail
max_wait = 15
while max_wait > 0:
    if wlan.status() < 0 or wlan.status() >= 3:
        break
    max_wait -= 1
    print('waiting for connection...')
    time.sleep(1)

last_ntp_update = 0


# self-install deps after wifi is up
if not file_or_dir_exists('lib/tm1637.py'):
    mip.install('github:mcauser/micropython-tm1637/tm1637.py')
if not file_or_dir_exists('lib/datetime.mpy'):
    mip.install('datetime')
# if not file_or_dir_exists('lib/ds3231.py'):
#    mip.install('github:HAIZAKURA/esp-ds3231-micropython/ds3231.py')

import tm1637
import datetime
# from ds3231 import DS3231

tm_clock = tm1637.TM1637(clk=Pin(19), dio=Pin(18))
tm_date = tm1637.TM1637(clk=Pin(21), dio=Pin(20))
clear_display(tm_clock, tm_date)
# ds = DS3231(0, sdapin=16, sclpin=17)


# Handle connection error
if wlan.status() != 3:
    print('network connection failed')
    tm_clock.show("WIFI")
    tm_date.show("ERR")
    time.sleep(5)

else:
    tm_clock.show("WIFI")
    tm_date.show("UP")
    print('connected')
    time.sleep(1)
    led.high()
    status = wlan.ifconfig()
    print('ip = ' + status[0])
    print(status[2])

    print("Local time before synchronization：%s" % str(time.localtime()))

    if ntp_server:
        print('Using ntp server from config')
        ntptime.host = ntp_server
    else:
        print('NTP server not provided, using default gw')
        ntptime.host = status[2]
    ntptime.timeout = 5
    update_ntp()

while True:
    try:
        adjusted_time = time.localtime(time.time() + sys_timezone * 3600)
        tm_clock.numbers(adjusted_time[3], adjusted_time[4])
        tm_date.numbers(adjusted_time[2], adjusted_time[1])
        micropython.mem_info()
        # unsure why, but controller hangs if sleep is less than 1s
        time.sleep(1)

        # update ntp every 6 hours
        if time.time() > last_ntp_update + 21600:
            update_ntp()
    except Exception as err:
        print("Encountered error in main loop" + str(err))
        tm_clock.show("SYS")
        tm_date.show("ERR")
