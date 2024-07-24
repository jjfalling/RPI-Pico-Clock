# internet access is required for the first boot, then after libs are installed and as long as ntp server is local
#  it is no longer needed.
# if not using ntp server in config, then this assumes the net gw runs ntp.
# ds rtc is used as a backup if ntp is unavailable.

import os
import time

import mip
import network
import ntptime
import rp2
from machine import Pin

from settings import CONFIG

VERSION = '1.0.1'

TZ_SWITCH = LED = Pin(22, Pin.IN, Pin.PULL_UP)  # connect switch to ground
TM_CLOCK_CLK_PIN = Pin(19)
TM_CLOCK_DIO_PIN = Pin(18)
TM_DATE_CLK_PIN = Pin(21)
TM_DATE_DIO_PIN = Pin(20)
DS3231_SDA_PIN = Pin(16)
DS3231_SLC_PIN = Pin(17)
LED = Pin("LED", Pin.OUT)

ssid = CONFIG['wifi_ssid']
password = CONFIG['wifi_password']
sys_timezone = CONFIG['timezone']  # tz offset w/o daylight savings
rp2.country(CONFIG.get('wifi_country', 'NL'))
ntp_server = CONFIG.get('ntp_server')
display_brightness = CONFIG.get('display_brightness', 7)
tm_clock = None
tm_date = None

def init_displays():
    import tm1637
    tm_clock = tm1637.TM1637(clk=TM_CLOCK_CLK_PIN, dio=TM_CLOCK_DIO_PIN)
    tm_date = tm1637.TM1637(clk=TM_DATE_CLK_PIN, dio=TM_DATE_DIO_PIN)
    clear_display(tm_clock, tm_date)
    return tm_clock, tm_date


def display_text(clock_disp, date_disp):
    clear_display(tm_clock, tm_date)
    tm_clock.show(clock_disp)
    tm_clock.brightness(display_brightness)
    tm_date.show(date_disp)
    tm_date.brightness(display_brightness)


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
            display_text("ERR", "NTP")

        except:
            pass

        # update system time from ds rtc
        try:
            current_datetime = ds_rtc.datetime()
            # fudge the day of week as it isn't used in this prog and there is no point to calculate it
            import machine
            machine.RTC().datetime((current_datetime[0], current_datetime[1], current_datetime[2], 0,
                                    current_datetime[3], current_datetime[4], current_datetime[5], 0))
            print("Updated system datetime from external RTC".format(e))
            print("Local time after reading from external RTC: %s" % str(time.localtime()))

        except Exception as err:
            print("RTC update failed: {}".format(err))
            display_text("ERR", "RTC")

        # try to update again in 60 sec
        last_ntp_update = time.time() - 21540

        time.sleep(5)
    return


print('RPI Pico Clock Version: %s' % VERSION)

# blink on boot
time.sleep(0.25)
LED.high()
time.sleep(0.25)
LED.low()

# try to init display here, if lib isn't installed then just wait
try:
    tm_clock, tm_date = init_displays()
    display_text("BOOT", "ING")
except:
    pass

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

from ds3231 import DS3231
ds_rtc = DS3231(0, sdapin=DS3231_SDA_PIN, sclpin=DS3231_SLC_PIN)

# init displays if not done already
if not tm_clock or not tm_date:
    tm_clock, tm_date = init_displays()
    display_text("BOOT", "ING")

# Handle connection error
if wlan.status() != 3:
    print('network connection failed')
    display_text("ERR", "WIFI")

    time.sleep(5)

else:
    print('wifi connected')
    display_text("WIFI", " UP")
    time.sleep(1)
    LED.high()
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
        if TZ_SWITCH.value():
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
        display_text("ERR", "SYS")
