#!/usr/bin/python
import struct
import sys

def bytes2hex(bin, sep=""):
    return sep.join(["%02x" % x for x in bin])

file = open(sys.argv[1], "rb")
rawdata = file.read()
file.close()

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
    # print in csv format compatible with mh-/diagnosis-keys
    print(str(start_time) + ";" + str(end_time) + ";" + bytes2hex(rpi) + ";" + bytes2hex(aem) + ";" + str(int(rssi_max)) + ";" + bytes2hex(mac, ":"))
