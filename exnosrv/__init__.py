# This code is based on schneider's work in this merge request https://git.card10.badge.events.ccc.de/card10/firmware/-/merge_requests/392

import interrupt
import sys_ble
import time
import vibra
import display
import color
import buttons
import leds
import config
import struct
import power
import math
import os
import sys
import gc

sys.path.append("/apps/exnosrv/")

# Pure-Python AES https://github.com/ricmoo/pyaes MIT License
import pyaes

# Micropython-lib https://github.com/micropython/micropython-lib MIT License
import hashlib
import hmac

DM_ADV_TYPE_FLAGS = 0x01
DM_ADV_TYPE_16_UUID = 0x03
DM_ADV_TYPE_SERVICE_DATA = 0x16
UUID = b"\x6f\xfd"
TIMEOUT = 120
WRITE_TIMEOUT = 30
WRITE_THRESHOLD = 10
EXPNO_FILENAME = "exno.bin"
TEK_FILENAME = "tek.bin"

MODE_OFF = 0
MODE_ON_NEW_MAC = 1
MODE_ON_RX = 2
MODE_BOTH = 3

BL_TIMEOUT = 3000

seen = {}
seen_towrite = {}
last_towrite_add = 0
vib_mode = MODE_BOTH
led_mode = MODE_BOTH

packet_count = 0
write_count = 0


# ----- Tools for sending exposure notifications -----

# HKDF Code shamelessly stolen from Wikipedia
hash_len = 32
def hmac_sha256(key, data):
    return hmac.new(key, data, hashlib.sha256).digest()

def hkdf(length: int, ikm, salt: bytes = b"", info: bytes = b"") -> bytes:
    if len(salt) == 0:
        salt = bytes([0]*hash_len)
    prk = hmac_sha256(salt, ikm)
    t = b""
    okm = b""
    for i in range(math.ceil(length / hash_len)):
        t = hmac_sha256(prk, t + info + bytes([1+i]))
        okm += t
    return okm[:length]

# RPI/AEM Key generation and encryption based on https://github.com/mh-/diagnosis-keys/blob/master/lib/crypto.py
interval_length_minutes = 10
tek_rolling_period=144

def en_interval_number(timestamp_seconds):
    return timestamp_seconds // (60 * interval_length_minutes)

def encoded_en_interval_number(enin):
    return struct.pack("<I", enin)

def derive_rpi_key(tek):
    return hkdf(length=16, ikm=tek, info="EN-RPIK".encode("UTF-8"))

def derive_aem_key(tek):
    return hkdf(length=16, ikm=tek, info="EN-AEMK".encode("UTF-8"))

def encrypt_rpi(rpi_key, interval_number):
    enin = encoded_en_interval_number(interval_number)
    padded_data = "EN-RPI".encode("UTF-8") + bytes([0x00] * 6) + enin
    cipher = pyaes.AESModeOfOperationECB(rpi_key)
    return cipher.encrypt(padded_data)

def encrypt_aem(aem_key, aem, rpi):
    cipher = pyaes.AESModeOfOperationCTR(aem_key, counter = pyaes.Counter(initial_value = rpi))
    return cipher.encrypt(aem)

def generate_tek():
    return os.urandom(16)

def generate_aem(tx_pwr, aem_key, rpi):
    version = 0b01000000 # Version 1.0
    data = struct.pack("<BbBB", version, int(tx_pwr), 0, 0)
    return encrypt_aem(aem_key, data, rpi)

def write_tek_to_file(tek, tek_interval):
    global write_count

    write_count += 1
    print("Writing TEK to flash")
    with open(TEK_FILENAME, "ab") as outfile:
        outfile.write(struct.pack("<L16s", tek_interval, tek))
    print("Write finished")

# BLE TX
def tx_expno(ble_mac, rpi, aem):
    print("TX MAC:", bytes2hex(ble_mac, ":"), "RPI:", bytes2hex(rpi), "AEM:", bytes2hex(aem))


# ----- Tools for receiving exposure notifications -----

