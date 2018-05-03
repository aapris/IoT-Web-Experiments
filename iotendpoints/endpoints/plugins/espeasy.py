"""
ESP Easy endpoint.

You must declare environment variable ESPEASY_URL to activate this plugin.

ESP Easy settings

HTTP Header field (no new line or whitespace after last '%'!):
```
Content-Type: application/x-www-form-urlencoded
X-Local-IP: %ip%
X-Uptime: %uptime%
X-Sysload: %sysload%
```

HTTP Body field
```
idcode=%sysname%&sensor=%tskname%&id=%id%&data=%1%%vname1%=%val1%%/1%%2%,%vname2%=%val2%%/2%%3%,%vname3%=%val3%%/3%%4%%vname4%=%val4%%/4%
```

"""

import os
import logging
from django.conf.urls import url
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from influxdb.exceptions import InfluxDBClientError
from endpoints.utils import BasePlugin
from endpoints.utils import basicauth, get_influxdb_client, create_influxdb_obj
from endpoints.utils import get_setting
from endpoints.tasks import save_to_influxdb

ENV_NAME = 'ESPEASY_URL'
URL = get_setting(ENV_NAME)
ESP_EASY_DB = get_setting('ESP_EASY_DB', 'espeasy')
logger = logging.getLogger(__name__)


class Plugin(BasePlugin):
    """
    Esp Easy plugin. Checks if endpoint's URL has been set in env.
    """
    name = 'espeasy'
    viewname = 'espeasyhandler'

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

        export ESPEASY_URL=esp
        echo -n "idcode=unique_id_here&sensor=bme280&id=0&data=Temperature=24.84,Humidity=52.05,Pressure=1002.50" | \
           http -v --auth user:pass --form POST http://127.0.0.1:8000/esp
        """
        uname, passwd, user = basicauth(request)
        p = request.POST
        if user is None:
            return HttpResponse("Authentication failure", status=401)
        idcode = p.get('idcode')
        sensor = p.get('sensor')
        data = p.get('data')
        # Reject request if required variables are not set
        if None in [idcode, sensor, data]:
            err_msg = '[ESPEASY] idcode, sensor and/or data is missing in request form data'
            logger.error(err_msg)
            return HttpResponse(err_msg, status=400)
        data = data.strip()
        # Reject request if data is not comma separated key=value pairs or value is not float
        try:
            fields = dict([tuple(x.split('=')) for x in data.split(',')])
            for k in fields.keys():
                fields[k] = float(fields[k])
        except ValueError as err:
            err_msg = '[ESPEASY] data error: {}. Hint: data was "{}".'.format(err, data)
            logger.error(err_msg)
            response = HttpResponse(err_msg, status=400)
            return response
        measurement = create_influxdb_obj(idcode, sensor, fields)
        measurements = [measurement]
        # import json; print(json.dumps(measurement, indent=1)); print(data)
        dbname = uname  # Use username as database name
        try:
            save_to_influxdb.delay(dbname, measurements)
        except Exception as err:
            logger.error(err)
            raise
        # iclient = get_influxdb_client(database=dbname)
        # try:
        #     iclient.create_database(dbname)
        #     iclient.write_points(measurements)
        #     response = HttpResponse("ok")
        # except InfluxDBClientError as err:
        #     err_msg = '[ESPEASY] InfluxDB error: {}'.format(err)
        #     logger.error(err_msg)
        #     response = HttpResponse(err_msg, status=500)
        response = HttpResponse("ok")
        return response
