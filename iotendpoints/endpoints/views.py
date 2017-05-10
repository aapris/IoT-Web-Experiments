# from django.shortcuts import render
from django.http import HttpResponse


def index(request):
    return HttpResponse("Hello, world. This is IoT endpoint.")


META_KEYS = ['QUERY_STRING', 'REMOTE_ADDR', 'REMOTE_HOST', 'REMOTE_USER', 'REQUEST_METHOD', 'SERVER_NAME', 'SERVER_PORT']

def obscure_dump_request_endpoint(request):
    print('--- GET parameters ---')
    for key, val in request.GET.items():
        print('{}={}'.format(key, val))

    print('--- POST parameters ---')
    for key, val in request.POST.items():
        print('{}={}'.format(key, val))

    print('--- META parameters ---')
    for key, val in request.META.items():
        if key.startswith('HTTP_') or key.startswith('CONTENT_') or key in META_KEYS:
            print('{}={}'.format(key, val))

    return HttpResponse("OK, I dumped HTTP request data to a file.")
