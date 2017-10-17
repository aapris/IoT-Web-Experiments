import os
from django.conf.urls import url
from . import views


DUMMY_OBSCURE_URL = 'this_should_be_in_env_var'

OBSCURE_URL = os.environ.get('OBSCURE_URL', DUMMY_OBSCURE_URL)
DIGITA_URL = os.environ.get('DIGITA_URL', DUMMY_OBSCURE_URL)

if DUMMY_OBSCURE_URL == OBSCURE_URL:
    print("Warning: you should set OBSCURE_URL environment variable in this env\n\n")

OBSCURE_URL_PATTERN = r'^{}$'.format(os.environ.get('OBSCURE_URL', OBSCURE_URL))
DIGITA_URL_PATTERN = r'^{}$'.format(os.environ.get('DIGITA_URL', OBSCURE_URL))

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(OBSCURE_URL_PATTERN, views.obscure_dump_request_endpoint, name='dump_request'),
    url(DIGITA_URL_PATTERN, views.digita_dump_request_endpoint, name='digita_dump_request'),
    url(r'^basicauth$', views.basicauth_dump_request_endpoint, name='basicauth_dump_request'),
    url(r'^aqtest$', views.basicauth_dump_request_endpoint, name='aqtest'),
]



