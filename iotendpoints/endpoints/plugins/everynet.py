"""
Everynet.io endpoint.

You must declare environment variable EVERYNET_URL to activate this plugin.

"""

import os
import json
import base64
import logging
import datetime
import pytz
import re
import random
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

ENV_NAME = 'EVERYNET_URL'
URL = get_setting(ENV_NAME)
EVERYNET_DB = get_setting('EVERYNET_DB', 'everynet')
logger = logging.getLogger(__name__)


def handle_v1(data):
    pass


def handle_paxcounter(data_str):
    wifi = int.from_bytes(data_str[:2], byteorder='big')
    ble = int.from_bytes(data_str[2:], byteorder='big')
    idata = {'wifi': wifi, 'ble': ble}
    return idata


def handle_keyval(data_str):
    idata = dict(re.findall(r'([^,]+)=(".*?"|[^,]+)', data_str))
    return idata


def invalid_data(data_str, msg, status=400):
    log_msg = '[EVERYNET] Invalid data: "{}". {}.'.format(data_str[:50], msg)
    err_msg = 'Invalid data: "{}"... Hint: {}'.format(data_str[:50], msg)
    logger.error(log_msg)
    return HttpResponse(err_msg, status=status)


class Plugin(BasePlugin):
    """
    Everynet.io plugin. Checks if endpoint's URL has been set in env.
    """
    name = 'everynet'
    viewname = 'everynethandler'

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
        Endpoint requires idcode, sensor and data parameters. Also a valid Django user must exist. Test like this:

        export EVERYNET_URL=everynet
        """
        ok_response = HttpResponse("ok")
        body_data = ''
        if request.method not in ['OPTIONS', 'POST']:
            return HttpResponse('Only OPTIONS, POST methdods are allowed', status=405)
        if request.method == 'OPTIONS':  # FIXME: I don't know is this a correct answer
            return HttpResponse('OK', status=200)
        try:
            body_data = request.body
            data = json.loads(body_data.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as err:
            return invalid_data(body_data, "Hint: should be UTF-8 json.", status=400)
        # meta and type keys should be always in request json
        try:
            device = data['meta']['device']
            times = str(data['meta']['time'])
            packet_type = data['type']
        except KeyError as err:
            err_msg = 'Invalid json structure: "{}". Hint: missing key {}.'.format(body_data, err)
            return invalid_data(body_data, err_msg, status=400)
        now = timezone.now().astimezone(pytz.utc)
        path = os.path.join(settings.MEDIA_ROOT, 'everynet', now.strftime('%Y-%m-%d'), device)
        os.makedirs(path, exist_ok=True)
        fpath = os.path.join(path, now.strftime('%Y%m%dT%H%M%S.%fZ.json'))
        dl_descr = 'everynet'
        if random.randint(0,50) == 10:  # Save 1/50 of packages for debugging purposes
            with open(fpath, 'wt') as destination:
                destination.write(json.dumps(data, indent=1))
                dump_request(request, postfix='everynet')
        if packet_type == 'error':
            logger.warning('[EVERYNET]: Got error msg, check {} for details.'.format(fpath))
            return ok_response
        elif packet_type == 'uplink':
            payload = data['params']['payload'].encode()
            _type = request.GET.get('type')
            if _type == 'paxcounter':
                data_str = base64.decodebytes(payload)
                idata = handle_paxcounter(data_str)
                keys_str = 'wifi-ble'
                dl_descr = 'paxcounter'
            elif _type == 'keyval':  # data should be key=val,key2=val2,... formatted
                data_str = base64.decodebytes(payload).decode('utf8')
                print(data_str, type(data_str))
                idata = handle_keyval(data_str)
                try:  # convert values to floats in dict
                    idata = {k: float(v) for k, v in idata.items()}
                except ValueError as err:
                    err_msg = 'Should be base64 encoded key=val pairs, comma separated.'.format(data_str[:50])
                    return invalid_data(data_str, err_msg, status=400)
                print(idata)
                keys = list(idata.keys())
                keys.sort()
                if len(keys) == 0:
                    err_msg = 'Should be base64 encoded key=val pairs, comma separated.'
                    # NOTE: from everynet's point of view this is not error.
                    return invalid_data(data_str, err_msg, status=200)

                keys_str = '_'.join(keys)
                dl_descr = 'keyval'
            else:
                data_str = base64.decodebytes(payload).decode('utf8')
                handle_v1(data_str)  # TODO
                try:
                    sensordata = json.loads(data_str)
                    if not isinstance(sensordata, dict):
                        err_msg = '[EVERYNET] payload is not json: {}'.format(data_str)
                        logger.warning(err_msg)
                        return HttpResponse("OK: dumped data to a file.")
                except (ValueError) as err:
                    return invalid_data(data_str, "Hint: should be UTF-8 json.", status=400)
                if 'id' in sensordata and 'sensor' in sensordata:
                    keys = list(sensordata['data'].keys())
                    idata = sensordata['data']
                    pass
                else:  # old method
                    keys = list(sensordata.keys())
                    idata = sensordata
                keys.sort()
                keys_str = '-'.join(keys)
            datalogger, created = get_datalogger(device, description=dl_descr, update_activity=True)
            # TODO: log new devices (created == True), maybe send email to admin?
            ts = datetime.datetime.utcfromtimestamp(data['meta']['time'])
            ts = pytz.UTC.localize(ts)  # Make timestamp timezone aware at UTC
            measurement = create_influxdb_obj(device, keys_str, idata, ts)
            measurements = [measurement]
            dbname = request.GET.get('db')
            if dbname is None:
                dbname = EVERYNET_DB
            iclient = get_influxdb_client(database=dbname)
            iclient.create_database(dbname)
            try:
                iclient.write_points(measurements)
                response = HttpResponse("ok")
            except InfluxDBClientError as err:
                err_msg = '[EVERYNET] InfluxDB error: {}'.format(err)
                logger.error(err_msg)
                response = HttpResponse(err_msg, status=500)
            return response
        else:
            err_msg = '[EVERYNET] Unknown packet type {}'.format(packet_type)
            logger.warning(err_msg)
        return ok_response
