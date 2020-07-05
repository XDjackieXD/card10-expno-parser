#!/usr/bin/python
from datetime import datetime
import struct
import sys

def bytes2hex(bin, sep=""):
    return sep.join(["%02x" % x for x in bin])

file = open(sys.argv[1], "rb")
rawdata = file.read()
file.close()

total_uniq = 0
total_rx = 0
max_seen = 0

for i in range(0, int(len(rawdata)/56)):
    uniq = struct.unpack("<6sHiiiQQ20s", rawdata[i*56:(i+1)*56])
    mac = uniq[0]
    packet_count = uniq[1]
    rssi_max = uniq[2]/100
    rssi_avg = uniq[3]/100
    rssi_min = uniq[4]/100
    start_time = uniq[5]
    end_time = uniq[6]
    rpi = uniq[7][0:16]
    aem = uniq[7][16:]
    print(datetime.utcfromtimestamp(start_time).strftime('[%Y.%m.%d %H:%M:%S]') + " MAC address " + bytes2hex(mac, ":") + " seen for" + f'{end_time-start_time: 5}' + "s, received" + f'{packet_count: 5}' + " packets")
    total_uniq += 1
    total_rx += packet_count
    if end_time-start_time > max_seen:
        max_seen = end_time-start_time

print("Total unique MACs seen:", str(total_uniq))
print("Total packets received:", str(total_rx))
print("Maximum time one MAC was seen:", str(max_seen))
