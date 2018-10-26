"""
PLATECAMERA endpoint.

You must declare environment variable PLATECAMERA_URL to activate this plugin.

If you are running development server (`python manage.py runserver`), you can
`export PLATECAMERA_URL=path_without_leading_slash`
before starting runserver.

If you use supervisord to keep gunicorn or similar running, you can add line
`environment = PLATECAMERA_URL=path_without_leading_slash` in your superisor/site.conf.

Raw gunicorn seems to accept `--env PLATECAMERA_URL=path_without_leading_slash` command line argument.
"""
import json
import logging
import os
from dateutil.parser import parse
from django.conf.urls import url
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from influxdb.exceptions import InfluxDBClientError
from endpoints.utils import BasePlugin
from endpoints.utils import get_influxdb_client, create_influxdb_obj
from endpoints.utils import get_setting
from endpoints.views import dump_request
from endpoints.models import Plate

ENV_NAME = 'PLATECAMERA_URL'
URL = get_setting(ENV_NAME)
logger = logging.getLogger(__name__)


def invalid_data(data_str, msg, status=400):
    log_msg = '[EVERYNET] Invalid data: "{}". {}.'.format(data_str[:50], msg)
    err_msg = 'Invalid data: "{}"... Hint: {}'.format(data_str[:50], msg)
    logger.error(log_msg)
    return HttpResponse(err_msg, status=status)


class Plugin(BasePlugin):
    """
    Example plugin. Checks if endpoint's URL has been set in env.
    """
    name = 'PLATECAMERA'
    viewname = 'platecamerahandler'

    def __init__(self):
        """Check that `ENV_NAME` is in env variables."""
        super().__init__()
        if URL is not None:
            self.in_use = True

    def register(self):
        print('Registering plugin "{}"'.format(self.name))

    def get_urlpatterns(self):
        if self.in_use is False:
            print('{} environment variable is not set. PLATECAMERA endpoint is not in use.'.format(ENV_NAME))
            urlpatterns = []
        else:
            url_pattern = r'^{}$'.format(URL)
            urlpatterns = [
                url(url_pattern, self.view_func, name=self.viewname),
            ]
        return urlpatterns

    @csrf_exempt
    def view_func(self, request):
        res = dump_request(request, postfix='democam')
        ok_response = HttpResponse("ok")
        body_data = ''
        if request.method not in ['POST']:
            return HttpResponse('Only POST methdod is allowed', status=405)
        try:
            body_data = request.body
            data = json.loads(body_data.decode('utf-8'))
        except (ValueError, UnicodeDecodeError) as err:
            return invalid_data(body_data, "Hint: should be UTF-8 json.", status=400)
        # Validate data
        for k in ["plate", "date", "country", "confidence", "ip", "direction"]:
            if k not in data.keys():
                return invalid_data(body_data, "Hint: key '{}' is missing.".format(k), status=400)
        timestamp = parse(data['date'])
        plate = Plate(
            plate=data['plate'],
            timestamp=timestamp,
            country=data['country'],
            confidence=float(data['confidence']),
            ip=data['ip'],
            direction=int(data['direction'])
        )
        plate.save()
        idata = {'vehicle': 1}
        measurement = create_influxdb_obj('001', 'cnt', idata, timestamp)
        measurements = [measurement]
        dbname = 'vehicle'
        iclient = get_influxdb_client(database=dbname)
        iclient.create_database(dbname)
        try:
            iclient.write_points(measurements)
            response = HttpResponse("OK")
        except InfluxDBClientError as err:
            err_msg = '[EVERYNET] InfluxDB error: {}'.format(err)
            logger.error(err_msg)
            response = HttpResponse(err_msg, status=500)
        return response
