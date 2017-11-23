import sys
import os
import zipfile
import json
import logging
import argparse
from dateutil.parser import parse
import simplekml

#logging.basicConfig(stream=sys.stderr, level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')


def read_data_from_zipfile(zipname):
    logging.info("Processing zip file: {}".format(zipname))
    zf = zipfile.ZipFile(zipname, 'r')
    fnames = zf.namelist()
    # Get all gps and data logs to a separate lists
    gps_names = [x for x in fnames if 'gps_log' in x]
    data_names = [x for x in fnames if 'data_log' in x]
    # Sort, chronologically
    gps_names.sort()
    data_names.sort()
    # Read data lines from files
    gps_data = []
    sensor_data = []
    for fn in gps_names:
        logging.debug("Processing file: {}".format(fn))
        datalines = zf.read(fn).splitlines()
        for line in datalines:
            data = json.loads(line)
            data['timestamp'] = parse(data['time'])
            gps_data.append(data)
    for fn in data_names:
        logging.debug("Processing file: {}".format(fn))
        datalines = zf.read(fn).splitlines()
        for line in datalines:
            data = json.loads(line)
            data['timestamp'] = parse(data['time'])
            sensor_data.append(data)
    from operator import itemgetter
    gps_data = sorted(gps_data, key=itemgetter('timestamp'))
    sensor_data = sorted(sensor_data, key=itemgetter('timestamp'))
    return gps_data, sensor_data


def interpolate_position(gps_data, sensor_data, output, limit=0):
    new_data = []
    if limit > 0:
        sensor_data = sensor_data[:limit]
    for s in sensor_data:
        # TODO: remove looping all gps_data every time
        for i in range(1, len(gps_data) - 1):
            if gps_data[i]['timestamp'] > s['timestamp']:
                prev_gps_sec = (s['timestamp'] - gps_data[i - 1]['timestamp']).total_seconds()
                next_gps_sec = (gps_data[i]['timestamp'] - s['timestamp']).total_seconds()
                prev_gps = gps_data[i - 1]
                next_gps = gps_data[i]
                try:
                    interpolated_lat = (next_gps_sec / (prev_gps_sec + next_gps_sec)) * prev_gps['lat'] + \
                                       (prev_gps_sec / (prev_gps_sec + next_gps_sec)) * next_gps['lat']
                    interpolated_lon = (next_gps_sec / (prev_gps_sec + next_gps_sec)) * prev_gps['lon'] + \
                                       (prev_gps_sec / (prev_gps_sec + next_gps_sec)) * next_gps['lon']
                except KeyError as e:
                    logging.critical(prev_gps)
                    raise
                new_data.append([interpolated_lon, interpolated_lat])
                s['lat'] = interpolated_lat
                s['lon'] = interpolated_lon
                s['acc'] = max(prev_gps['acc'], next_gps['acc'])
                s['alt'] = (prev_gps['alt'] + next_gps['alt']) / 2
                logging.debug("{} {} {} {} {} {} {}".format(interpolated_lat, interpolated_lon,
                    gps_data[i - 1]['timestamp'],
                    prev_gps_sec,
                    s['timestamp'],
                    next_gps_sec,
                    gps_data[i]['timestamp'])
                )
                break
    kml = simplekml.Kml()
    lin = kml.newlinestring(name="Sensor user path", description="The path travelled by user", coords=new_data)
    lin.style.linestyle.color = 'ff0000ff'  # Red
    lin.style.linestyle.width = 5  # pixels
    i = 0
    json_fn = output + '.json'
    kml_fn = output + '.kml'
    with open(json_fn, 'wt') as f:
        for d in sensor_data:
            if i % 10 == 0:  # use only every 10th data points for now
                logging.debug(d)
                pnt = kml.newpoint(coords=[(d['lon'], d['lat'], d['alt'])])
                pnt.style.balloonstyle.text = "{}".format(d['ascii'])
                pnt.style.iconstyle.icon.href = 'http://maps.google.com/mapfiles/kml/shapes/placemark_circle.png'
            i += 1
            d.pop('timestamp')
            f.write(json.dumps(d) + "\n")
    logging.info("Wrote json data to: {}".format(json_fn))
    kml.save(kml_fn)
    logging.info("Wrote kml data to: {}".format(kml_fn))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("fname", type=str, nargs='+', help="ZIP file name(s)")
    parser.add_argument("-v", action='count', default=0, help="Increase output verbosity (v - vvvv)")
    parser.add_argument("-l", "--limit", type=int, default=0, help="Parse first l sensor data points")
    parser.add_argument("-O", "--output", help="Where to write the output")
    # parser.add_argument("-l", "--logfile", default=sys.stderr, help="Log file name")
    args = parser.parse_args()
    level = 50 - args.v * 10
    logging.basicConfig(stream=sys.stderr, level=level, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info("Logging level is {}".format(level))
    for fname in args.fname:
        gps_data, sensor_data = read_data_from_zipfile(fname)
        if args.output is None:
            output = os.path.splitext(os.path.basename(fname))[0]
        else:
            output = args.output
        interpolate_position(gps_data, sensor_data, output, limit=args.limit)