def parse_advertisement_data(data):
    ads = {}

    l = len(data)
    p = 0
    while p < l:
        ad_len = data[p]
        p += 1
        if ad_len > 0:
            ad_type = data[p]
            ad_data = b""
            p += 1
            if ad_len > 1:
                ad_data = data[p : p + ad_len - 1]
                p += ad_len - 1
            ads[ad_type] = ad_data
    return ads


def bytes2hex(bin, sep=""):
    return sep.join(["%02x" % x for x in bin])


def process_covid_data(mac, service_data, rssi, flags):
    global vib_mode
    global packet_count

    if vib_mode in [MODE_ON_RX, MODE_BOTH]:
        vibra.vibrate(10)

    if vib_mode in [MODE_ON_NEW_MAC, MODE_BOTH] and mac not in seen:
        vibra.vibrate(100)

    if led_mode in [MODE_ON_RX, MODE_BOTH]:
        leds.flash_rocket(0, 31, 20)

    if led_mode in [MODE_ON_NEW_MAC, MODE_BOTH] and mac not in seen:
        leds.flash_rocket(1, 31, 200)

    packet_count += 1

    # try to produce a small int
    last_rx_time = time.time() - t0
    if mac in seen:
        print(bytes2hex(mac, ":"), rssi, bytes2hex(service_data), flags, seen[mac][1]+1)
        seen[mac][0] = int(last_rx_time)
        seen[mac][1] += 1 # increase counter
        seen[mac][2][0] = max(seen[mac][2][0], rssi)
        seen[mac][2][1] = (seen[mac][2][1] + rssi)/2
        seen[mac][2][2] = min(seen[mac][2][2], rssi)
        seen[mac][3][1] = time.unix_time()
    else:
        print(bytes2hex(mac, ":"), rssi, bytes2hex(service_data), flags, "1")
        # The elements are
        # - last rx time
        # - seen count
        # - rssi
        #   - max
        #   - avg
        #   - min
        # - timestamps
        #   - first seen
        #   - last seen
        # - flags
        # - service data
        seen[mac] = [int(last_rx_time), 1, [rssi, rssi, rssi], [time.unix_time(), time.unix_time()], flags, service_data]


def write_to_file(data):
    global write_count

    write_count += 1
    print("Writing", len(data), "seen MACs into flash...")
    with open(EXPNO_FILENAME, "ab") as outfile:
        for mac in data:
            outfile.write(struct.pack("<6sHiiiQQ20s", mac, data[mac][1], int(data[mac][2][0]*100), int(data[mac][2][1]*100), int(data[mac][2][2]*100), data[mac][3][0], data[mac][3][1], data[mac][5]))
    print("Write finished")


def prune():
    global seen
    global seen_towrite
    global last_towrite_add
    seen_pruned = {}
    now = time.time() - t0

    for mac in seen:
        if seen[mac][0] + TIMEOUT > now:
            seen_pruned[mac] = seen[mac]
        else:
            print("Add MAC", mac, "to write queue")
            seen_towrite[mac] = seen[mac]
            last_towrite_add = now

    seen = seen_pruned

    if len(seen_towrite) >= WRITE_THRESHOLD or (last_towrite_add + WRITE_TIMEOUT < now and len(seen_towrite) > 0):
        write_to_file(seen_towrite)
        seen_towrite = {}


def process_scan_report(scan_report):
    ads = parse_advertisement_data(scan_report[0])
    mac = scan_report[4]
    mac = bytes([mac[5], mac[4], mac[3], mac[2], mac[1], mac[0]])
    rssi = scan_report[1]

    # print(bytes2hex(mac, ':'), rssi, bytes2hex(scan_report[0]), ads)
    # According to spec there is no other service announced and the
    # service is always listed in the complete list of 16 bit services
    if DM_ADV_TYPE_16_UUID in ads:
        if ads[DM_ADV_TYPE_16_UUID] == UUID:
            if DM_ADV_TYPE_SERVICE_DATA in ads:
                flags = None
                if DM_ADV_TYPE_FLAGS in ads:
                    flags = ads[DM_ADV_TYPE_FLAGS]
                # service data contains another copy of the service UUID
                process_covid_data(mac, ads[DM_ADV_TYPE_SERVICE_DATA][2:], rssi, flags)


