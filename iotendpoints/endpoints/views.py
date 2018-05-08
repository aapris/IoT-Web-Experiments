import datetime
import json
import os
import re
import pytz
import base64
import influxdb
import requests
from dateutil.parser import parse
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.contrib.auth import authenticate
from .models import Request

META_KEYS = ['QUERY_STRING', 'REMOTE_ADDR', 'REMOTE_HOST', 'REMOTE_USER',
             'REQUEST_METHOD', 'SERVER_NAME', 'SERVER_PORT', 'REQUEST_URI']

ORION_URL_ROOT = os.environ.get('ORION_URL_ROOT')
ORION_USERNAME = os.environ.get('ORION_USERNAME')
ORION_PASSWORD = os.environ.get('ORION_PASSWORD')


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


def create_influxdb_obj(dev_id, measurement, fields, timestamp=None):
    if timestamp is None:
        timestamp = datetime.datetime.utcnow()
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


def index(request):
    return HttpResponse("Hello, world. This is IoT endpoint.")


def dump_request(request, user=None, postfix=None):
    """
    Dump a HttpRequest to files in a directory.
    """
    r = Request(method=request.method, user=user)
    fpath = create_path(postfix)
    fname = os.path.join(fpath, 'request_body.txt')
    with open(fname, 'wb') as destination:
        destination.write(request.body)
    res = []
    res.append('Request Method: {}'.format(request.method))
    res.append('Request full path: {}'.format(request.get_full_path()))

    res.append('--- GET parameters ---')
    for key, val in request.GET.items():
        res.append('{}={}'.format(key, val))

    res.append('--- POST parameters ---')
    for key, val in request.POST.items():
        res.append('{}={}'.format(key, val))

    res.append('--- META parameters ---')
    for key, val in request.META.items():
        if key.startswith('HTTP_') or key.startswith('CONTENT_') or key in META_KEYS:
            res.append('{}={}'.format(key, val))

    res.append('--- FILES ---')

    fnr = 0
    for key, val in request.FILES.items():
        res.append('{}. {}={}'.format(fnr, key, val))
        fnr += 1
        f = request.FILES[key]
        res.append('content_type={}'.format(f.content_type))
        res.append('size={}B'.format(f.size))
        fname = os.path.join(fpath, '{}'.format(val))
        res.append('path={}'.format(fname))
        with open(fname, 'wb+') as destination:
            for chunk in f.chunks():
                destination.write(chunk)
    r.filecount = fnr
    r.save()
    fname = os.path.join(fpath, 'request_headers.txt')
    with open(fname, 'wt+') as destination:
        destination.write('\n'.join(res))
    return res


@csrf_exempt
def obscure_dump_request_endpoint(request, postfix):
    """
    Dump a HttpRequest to files in a directory.
    """
    res = dump_request(request, postfix=postfix)
    print('\n'.join(res))  # to console or stdout/stderr
    return HttpResponse("OK, I dumped HTTP request data to a file.")


@csrf_exempt
def digita_dump_request_endpoint(request):
    """
    Dump a HttpRequest to files in a directory.
    """
    res = dump_request(request, postfix='digita')
    print('\n'.join(res))  # to console or stdout/stderr
    return HttpResponse("OK, I dumped Digita LoRa HTTP request data to a file.")


@csrf_exempt
def sentilo_dump_request_endpoint(request):
    """
    Dump a HttpRequest to files in a directory.
    """
    res = dump_request(request, postfix='sentilo')
    print('\n'.join(res))  # to console or stdout/stderr
    return HttpResponse("OK, I dumped Sentilo HTTP request data to a file.")


def _basicauth(request):
    # Check for valid basic auth header
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


@csrf_exempt
def basicauth_dump_request_endpoint(request):
    """
    Dump a HttpRequest to files in a directory.
    """
    uname, passwd, user = _basicauth(request)
    print(uname, passwd, user)

    if user is None:
        # Either they did not provide an authorization header or
        # something in the authorization attempt failed. Send a 401
        # back to them to ask them to authenticate.
        response = HttpResponse('<h1>401 Unauthorized</h1> You need a valid user account '
                                '(username and password) to access this page.')
        response.status_code = 401
        BASIC_AUTH_REALM = 'test'
        response['WWW-Authenticate'] = 'Basic realm="{}"'.format(BASIC_AUTH_REALM)
        return response
    else:
        res = dump_request(request, user=user)
        print('\n'.join(res))
        return HttpResponse("OK, I dumped HTTP request data to a file.")


@csrf_exempt
def aqtest(request):
    """
    Dump a HttpRequest to files in a directory.
    """
    uname, passwd, user = _basicauth(request)

    if user is None:
        # Either they did not provide an authorization header or
        # something in the authorization attempt failed. Send a 401
        # back to them to ask them to authenticate.
        response = HttpResponse('<h1>401 Unauthorized</h1> You need a valid user account '
                                '(username and password) to access this page.')
        response.status_code = 401
        BASIC_AUTH_REALM = 'test'
        response['WWW-Authenticate'] = 'Basic realm="{}"'.format(BASIC_AUTH_REALM)
        return response
    else:
        res = dump_request(request)
        print('\n'.join(res))
        return HttpResponse("OK, I dumped HTTP request data to a file.")


