#!/usr/bin/python
import struct
import sys

def bytes2hex(bin, sep=""):
    return sep.join(["%02x" % x for x in bin])

file = open(sys.argv[1], "rb")
rawdata = file.read()
file.close()

for i in range(0, int(len(rawdata)/20)):
    uniq = struct.unpack("<L16s", rawdata[i*20:(i+1)*20])
    intnum = uniq[0]
    tek = uniq[1]
    print(str(intnum) + ";" + bytes2hex(tek))
