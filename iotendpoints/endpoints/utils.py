import base64
import influxdb
import datetime
from django.contrib.auth import authenticate


def get_plugins(plugins_dir):
    for name in plugins_dir.__all__:
        plugin = getattr(plugins_dir, name)
        try:
            # see if the plugin has a 'Plugin' class
            p = plugin.Plugin()
        except AttributeError:
            # raise an exception, log a message,
            # or just ignore the problem
            raise
            pass
        yield p


def plugin_urlpatterns(plugins_dir):
    plugins = get_plugins(plugins_dir)
    urlpatterns = []
    for p in plugins:
        register_plugin = p.register
        register_plugin()
        urlpatterns += p.get_urlpatterns()
    return urlpatterns


def basicauth(request):
    """Check for valid basic auth header."""
    uname, passwd, user = None, None, None
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        if len(auth) == 2:
            if auth[0].lower() == "basic":
                a = auth[1].encode('utf8')
                s = base64.b64decode(a)
                uname, passwd = s.decode('utf8').split(':')
                user = authenticate(username=uname, password=passwd)
    return uname, passwd, user


def get_influxdb_client(host='127.0.0.1', port=8086, database='mydb'):
    iclient = influxdb.InfluxDBClient(host=host, port=port, database=database)
    return iclient


def create_influxdb_obj(dev_id, measurement, fields, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.utcnow()
    # TODO: check that timestmap is in UTC timezone and raise value error if it is naïve
    for k, v in fields.items():
        fields[k] = float(v)
    measurement = {
        "measurement": measurement,
        "tags": {
            "dev-id": dev_id,
        },
        "time": timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "fields": fields
    }
    return measurement


class BasePlugin:
    """
    Every plugin must inherit BasePlugin and implement at least get_urlpatterns()
    and a view function, which returns HttpResponse object.
    """

    name = None
    viewname = None
    in_use = False

    def __init__(self):
        if self.name is None or self.viewname is None:
            raise ValueError('self.name or self.viewname must be defined')

    def register(self):
        print('Registering plugin "{}"'.format(self.name))

    def get_urlpatterns(self):
        return []
