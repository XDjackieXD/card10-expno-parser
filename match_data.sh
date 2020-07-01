#!/bin/bash
./parse.py "$1" > rpis.csv
./get_batch.py
./diagnosis-keys/parse_keys.py -d at_b14.zip -r rpis.csv |grep "MATCH" -A 3
rm at_b14.zip rpis.csv