def get_iclient(host='127.0.0.1', port=8086, database='mydb'):
    # using Http
    iclient = influxdb.InfluxDBClient(host=host, port=port, database=database)
    return iclient


@csrf_exempt
def fmiaqhandler(request, version='0.0.0'):
    """
    echo -n "sensor=fmi_pm&idcode=fmiburk_001&data=pm2_5%3D0.54%2Cpm2_5_10%3D0.00%2Cair_temp%3D22.79%2Cair_humi%3D24.36%2Ccase_temp%3D26.66" | \
       http -v --auth user:pass --form POST http://127.0.0.1:8000/fmiaq/v1
    """
    uname, passwd, user = _basicauth(request)
    p = request.POST
    if user is None:
        return HttpResponse("Authentication failure", status=401)
    idcode = p.get('idcode')
    sensor = p.get('sensor')
    data = p.get('data')
    if None in [idcode, sensor, data]:
        return HttpResponse("idcode, sensor and/or data is missing in request form data", status=400)
    meas = 'fmiburk'
    json_body = [
        {
            "measurement": meas,
            "tags": {
                "dev-id": p['idcode'],
                # "sensor": p['sensor'],
            },
            "time": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "fields": {}
        }
    ]
    data = p.get('data', '').strip()
    a = dict([tuple(x.split('=')) for x in data.split(',')])
    for k in a.keys():
        a[k] = float(a[k])
    json_body[0]['fields'] = a
    # import json; print(json.dumps(json_body, indent=1)); print(data)
    try:
        iclient = get_iclient(database='airquality')
        iclient.write_points(json_body)
    except influxdb.exceptions.InfluxDBClientError as err:
        print(str(err))
        return HttpResponse(str(err), status=500)
    response = HttpResponse("ok")
    return response


