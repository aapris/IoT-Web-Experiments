import os
from django.conf.urls import url
from . import views

OBSCURE_URL = r'^{}$'.format(os.environ.get('OBSCURE_URL', 'this_should_be_in_env_var'))

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(OBSCURE_URL, views.obscure_dump_request_endpoint, name='dump_request'),
]