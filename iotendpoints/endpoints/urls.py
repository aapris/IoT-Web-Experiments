from django.conf.urls import url
from . import views

OBSCURE_URL = r'^obs$'

urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(OBSCURE_URL, views.obscure_dump_request_endpoint, name='dump_request'),
]