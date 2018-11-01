"""
Very quick and dirty script to insert FMI PM data from CSV file into InfluxDB.
"""

import sys
import os
import math
import csv
import datetime
import influxdb
from dateutil.parser import parse
import pytz

if len(sys.argv) < 2:
    print("Usage:\n\tpython {} pm_min PM10_PM25_min.csv".format(sys.argv[0]))
    exit(1)


tz = pytz.timezone('Europe/Helsinki')
epoch_dt = pytz.UTC.localize(datetime.datetime(1970, 1, 1))
dev_id = 'fmi_2'
measurement = sys.argv[1]

# Example data
"""
<U+FEFF>Station: Mäkelänkatu  Periodically: 27/09/2018 00:01-11/10/2018 00:00  Type: AVG 1 Min. [1 Min.];;
;;
Date & Time;PM10;PM2_5
;ug/m3;ug/m3
27/09/2018 00:01;-0.7;0.7
27/09/2018 00:02;-0.4;0.8
27/09/2018 00:03;-0.1;0.9
27/09/2018 00:04;0;0.9
"""


def get_influxdb_client(host='127.0.0.1', port=8086, database='mydb'):
    iclient = influxdb.InfluxDBClient(host=host, port=port, database=database)
    iclient.create_database(database)
    return iclient


def create_influxdb_obj(dev_id, measurement, fields, epoch):
    for k, v in fields.items():
        if v is not None:
            fields[k] = float(v)
    if fields == {}:
        return None
    measurement = {
        "measurement": measurement,
        "tags": {
            "dev-id": dev_id,
        },
        "time": epoch,
        "fields": fields
    }
    return measurement


with open(sys.argv[2], newline='') as csvfile:
    spamreader = csv.reader(csvfile, delimiter=';')
    iclient = get_influxdb_client(database='aq2')
    for row in spamreader:
        ts = None
        try:
            ts = parse(row[0], dayfirst=True)
            ts = tz.localize(ts)
            epoch = int((ts - epoch_dt).total_seconds())
        except ValueError as err:
            continue  # contains header and empty rows
        fields = {}
        try:
            fields['pm10'] = float(row[1])
        except ValueError:
            pass
        try:
            fields['pm25'] = float(row[2])
        except ValueError:
            pass
        json_body = create_influxdb_obj(dev_id, measurement, fields, epoch)
        print(json_body)
        if json_body is not None:
            saved = iclient.write_points([json_body], time_precision='s')  # Note []
