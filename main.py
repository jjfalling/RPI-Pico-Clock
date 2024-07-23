# internet access is required for the first boot, then after libs are installed and as long as ntp server is local
#  it is no longer needed.
# if not using ntp server in config, then this assumes the net gw runs ntp.
# ds rtc is used as a backup if ntp is unavailable.

import ntptime
import network
import time
from machine import Pin
import rp2
import mip
import os
from settings import CONFIG

VERSION = '1.0.1'

led = Pin("LED", Pin.OUT)
tz_switch = led = Pin(22, Pin.IN, Pin.PULL_UP)  # connect switch to ground

ssid = CONFIG['wifi_ssid']
password = CONFIG['wifi_password']
sys_timezone = CONFIG['timezone']  # tz offset w/o daylight savings
rp2.country(CONFIG.get('wifi_country', 'NL'))
ntp_server = CONFIG.get('ntp_server')
display_brightness = CONFIG.get('display_brightness', 7)

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
        ds_rtc.datetime(now[0], now[1], now[2], now[3], now[4], now[5])
        print("Local time after synchronization: %s" % str(now))
    except Exception as e:
        print("NTP update failed: {}".format(e))
        try:
            clear_display(tm_clock, tm_date)
            tm_clock.show("ERR")
            tm_clock.brightness(display_brightness)
            tm_date.show("NTP")
            tm_date.brightness(display_brightness)

        except:
            pass

        # update system time from ds rtc
        try:
            current_datetime = ds_rtc.datetime()
            # fudge the day of week as it isn't used in this prog and there is no point to calculate it
            import machine
            machine.RTC().datetime((current_datetime[0], current_datetime[1], current_datetime[2], 0, current_datetime[3], current_datetime[4], current_datetime[5], 0))
            print("Updated system datetime from external RTC".format(e))
            print("Local time after reading from external RTC: %s" % str(time.localtime()))

        except Exception as err:
            print("RTC update failed: {}".format(err))

            clear_display(tm_clock, tm_date)
            tm_clock.show("ERR")
            tm_clock.brightness(display_brightness)
            tm_date.show("RTC")
            tm_date.brightness(display_brightness)

        # try to update again in 60 sec
        last_ntp_update = time.time() - 21540

        time.sleep(5)
    return


# try to display boot msg, if display lib is installed
try:
    import tm1637

    tm_clock, tm_date = init_displays()
    tm_clock.show("BOOT")
    tm_clock.brightness(display_brightness)
    tm_date.show("-ING")
    tm_date.brightness(display_brightness)

except Exception as err:
    pass

print('RPI Pico Clock Version: %s' % VERSION)

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
    print('waiting for wifi connection...')
    time.sleep(1)

last_ntp_update = 0

# self-install deps after wifi is up
if not file_or_dir_exists('lib/tm1637.py'):
    mip.install('github:mcauser/micropython-tm1637/tm1637.py')
if not file_or_dir_exists('lib/ds3231.py'):
   mip.install('github:HAIZAKURA/esp-ds3231-micropython/ds3231.py')

import tm1637
from ds3231 import DS3231

tm_clock = tm1637.TM1637(clk=Pin(19), dio=Pin(18))
tm_date = tm1637.TM1637(clk=Pin(21), dio=Pin(20))
clear_display(tm_clock, tm_date)
ds_rtc = DS3231(0, sdapin=16, sclpin=17)

# Handle connection error
if wlan.status() != 3:
    print('network connection failed')
    tm_clock.show("WIFI")
    tm_clock.brightness(display_brightness)
    tm_date.show("ERR")
    tm_date.brightness(display_brightness)
    time.sleep(5)

else:
    tm_clock.show("WIFI")
    tm_clock.brightness(display_brightness)
    tm_date.show("UP")
    tm_date.brightness(display_brightness)
    print('wifi connected')
    time.sleep(1)
    led.high()
    status = wlan.ifconfig()
    print('device ip: ' + status[0])

    print("Local time before synchronization %s" % str(time.localtime()))

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
        # local time is non-dst aware, so adjust when displaying
        if tz_switch.value():
            real_sys_timezone = sys_timezone + 1
        else:
            real_sys_timezone = sys_timezone

        adjusted_time = time.localtime(time.time() + real_sys_timezone * 3600)

        tm_clock.numbers(adjusted_time[3], adjusted_time[4])
        tm_clock.brightness(display_brightness)
        tm_date.numbers(adjusted_time[2], adjusted_time[1])
        tm_date.brightness(display_brightness)
        # micropython.mem_info()
        # unsure why, but controller hangs if sleep is less than 1s
        time.sleep(1)

        # update ntp every 6 hours
        if time.time() > last_ntp_update + 21600:
            update_ntp()
    except Exception as err:
        print("Encountered error in main loop" + str(err))
        tm_clock.show("SYS")
        tm_clock.brightness(display_brightness)
        tm_date.show("ERR")
        tm_date.brightness(display_brightness)
