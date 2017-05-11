import os
import pytz
# from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone


META_KEYS = ['QUERY_STRING', 'REMOTE_ADDR', 'REMOTE_HOST', 'REMOTE_USER', 'REQUEST_METHOD', 'SERVER_NAME', 'SERVER_PORT']


def index(request):
    return HttpResponse("Hello, world. This is IoT endpoint.")


@csrf_exempt
def obscure_dump_request_endpoint(request):
    res = []
    res.append('Request Method: {}'.format(request.method))

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
    now = timezone.now().astimezone(pytz.utc)
    fpath = os.path.join(settings.MEDIA_ROOT, now.strftime('%Y%m%dT%H%M%S.%fZ'))
    os.makedirs(fpath, exist_ok=True)
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
    fname = os.path.join(fpath, 'request.txt')
    with open(fname, 'wt+') as destination:
        destination.write('\n'.join(res))
    print('\n'.join(res))
    return HttpResponse("OK, I dumped HTTP request data to a file.")
