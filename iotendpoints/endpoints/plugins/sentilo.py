"""
Sentilo / CESVA TA120 endpoint.

You must declare environment variable SENTILO_URL to activate this plugin.

Example PUT payload:

```
{"sensors":[
 {
  "sensor":"TA120-T246177-N",
  "observations":[
   {"value":"45.4", "timestamp":"02/01/2018T11:22:59UTC"}
  ]
 },{
  "sensor":"TA120-T246177-O",
  "observations":[
   {"value":"false", "timestamp":"02/01/2018T11:22:59UTC"}
  ]
 },{
  "sensor":"TA120-T246177-U",
  "observations":[
   {"value":"false", "timestamp":"02/01/2018T11:22:59UTC"}
  ]
 },{
  "sensor":"TA120-T246177-M",
  "observations":[
   {"value":"100", "timestamp":"02/01/2018T11:22:59UTC"}
  ]
 },{
  "sensor":"TA120-T246177-S",
  "observations":[
   {"value":"044.0,0,0;043.9,0,0;044.2,0,0;044.0,0,0;043.8,0,0;043.9,0,0;044.5,0,0;044.2,0,0;043.8,0,0;044.2,0,0;044.5,0,0;044.7,0,0;044.4,0,0;044.8,0,0;044.2,0,0;045.3,0,0;046.1,0,0;046.5,0,0;046.6,0,0;046.1,0,0;046.3,0,0;046.7,0,0;048.1,0,0;048.5,0,0;048.4,0,0;049.7,0,0;051.6,0,0;047.8,0,0;047.7,0,0;046.7,0,0;046.0,0,0;044.9,0,0;043.9,0,0;043.5,0,0;043.1,0,0;042.5,0,0;043.8,0,0;043.5,0,0;043.4,0,0;043.4,0,0;042.9,0,0;045.2,0,0;043.0,0,0;044.2,0,0;043.4,0,0;044.3,0,0;044.1,0,0;043.2,0,0;043.6,0,0;042.9,0,0;043.1,0,0;043.9,0,0;044.2,0,0;044.1,0,0;048.0,0,0;043.7,0,0;042.9,0,0;048.0,0,0;044.4,0,0;044.5,0,0", "timestamp":"02/01/2018T11:22:59UTC"}
  ]
 }
]}
```

"""
import datetime
import json
import logging

from dateutil.parser import parse
from django.conf.urls import url
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from influxdb.exceptions import InfluxDBClientError
from endpoints.utils import BasePlugin
from endpoints.utils import basicauth, get_influxdb_client, create_influxdb_obj
from endpoints.utils import get_setting, get_datalogger
from endpoints.tasks import save_to_influxdb, push_ngsi_orion

ENV_NAME = 'SENTILO_URL'
URL = get_setting(ENV_NAME)
SENTILO_DB = get_setting('SENTILO_DB', 'sentilo')
logger = logging.getLogger(__name__)

ORION_URL_ROOT = get_setting('ORION_URL_ROOT')
ORION_USERNAME = get_setting('ORION_USERNAME')
ORION_PASSWORD = get_setting('ORION_PASSWORD')


def parse_sentilo_data(data):
    measurements = []
    for item in data['sensors']:
        ts_str = item['observations'][0].get('timestamp')
        if ts_str is not None:
            ts = parse(item['observations'][0]['timestamp'], dayfirst=True)
        else:
            ts = datetime.datetime.utcnow()
            print(ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ data without timestamp!"))
        dev_id = item['sensor'][0:-2]
        if item['sensor'].endswith('N'):
            fields = {'dBA': float(item['observations'][0]['value'])}
            measurement = create_influxdb_obj(dev_id, 'LAeq', fields, timestamp=ts)
            measurements.append(measurement)
        if item['sensor'].endswith('S'):
            cnt = 0
            secvals = item['observations'][0]['value'].split(';')
            secvals.reverse()
            for val in secvals:
                fields = {'dBA': float(val.split(',')[0])}
                measurement = create_influxdb_obj(dev_id, 'LAeq1s', fields,
                                                  timestamp=(ts - datetime.timedelta(seconds=cnt)))
                cnt += 1
                measurements.append(measurement)
    return measurements


def parse_sentilo2ngsi(data, lat=None, lon=None):
    device_id = data['sensors'][0]['sensor'][:-2]  # all list items _should_ have same ID
    obs_type = 'NoiseLevelObserved'
    location = {
        "type": "Point",
        "coordinates": [lon, lat]
    }
    # address = ""
    sonometer_class = "1"
    date_observed = None
    measurand = None
    laeq = lamax = laeq1s = date_observed_from = date_observed_to = None
    for m in data['sensors']:  # iterate to find LAeq aka "N" among params reported by sensor
        # print(m)
        if 'N' in m['sensor'][-1]:
            ts = parse(m['observations'][0]['timestamp'], dayfirst=True)
            date_observed_from = (ts - datetime.timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            date_observed_to = ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            laeq = float(m['observations'][0]['value'])
            measurand = "{} | {} | {}".format("LAeq", laeq, "A-weighted, equivalent, sound level")
        if 'S' in m['sensor'][-1]:
            laeq1s = m['observations'][0]['value']
            lamax = max([float(x.split(',')[0]) for x in laeq1s.split(';')])
    if laeq:
        _id = device_id
        noise_level = {
            "id": device_id,
            "type": "NoiseLevelObserved",
            "LAeq": laeq,
            "dateObservedFrom": date_observed_from,
            "dateObservedTo": date_observed_to,
            "measurand": [measurand],
            "sonometerClass": sonometer_class,
            "location": location
        }
        if lamax:
            noise_level["LAmax"] = lamax
        return noise_level
    return None


class Plugin(BasePlugin):
    """
    Sentilo plugin. Checks if endpoint's URL has been set in env.
    """
    name = 'sentilo'
    viewname = 'sentilohandler'

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

        export SENTILO_URL=sentilo
        http -v PUT http://127.0.0.1:8000/sentilo < sentilo_packet.json
        """
        rawbody = request.body.decode('utf-8')
        try:
            data = json.loads(request.body.decode('utf-8'))
        except ValueError as err:
            print(str(err))
            with open('/tmp/sentiloraw.log', 'at') as f:
                import datetime
                f.write(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ") + ' SERVER ERROR with data\n')
                f.write(rawbody)
            raise
        with open('/tmp/sentilodata.log', 'at') as f:
            f.write(json.dumps(data, indent=1) + '\n')
        measurements = parse_sentilo_data(data)
        device_id = data['sensors'][0]['sensor'][:-2]  # all list items _should_ have same ID
        datalogger, created = get_datalogger(device_id, description='sentilo', update_activity=True)
        # lat = lon = None
        if datalogger.location:
            lon, lat = datalogger.location.coords  # Note lon, lat order
        else:
            lat = datalogger.lat
            lon = datalogger.lon
        # print(json.dumps(measurement, indent=1)); print(data)
        dbname = SENTILO_DB
        try:
            save_to_influxdb.delay(dbname, measurements)
        except Exception as err:
            logger.error(err)
        ngsi_json = parse_sentilo2ngsi(data, lat, lon)
        # print(json.dumps(ngsi_json, indent=2))
        # TODO: this should be dynamic and configurable per sensor
        push_ngsi_orion.delay(ngsi_json, ORION_URL_ROOT, ORION_USERNAME, ORION_PASSWORD)
        response = HttpResponse("ok")
        return response
