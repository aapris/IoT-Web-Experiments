"""
Digita endpoint.

You must declare environment variable DIGITA_URL to activate this plugin.

"""

import os
import json
import logging
import binascii
import dateutil
import pytz
from django.conf import settings
from django.conf.urls import url
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from influxdb.exceptions import InfluxDBClientError
from endpoints.utils import BasePlugin
from endpoints.utils import get_influxdb_client, create_influxdb_obj
from endpoints.utils import get_setting, get_datalogger
from endpoints.views import dump_request

ENV_NAME = 'DIGITA_URL'
URL = get_setting(ENV_NAME)
DIGITA_DB = get_setting('DIGITA_DB', 'digita')
logger = logging.getLogger(__name__)


def hex2int(hex_str):
    """
    Convert 2 hex characters (e.g. "23") to int (35)
    :param hex_str: hex character string
    :return: int integer
    """
    return int(hex_str, 16)


def calc_temp(hex_str):
    """
    Convert 4 hex characters (e.g. "040b") to float temp (25.824175824175825)
    :param hex_str: hex character string
    :return: float temperature
    """
    adc = int(hex_str[0:2], 16) * 256 + int(hex_str[2:4], 16)
    temp = (300 * adc / 4095) - 50
    return temp


def calc_volts(hex_str):
    """
    Convert 2 hex characters (e.g. "fe") to float volts (3.5043478260869567)
    :param hex_str: hex character string
    :return: float volts
    """
    volts = ((int(hex_str, 16) / 0.23) + 2400) / 1000
    return volts


def handle_clickey_tempsens(hex_str):
    temp1 = calc_temp(hex_str[2:6])
    temp2 = calc_temp(hex_str[6:10])
    volts = calc_volts(hex_str[10:12])
    return {
        'temp1': temp1,
        'temp2': temp2,
        'volt': volts
    }


def hex2value10(hex_str):
    return hex2int(hex_str) / 10.0


def handle_aqburk(hex_str):
    """
    Parse payload like "2a2a0021002c002800300056003b0000" float values
    :param hex_str: AQLoRaBurk hex payload
    :return: dict containing float values
    """
    return {
        'pm25min': hex2value10(hex_str[4:8]),
        'pm25max': hex2value10(hex_str[8:12]),
        'pm25avg': hex2value10(hex_str[12:16]),
        'pm25med': hex2value10(hex_str[16:20]),
        'pm10min': hex2value10(hex_str[20:24]),
        'pm10max': hex2value10(hex_str[24:28]),
        'pm10avg': hex2value10(hex_str[28:32]),
        'pm10med': hex2value10(hex_str[32:36]),
    }


def handle_keyval(hex_str):
    """
    :param hex_str: key-value hex payload
    :return: dict containing parsed balues
    :raises UnicodeDecodeError: if hex_str contains illegal bytes for utf8
    """
    _str = binascii.unhexlify(hex_str)  # --> b'temp=24.61,hum=28.69'
    _str = _str.decode()  # --> 'temp=24.61,hum=28.69'
    keyvals = [x.split('=') for x in _str.split(',')]  # --> [['temp', '24.61'], ['hum', '28.69']]
    keyvals = [[x[0], float(x[1])] for x in keyvals]  # --> [['temp', 24.61], ['hum', 28.69]]
    data = dict(keyvals)  # --> {'temp': 24.61, 'hum': 28.69}
    return data


