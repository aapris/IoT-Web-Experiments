import numbers
import os
import datetime
import json
import configparser
import argparse
import paho.mqtt.client as mqtt
import influxdb
import pytz

# Tulevaisuuden esine data sample:
# {"chipid":2057786,"sensor":"humitemp","millis":745033031,"data":["humi",52.01392,"temp",23.77477,"_",0]}

# ruuvitag_sensor Python module produces data like this
EXAMPLE_DATA = {
    "F8:C6:12:37:F4:3D": {
        "pressure": 996.34,
        "humidity": 40.5,
        "acceleration_x": -16,
        "temperature": 20.54,
        "acceleration_z": 1004,
        "acceleration": 1004.7726110916838,
        "battery": 2941,
        "acceleration_y": 36
    },
    "E4:F4:86:52:C5:84": {
        "pressure": 995.87,
        "humidity": 40.5,
        "acceleration_x": -24,
        "temperature": 19.85,
        "acceleration_z": 1036,
        "acceleration": 1036.4709354342745,
        "battery": 2905,
        "acceleration_y": 20
    }
}


def get_influxdb_client(host='127.0.0.1', port=8086, database='mydb'):
    iclient = influxdb.InfluxDBClient(host=host, port=port, database=database)
    iclient.create_database(database)
    return iclient


def create_influxdb_obj(dev_id, measurement, fields, timestamp=None, extratags=None):
    # Make sure timestamp is timezone aware and in UTC time
    if timestamp is None:
        timestamp = pytz.UTC.localize(datetime.datetime.utcnow())
    # FIXME: this is django related, check generic version
    # elif timestamp.tzinfo is None or timestamp.tzinfo.utcoffset(timestamp) is None:
    #     timestamp = get_default_timezone().localize(timestamp)
    timestamp = timestamp.astimezone(pytz.UTC)
    for k, v in fields.items():
        fields[k] = float(v)
    measurement = {
        "measurement": measurement,
        "tags": {
            "dev-id": dev_id,
        },
        "time": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),  # is in UTC time
        "fields": fields
    }
    if extratags is not None:
        measurement['tags'].update(extratags)
    return measurement


def on_connect(client, userdata, flags, rc):
    print("Connected with result code {}".format(rc))
    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(client.t)


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    payload = msg.payload.decode('utf-8')
    if msg.retain == 1:
        print("No handle retain message {}".format(payload))
        return
    topic = msg.topic
    if args.verbose > 2:
        print(topic, payload[:50])
    try:
        data = json.loads(payload)
    except json.decoder.JSONDecodeError as e:
        print('JSON ERROR "{}" IN DATA: {}'.format(str(e), payload[:100]))
        return
    except Exception as e:
        print('ERROR "{}" IN DATA: {}'.format(str(e), payload[:100]))
        return
    if isinstance(data, numbers.Number):
        print('Got number?!? {}'.format(data))
        return
    handle_message(topic, data)


def handle_message(topic, data):
    tt = topic.split('/')
    if tt[-1] == 'ruuvitag':
        database = tt[-2] if len(tt) > 1 else 'mydb'
        handle_ruuvitag(topic, data, database)
    elif ('chipid' in data or 'mac' in data) and 'sensor' in data and 'data' in data:
        # database name is the second token in the topic
        database = tt[1] if len(tt) > 1 else 'mydb'
        handle_tulevaisuudenesine(topic, data, database)
    else:
        print("No handle :(")


def handle_tulevaisuudenesine(topic, data, database):
    saved = False
    measurement = '{}'.format(data['sensor'])
    fields = {}
    if isinstance(data['data'], dict):
        fields = data['data']
    if isinstance(data['data'], list):
        it = iter(data['data'])
        for x, y in zip(it, it):
            if x != '_':
                fields[x] = y
    if 'chipid' in data:
        dev_id = str(data['chipid'])
    elif 'mac' in data:
        dev_id = data['mac'].upper()
    else:
        print('No dev_id found!')
        return
    json_body = create_influxdb_obj(dev_id, measurement, fields, timestamp=None, extratags=None)
    if args.verbose > 2:
        print(json.dumps(json_body, indent=2))
    if args.verbose == 2:
        print('{} {} ...'.format(topic, json.dumps(json_body)[:80]))
    if args.dryrun is False:
        iclient = get_influxdb_client(database=database)
        try:
            saved = iclient.write_points([json_body])  # Note []
        except influxdb.exceptions.InfluxDBClientError as err:
            print('ERROR: {}'.format(err))
    if saved is False:
        print('Dryrun: {}, Not saved {}'.format(args.dryrun, json.dumps(data)))


def handle_ruuvitag(topic, data, database):
    iclient = get_influxdb_client(database=database)
    for o in data:
        f = o['fields']
        if 'battery' in f and f['battery'] < 10:  # old version had mV, new V
            f['battery'] = int(f['battery'] * 1000)
            # print("fix battery value")
        for k in ['mac', 'tx_power']:
            if k in f:
                # print("remove {}".format(k))
                del f[k]
    saved = False
    if args.verbose > 2:
        print(json.dumps(data, indent=2))
    if args.verbose == 2:
        print('{} {} ...'.format(topic, json.dumps(data)[:70]))
    if args.dryrun is False:
        saved = iclient.write_points(data)
    if saved is False:
        print('Dryrun: {}, Not saved {}'.format(args.dryrun, json.dumps(data)))


def get_setting(args, arg, config, section, key, envname, default=None):
    # Return command line argument, if it exists
    if args and hasattr(args, arg) and getattr(args, arg) is not None:
        return getattr(args, arg)
    # Return value from config.ini if it exists
    elif section and key and section in config and key in config[section]:
        return config[section][key]
    # Return value from env if it exists
    elif envname:
        return os.environ.get(envname)
    else:
        return default


if __name__ == '__main__':
    # Parse arguments
    parser = argparse.ArgumentParser()
    parser.add_argument('-q', '--quiet', action='store_true', help='Never print a char (except on crash)')
    parser.add_argument('--dryrun', action='store_true', help='Do not really save into InfluxDB')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Print some informative messages')
    parser.add_argument('-t', '--topic', help='MQTT topic – if not set, config.ini\' setting is used')
    parser.add_argument('-D', '--database', help='InfluxDB database name')
    args = parser.parse_args()

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.

    iclient = None
    mclient = None
    config = configparser.ConfigParser()
    dir_path = os.path.dirname(os.path.realpath(__file__))
    config.read(os.path.join(dir_path, 'config.ini'))
    # timeout_in_sec = float(config['DEFAULT']['timeout'])
    # print(get_setting(None, None, config, 'mqtt', 'topic', 'MQTT_TOPIC'))
    # print(get_setting(args, 'topic', config, 'mqtt', 'topic', 'MQTT_TOPIC'))
    mclient = mqtt.Client()
    mclient.username_pw_set(config['mqtt']['username'], config['mqtt']['password'])
    mclient.on_connect = on_connect
    mclient.on_message = on_message
    mclient.connect(config['mqtt']['host'], int(config['mqtt']['port']), 60)
    if args.topic is None:
        mclient.t = args.topic = config['mqtt']['topic']
        print(mclient.t)
    try:
        mclient.loop_forever()
    except KeyboardInterrupt:
        mclient.disconnect()
        print("Good bye")
