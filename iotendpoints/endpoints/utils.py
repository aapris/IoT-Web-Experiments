import os
import re
import datetime
import base64
import influxdb
import pytz
from django.conf import settings
from django.contrib.auth import authenticate
from django.core.exceptions import ImproperlyConfigured
from django.utils import timezone
from .models import Request, Datalogger

META_KEYS = ['QUERY_STRING', 'REMOTE_ADDR', 'REMOTE_HOST', 'REMOTE_USER',
             'REQUEST_METHOD', 'SERVER_NAME', 'SERVER_PORT', 'REQUEST_URI']


def get_datalogger(devid, name='', description='', update_activity=False):
    datalogger, created = Datalogger.objects.get_or_create(devid=devid)
    changed = False
    if created:
        datalogger.description = description
        datalogger.name = name
        changed = True
    if update_activity:
        datalogger.activity_at = timezone.now()
        changed = True
    if changed:
        datalogger.save()
    return datalogger, created


def get_setting(key, default=None):
    """
    Return 'key' from os.environ or Django settings if found or None.
    If key is defined in more than 1 place, raise error.

    :param str key: Setting name
    :return: Setting value
    :raises ImproperlyConfigured: if the key is defined more than once
    """
    from_env = os.environ.get(key, None)
    from_settings = getattr(settings, key, None)
    if from_env and from_settings:
        err_msg = '{} is configured twice: {} in ENV and {} in settings.'.format(key, from_env, from_settings)
        raise ImproperlyConfigured(err_msg)
    else:  # return value or None, if both are None
        val = from_env if from_env else from_settings
        if val is None:
            val = default
        return val


def get_plugins(plugins_dir):
    """
    :param module plugins_dir: Imported module
    :return:
    :rtype: Iterator
    """
    for name in plugins_dir.__all__:
        plugin = getattr(plugins_dir, name)
        try:
            # see if the plugin has a 'Plugin' class
            p = plugin.Plugin()
        except AttributeError:
            # raise an exception, log a message,
            # or just ignore the problem
            raise
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


def create_path(postfix):
    now = timezone.now().astimezone(pytz.utc)
    if postfix:
        path = re.sub("[^a-zA-Z0-9]", "", postfix)
    else:
        path = ''
    path = os.path.join(path, now.strftime('%Y-%m-%d'), now.strftime('%Y%m%dT%H%M%S.%fZ'))
    fpath = os.path.join(settings.MEDIA_ROOT, path)
    os.makedirs(fpath, exist_ok=True)
    return fpath


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