class Plugin(BasePlugin):
    """
    Digita plugin. Checks if endpoint's URL has been set in env.
    """
    name = 'digita'
    viewname = 'digitahandler'

    def __init__(self):
        """Check that `ENV_NAME` is in env variables."""
        super().__init__()
        if URL is not None:
            self.in_use = True

    def register(self):
        print('Registering plugin "{}"'.format(self.name))

    def get_urlpatterns(self):
        if self.in_use is False:
            print('{} environment variable is not set. {} endpoint is not in use.'.format(ENV_NAME, self.name))
            urlpatterns = []
        else:
            url_pattern = r'^{}$'.format(URL)
            urlpatterns = [
                url(url_pattern, self.view_func, name=self.viewname),
            ]
        return urlpatterns

    @csrf_exempt
    def view_func(self, request):
        """
        Endpoint requires valid Digita formatted JSON payload.
        """
        err_msg = ''
        status = 200
        try:
            body_data = request.body
            data = json.loads(body_data.decode('utf-8'))
        except (json.decoder.JSONDecodeError, UnicodeDecodeError) as err:
            log_msg = '[DIGITA] Invalid data: "{}". Hint: should be UTF-8 json.'.format(body_data[:50])
            err_msg = 'Invalid data: "{}"... Hint: should be UTF-8 json.'.format(body_data[:50])
            logger.error(log_msg)
            return HttpResponse(err_msg, status=400)
        # meta and type keys should be always in request json
        try:
            d = data['DevEUI_uplink']
            device = d['DevEUI']
            times = str(d['Time'])
            rssi = d['LrrRSSI']
            payload_hex = d['payload_hex']
        except KeyError as err:
            log_msg = '[DIGITA] Invalid json structure: "{}". Missing key: {}.'.format(body_data, err)
            err_msg = 'Invalid json structure: "{}". Hint: missing key {}.'.format(body_data, err)
            logger.error(log_msg)
            return HttpResponse(err_msg, status=400)
        now = timezone.now().astimezone(pytz.utc)
        path = os.path.join(settings.MEDIA_ROOT, 'digita', now.strftime('%Y-%m-%d'), device)
        os.makedirs(path, exist_ok=True)
        fpath = os.path.join(path, now.strftime('%Y%m%dT%H%M%S.%fZ.json'))
        with open(fpath, 'wt') as destination:
            destination.write(json.dumps(data, indent=1))
        response = HttpResponse("ok")
        # TODO: move this to a function
        if len(payload_hex) == 8:
            idata = {
                'wifi': int(payload_hex[0:4], 16),
                'ble': int(payload_hex[4:8], 16)
            }
            idata['rssi'] = rssi
            keys_str = 'wifi-ble'
            dl_descr = 'paxcounter'
            datalogger, created = get_datalogger(device, description=dl_descr, update_activity=True)
            ts = dateutil.parser.parse(times)
            measurement = create_influxdb_obj(device, keys_str, idata, ts)
            measurements = [measurement]
            # dbname = request.GET.get('db', DIGITA_DB)
            dbname = 'paxcounter'
            iclient = get_influxdb_client(database=dbname)
            iclient.create_database(dbname)
            try:
                iclient.write_points(measurements)
            except InfluxDBClientError as err:
                err_msg = '[DIGITA] InfluxDB error: {}'.format(err)
                status = 500
        elif payload_hex[:2] == '13':
            idata = handle_clickey_tempsens(payload_hex)
            idata['rssi'] = rssi
            keys_str = 'tempsens'
            datalogger, created = get_datalogger(device, description='Clickey Tempsens PRO', update_activity=True)
            ts = dateutil.parser.parse(times)
            measurement = create_influxdb_obj(device, keys_str, idata, ts)
            measurements = [measurement]
            # dbname = request.GET.get('db', DIGITA_DB)
            dbname = 'digita'
            iclient = get_influxdb_client(database=dbname)
            iclient.create_database(dbname)
            try:
                iclient.write_points(measurements)
            except InfluxDBClientError as err:
                err_msg = '[DIGITA] InfluxDB error: {}'.format(err)
                status = 500
        elif payload_hex[:4].lower() == '2a2a':
            idata = handle_aqburk(payload_hex)
            idata['rssi'] = rssi
            keys_str = 'aqburk'
            datalogger, created = get_datalogger(device, description='FVH AQ burk', update_activity=True)
            ts = dateutil.parser.parse(times)
            measurement = create_influxdb_obj(device, keys_str, idata, ts)
            measurements = [measurement]
            DIGITA_DB = 'aqburk'
            dbname = request.GET.get('db', DIGITA_DB)
            iclient = get_influxdb_client(database=dbname)
            iclient.create_database(dbname)
            try:
                iclient.write_points(measurements)
            except InfluxDBClientError as err:
                err_msg = '[DIGITA] InfluxDB error: {}'.format(err)
                status = 500
        elif len(payload_hex) >= 2:  # Assume we have key-val data
            try:
                idata = handle_keyval(payload_hex)
            except (UnicodeDecodeError, IndexError) as err:
                err_msg = '[DIGITA] Payload error: {}'.format(err)
                status = 400
                logger.error(err_msg)
                dump_request(request, postfix='digita')
                response = HttpResponse(err_msg, status=status)
                return response
            idata['rssi'] = rssi
            ikeys = list(idata.keys())
            ikeys.sort()
            keys_str = '_'.join(ikeys)
            datalogger, created = get_datalogger(device, description='LoRaWAN device', update_activity=True)
            ts = dateutil.parser.parse(times)
            measurement = create_influxdb_obj(device, keys_str, idata, ts)
            measurements = [measurement]
            # dbname = request.GET.get('db', DIGITA_DB)
            dbname = 'digita'
            iclient = get_influxdb_client(database=dbname)
            iclient.create_database(dbname)
            try:
                iclient.write_points(measurements)
            except InfluxDBClientError as err:
                err_msg = '[DIGITA] InfluxDB error: {}'.format(err)
                status = 500
        else:
            err_msg = '[DIGITA] Not handled'
        if err_msg != '':
            logger.error(err_msg)
            dump_request(request, postfix='digita')
            response = HttpResponse(err_msg, status=status)
        return response
