import os
import pytz
import json
import time
import datetime
from dateutil.parser import parse
from astral import Astral, Location, AstralError

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.shortcuts import render

EPOCH = datetime.datetime.utcfromtimestamp(0)


def index(request):
    return HttpResponse("Hello, world. From here you can get a bunch of different minimal datasets.")

def sun(request):
    """
    Return sunrise, sunset etc. times.
    """

    a = Astral()
    a.solar_depression = 'civil'
    l = Location()

    # l.name = 'Lapinlahden sairaala'
    # l.region = 'Helsinki'

    lat = request.GET.get('lat')
    lon = request.GET.get('lon')
    if lat is None or lon is None:
        l.latitude = 60.167761
        l.longitude = 24.9118141
        l.loc_source = 'default'
    else:
        l.latitude = float(lat)
        l.longitude = float(lon)
        l.loc_source = 'request'
    l.timezone = 'UTC'
    l.elevation = 0
    timeformat = request.GET.get('timeformat', 'epoch')
    date_str = request.GET.get('date')
    format_str = request.GET.get('format', 'json')
    date = datetime.datetime.now().date()
    if date_str is not None:
        date = parse(date_str).date()
        pass
    sundata = {
        'now': datetime.datetime.now(tz=pytz.UTC),  # .astimezone(pytz.UTC),
        'date': date.strftime('%Y-%m-%d'),
        'lat': l.latitude,
        'lon': l.longitude,
        'loc_source': l.loc_source,
    }

    try:
        sun = l.sun(date=date, local=False)
    except AstralError as e:
        return HttpResponse(json.dumps({'error': str(e)}), content_type='application/json')
    for k in ['dawn', 'sunrise', 'noon', 'sunset', 'dusk']:
        sundata[k] = sun[k]
    if timeformat == 'iso':
        for k in sundata.keys():
            if isinstance(sundata[k], datetime.datetime):
                sundata[k] = sundata[k].isoformat()
    else:  # timeformat == 'epoch':
        for k in sundata.keys():
            if isinstance(sundata[k], datetime.datetime):
                sundata[k] = int(sundata[k].timestamp())
    res_str = json.dumps(sundata, indent=2)
    return HttpResponse(res_str, content_type='application/json')

