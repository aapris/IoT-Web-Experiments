# Create your tasks here
from __future__ import absolute_import, unicode_literals
from celery import shared_task


#def handle_datapost(headers, vars):
@shared_task
def handle_datapost(headers, vars):
    print(headers, vars)
    return headers, vars

