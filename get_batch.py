#!/usr/bin/python
import json
import urllib3

# Austrian batch data endpoint
base = "https://cdn.prod-rca-coronaapp-fd.net"
batch_endpoint = "/exposures/at/index.json"

http = urllib3.PoolManager()

r = http.request("GET", base + batch_endpoint)
if r.status == 200:
    file_url = base + json.loads(r.data)["full_14_batch"]["batch_file_paths"][0]
    rd = http.request("GET", file_url)
    if rd.status == 200:
        with open("at_b14.zip", "wb") as f:
            f.write(rd.data)
    else:
        print("Get File:", rd.status)
else:
    print("Get File List:", r.status)
