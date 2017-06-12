import os
import pytz
import base64
# from django.shortcuts import render
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from endpoints.models import Request
from django.contrib.auth import authenticate


META_KEYS = ['QUERY_STRING', 'REMOTE_ADDR', 'REMOTE_HOST', 'REMOTE_USER',
             'REQUEST_METHOD', 'SERVER_NAME', 'SERVER_PORT']


def index(request):
    return HttpResponse("Hello, world. This is IoT endpoint.")


def _dump_request_endpoint(request):
    """
    Dump a HttpRequest to files in a directory.
    """
    now = timezone.now().astimezone(pytz.utc)
    r = Request(method=request.method)
    r.path = os.path.join(now.strftime('%Y-%m-%d'), now.strftime('%Y%m%dT%H%M%S.%fZ'))
    fpath = os.path.join(settings.MEDIA_ROOT, r.path)
    os.makedirs(fpath, exist_ok=True)
    fname = os.path.join(fpath, 'request.raw')
    with open(fname, 'wb') as destination:
        destination.write(request.body)

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
    fname = os.path.join(fpath, 'request.txt')
    with open(fname, 'wt+') as destination:
        destination.write('\n'.join(res))
    return res


@csrf_exempt
def obscure_dump_request_endpoint(request):
    """
    Dump a HttpRequest to files in a directory.    
    """
    res = _dump_request_endpoint(request)
    print('\n'.join(res))  # to console or stdout/stderr
    return HttpResponse("OK, I dumped HTTP request data to a file.")


def _basicauth(request):
    # Check for valid basic auth header
    if 'HTTP_AUTHORIZATION' in request.META:
        auth = request.META['HTTP_AUTHORIZATION'].split()
        if len(auth) == 2:
            if auth[0].lower() == "basic":
                a = auth[1].encode('utf8')
                s = base64.b64decode(a)
                uname, passwd = s.decode('utf8').split(':')
                user = authenticate(username=uname, password=passwd)
                return uname, passwd, user
    return None, None, None


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
        res = _dump_request_endpoint(request)
        print('\n'.join(res))
        return HttpResponse("OK, I dumped HTTP request data to a file.")