def ble_callback(_):
    event = sys_ble.get_event()
    if event == sys_ble.EVENT_SCAN_REPORT:
        while True:
            scan_report = sys_ble.get_scan_report()
            if scan_report == None:
                break
            process_scan_report(scan_report)
        prune()


def show_stats():
    seen_google = 0
    seen_apple = 0

    t = time.time() - t0

    t_min = t

    # Make a copy as `seen` could change in between
    # and we're not locking it
    seen_copy = seen.copy()
    for mac in seen_copy:
        info = seen_copy[mac]
        if info[0] < t_min:
            t_min = info[0]

    window = (t - t_min) if len(seen_copy) > 0 else (t - last_rx_time)

    disp.clear()
    disp.print("Last %us" % window, posy=0, fg=color.WHITE)
    disp.print("Tot: %d" % packet_count, posy=20, fg=color.WHITE)
    disp.print("WC:  %d" % write_count, posy=40, fg=color.WHITE)
    disp.print("Bat: %.2fV" % power.read_battery_voltage(), posy=60, fg=color.WHITE)
    disp.update()


last_rx_time = 0
disp = display.open()
v_old = 0
pause = 1

interrupt.set_callback(interrupt.BLE, ble_callback)
interrupt.enable_callback(interrupt.BLE)

try:
    vib_mode = int(config.get_string("exno_vib_mode"))
except:
    pass

try:
    led_mode = int(config.get_string("exno_led_mode"))
except:
    pass

disp.clear()
disp.print(" Exp Notif", posy=0, fg=color.WHITE)
disp.print("  Logger", posy=20, fg=color.WHITE)
disp.print("           ", posy=40, fg=color.WHITE)
disp.print("   BL On ->", posy=60, fg=color.WHITE)
disp.update()

time.sleep(3)

t0 = time.time()
sys_ble.scan_start()

bl_on_time = time.monotonic_ms()
bl_on = True


# Variables for sending Exposure Notifications
intnum = 0
intnum_old = 0
tek = None
tek_intnum = 0
rpi_key = None
aem_key = None
rpi = None
aem = None
ble_mac = None
tx_pause = 1

while True:
    v_new = buttons.read()
    v = ~v_old & v_new
    v_old = v_new


    intnum = en_interval_number(time.unix_time())
    if intnum != intnum_old:
        print("Interval Number changed...")
        if tek == None or (intnum - tek_intnum) >= 144 or ble_mac == None:
            print("Generating new TEK...")
            tek = generate_tek()
            rpi_key = derive_rpi_key(tek)
            aem_key = derive_aem_key(tek)
            tek_intnum = intnum
            write_tek_to_file(tek, tek_intnum)
            print("TEK:", bytes2hex(tek))
        print("Generationg new BLE MAC and RPI/AEM...")
        ble_mac = os.urandom(6)
        rpi = encrypt_rpi(rpi_key, intnum)
        aem = generate_aem(20, aem_key, rpi)
        intnum_old = intnum

    tx_pause -= 1
    if tx_pause == 0:
        if ble_mac != None and rpi != None and aem != None:
            tx_expno(ble_mac, rpi, aem)
        tx_pause = 5

    if bl_on and time.monotonic_ms() > bl_on_time + BL_TIMEOUT:
        disp.backlight(0)
        bl_on = False

    if v & buttons.BOTTOM_RIGHT:
        show_stats()
        bl_on = True
        disp.backlight(100)
        bl_on_time = time.monotonic_ms()

    pause -= 1
    if pause == 0:
        if bl_on:
            show_stats()
            gc.collect()
            print(gc.mem_free())
        pause = 20
        prune()

    time.sleep(0.05)