def parse_sentilo_data(data):
    json_body = []
    for item in data['sensors']:
        ts_str = item['observations'][0].get('timestamp')
        if ts_str is not None:
            ts = parse(item['observations'][0]['timestamp'], dayfirst=True)
        else:
            ts = datetime.datetime.utcnow()
            print(ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ data without timestamp!"))
        dev_id = item['sensor'][0:-2]
        if item['sensor'].endswith('N'):
            measurement = {
                "measurement": 'LAeq',
                "tags": {
                    "dev-id": dev_id,  # leave out sensor type
                },
                "time": ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                "fields": {
                    'dBA': float(item['observations'][0]['value'])
                }
            }
            json_body.append(measurement)
        if item['sensor'].endswith('S'):
            cnt = 0
            secvals = item['observations'][0]['value'].split(';')
            secvals.reverse()
            for val in secvals:
                measurement = {
                    "measurement": 'LAeq1s',
                    "tags": {
                        "dev-id": dev_id,  # leave out sensor type
                    },
                    "time": (ts - datetime.timedelta(seconds=cnt)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
                    "fields": {
                        'dBA': float(val.split(',')[0])
                    }
                }
                cnt += 1
                json_body.append(measurement)
    return json_body


def parse_sentilo2ngsi(data):
    device_id = data['sensors'][0]['sensor'][:-2] # all list items _should_ have same ID
    obs_type = 'NoiseLevelObserved'
    location = {
        "type": "Point",
        "coordinates": [0,0]
    } # TODO
    # address = ""
    sonometerClass = "1"

    dateObserved = None
    measurand = None
    for m in data['sensors']: # iterate to find LAeq aka "N" among params reported by sensor
        if 'N' in m['sensor'][-1]:
            ts = parse(m['observations'][0]['timestamp'], dayfirst=True)
            dateObserved = ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
            # dateObserved = datetime.strptime(m['observations'][0]['timestamp'], "%d/%m/%YT%H:%M:%S%Z").isoformat()
            LAeq = float(m['observations'][0]['value'])
            measurand = "{} | {} | {}".format("LAeq", LAeq, "A-weighted, equivalent, sound level")
    if measurand:
        noiseLevelObserved_payload = {
            "id": device_id,
            "type": "Cesva-TA120",
            "NoiseLevelObserved": {
                "type": "NoiseLevelObserved",
                "value": {
                    "id": device_id + "-NoiseLevelObserved-" + dateObserved,
                    "type": obs_type,
                    "location": location,
                    "dateObserved": dateObserved,
                    "measurand": [
                        measurand
                    ],
                    "LAeq": LAeq,
                    "sonometerClass": sonometerClass
                }
            }
        }
        return noiseLevelObserved_payload
    return None


def push_ngsi_orion(data):
    device_id = data['id']
    resp = None
    try:
        # try to update the entity...
        resp = requests.patch('{}/entities/{}/attrs/'.format(ORION_URL_ROOT, data['id']), 
                auth=(ORION_USERNAME, ORION_PASSWORD),
                json={'NoiseLevelObserved': data['NoiseLevelObserved']})
    except Exception as e:
        #log.error('Something went wrong! Exception: {}'.format(e))
        print('Something went wrong PATCHing to Orion! Exception: {}'.format(e))

    # ...if updating failed, the entity probably doesn't exist yet so create it
    if not resp or (resp.status_code != 204):
        resp = requests.post('{}/entities/'.format(ORION_URL_ROOT), 
                auth=(ORION_USERNAME, ORION_PASSWORD),
                json=data)
    return resp


@csrf_exempt
def sentilohandler(request, version='0.0.0'):
    rawbody =  request.body.decode('utf-8')
    try:
        data = json.loads(request.body.decode('utf-8'))
    except ValueError as err:
        print(str(err))
        with open('/tmp/sentiloraw.log', 'at') as f:
            f.write(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ") + ' SERVER ERROR with data\n')
            f.write(rawbody)
        raise
        return HttpResponse('SERVER ERROR: ' + str(err), status=500)
    with open('/tmp/sentilodata.log', 'at') as f:
        f.write(json.dumps(data, indent=1) + '\n')
    json_body = parse_sentilo_data(data)
    with open('/tmp/sentiloparsed.log', 'at') as f:
        f.write(json.dumps(json_body, indent=1) + '\n')
    # print(json.dumps(json_body, indent=1))
    try:
        iclient = get_iclient(database='sentilo')
        iclient.write_points(json_body)
    except influxdb.exceptions.InfluxDBClientError as err:
        print(str(err))
        raise
        return HttpResponse(str(err), status=500)
    influx_response = HttpResponse("ok")

    #parse to NGSI format and push to Orion
    ngsi_json = parse_sentilo2ngsi(data)
    ngsi_response = push_ngsi_orion(ngsi_json)

    return influx_response


def parse_noisesensorv1_data(request):
    json_body = []
    ts = datetime.datetime.utcnow()
    s = request.GET.get('1s', '')
    dev_id = request.GET.get('mac')
    rssi = int(request.GET.get('rssi'))
    uptime = int(request.GET.get('uptime', 0))
    if s != '':
        svals = [int(x) for x in filter(None, s.split(','))]
        svals.reverse()
    else:
        return HttpResponse('Broken data {}'.format(s[:10]), status=400)
    cnt = 0
    measurement = {
        "measurement": 'rssi',
        "tags": {
            "dev-id": dev_id,  # leave out sensor type
        },
        "time": (ts - datetime.timedelta(seconds=cnt)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "fields": {
            'rssi': rssi
        }
    }
    json_body.append(measurement)
    if uptime:
        uptime = uptime / 1000.0  # convert to seconds
        measurement = {
            "measurement": 'uptime',
            "tags": {
                "dev-id": dev_id,  # leave out sensor type
            },
            "time": (ts - datetime.timedelta(seconds=cnt)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "fields": {
                'uptime': uptime
            }
        }
        json_body.append(measurement)
    for val in svals:
        measurement = {
            "measurement": 'raw_pp',
            "tags": {
                "dev-id": dev_id,  # leave out sensor type
            },
            "time": (ts - datetime.timedelta(seconds=cnt)).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "fields": {
                'raw': val
            }
        }
        cnt += 1
        if val > 0:
            json_body.append(measurement)
    return json_body


@csrf_exempt
def noisesensorhandler(request, version='0.0.0'):
    data = request.GET.get('1s', 'NO DATA')
    with open('/tmp/noiseraw.log', 'at') as f:
        f.write(datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%fZ") + ' SERVER ERROR with data\n')
        f.write(data)
    json_body = parse_noisesensorv1_data(request)
    # print(json.dumps(json_body, indent=1))
    try:
        iclient = get_iclient(database='noisesensor')
        iclient.write_points(json_body)
    except influxdb.exceptions.InfluxDBClientError as err:
        print(str(err))
        raise
        return HttpResponse(str(err), status=500)
    response = HttpResponse("ok")
    return response


@csrf_exempt
def mapmytracks(request):
    """
    Dump a HttpRequest to files in a directory.
    """
    res = dump_request(request, postfix='mapmytracks')
    print('\n'.join(res))  # to console or stdout/stderr
    pl = request.POST.get('points', '').split()
    points = [pl[x:x + 4] for x in range(0, len(pl), 4)]
    for point in points:
        lat, lon, alt, epoch = [float(x) for x in point]
        ts = pytz.UTC.localize(datetime.datetime.utcfromtimestamp(epoch))
        print(lat, lon, alt, epoch, ts)
    req = request.POST.get('request', '')
    if req == 'start_activity':
        return HttpResponse("""<?xml version="1.0" encoding="UTF-8"?>
            <message> <type>activity_started</type> <activity_id>9346</activity_id> </message>""")
    elif req == 'update_activity':
        return HttpResponse("""<?xml version="1.0" encoding="UTF-8"?>
            <message> <type>activity_updated</type> </message>""")
    elif req == 'upload_activity':
        return HttpResponse("""<?xml version="1.0" encoding="UTF-8"?>
            <message> <type>success</type> <id>12345678</id> </message>""")
    return HttpResponse("OK, I dumped HTTP request data to a file.")
