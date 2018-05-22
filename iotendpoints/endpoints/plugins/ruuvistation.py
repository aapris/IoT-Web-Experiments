"""
Ruuvi Station endpoint.

You must declare environment variable RUUVISTATION_URL to activate this plugin.
"""

import json
import dateutil.parser
import logging
from django.conf.urls import url
from django.http import HttpResponse
from django.utils.timezone import get_default_timezone
from django.views.decorators.csrf import csrf_exempt
from endpoints.utils import BasePlugin
from endpoints.utils import basicauth, create_influxdb_obj
from endpoints.utils import get_setting
from endpoints.tasks import save_to_influxdb

ENV_NAME = 'RUUVISTATION_URL'
URL = get_setting(ENV_NAME)
RUUVISTATION_DB = get_setting('RUUVISTATION_DB', 'ruuvistation')
logger = logging.getLogger(__name__)

to_save = [
    "rssi", "voltage",
    "accelY", "accelZ", "accelX",
    "temperature", "pressure", "humidity",
    "movementCounter", "defaultBackground",
]


def parse_tag_data(data):
    measurements = []
    for tag in data['tags']:
        ts = dateutil.parser.parse(tag['updateAt'])
        if ts.tzinfo is None or ts.tzinfo.utcoffset(ts) is None:
            ts = get_default_timezone().localize(ts)
        dev_id = tag['id']
        extratags = {'name': tag['name']}
        fields = {}
        for key in to_save:
            fields[key] = tag.get(key)
        measurement = create_influxdb_obj(dev_id, 'ruuvitag', fields, timestamp=ts, extratags=extratags)
        measurements.append(measurement)
        print(measurements)
    return measurements


class Plugin(BasePlugin):
    """
    Ruuvi Station plugin. Checks if endpoint's URL has been set in env.
    """
    name = 'ruuvistation'
    viewname = 'ruuvistationhandler'

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
        Test like this:

        export RUUVISTATION_URL=ruuvistation
        echo -n '{"deviceId":"a9e3f766-b2e6-44a5-aba0-8aab09662938","eventId":"0d0388cb-7134-411a-a8aa-eef04d85fa65",
        "tags":[{"id":"ED:20:D0:FE:B0:9B","name":"vetari 2","rawDataBlob":
        {"blob":[2,1,6,17,-1,-103,4,3,73,23,39,-52,-87,-1,-2,0,3,3,-13,12,121,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},
        "updateAt":"May 22, 2018 7:16:31 PM","accelX":-0.002,"accelY":0.002,"accelZ":1.006,"humidity":83.0,"pressure":1018.36,
        "temperature":5.18,"txPower":0.0,"voltage":3.163,"dataFormat":3,"defaultBackground":4,"favorite":true,
        "measurementSequenceNumber":0,"movementCounter":0,"rssi":-70}],"time":"May 22, 2018 7:16:31 PM"}' | \
           http -v --auth user:djangouser --form POST http://127.0.0.1:8000/ruuvistation
        """
        uname, passwd, user = basicauth(request)
        body_data = ''
        # Reject request if required variables are not set
        if user is None:
            pass
            # TODO: log error
            # return HttpResponse("Authentication failure", status=401)
        try:
            body_data = request.body
            data = json.loads(body_data.decode('utf-8'))
        except (json.decoder.JSONDecodeError, UnicodeDecodeError) as err:
            log_msg = '[RUUVISTATION] Invalid data: "{}". Hint: should be UTF-8 json.'.format(body_data[:50])
            err_msg = 'Invalid data: "{}"... Hint: should be UTF-8 json.'.format(body_data[:50])
            logger.error(log_msg)
            return HttpResponse(err_msg, status=400)
        measurements = parse_tag_data(data)
        dbname = request.GET.get('db', RUUVISTATION_DB)
        try:
            save_to_influxdb.delay(dbname, measurements)
        except Exception as err:
            logger.error(err)
        response = HttpResponse("ok")
        return response
