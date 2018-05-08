import os
import string
import random
from django.contrib.gis.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.utils.translation import ugettext_lazy as _
from django.conf import settings


def get_uid(length=12):
    """
    Generate and return a random string which can be considered unique.
    Default length is 12 characters from set [a-zA-Z0-9].
    """
    alphanum = string.ascii_uppercase + string.digits
    return ''.join([alphanum[random.randint(0, len(alphanum) - 1)]
                    for _ in range(length)])


class Request(models.Model):
    """
    Metadata about Request.
    """
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE, verbose_name='Sender')
    status = models.CharField(max_length=40, default="NEW",
                              choices=(("NEW", "New"),
                                       ("NOTIFIED", "Notified"),
                                       ("SPAM", "Spam"),
                                       ("PROCESSED", "Processed"),
                                       ("DELETED", "Deleted"),
                                       ))
    method = models.CharField(max_length=20, blank=False, editable=False)
    path = models.CharField(max_length=200, blank=False, editable=False)
    filecount = models.IntegerField(default=0)
    created = models.DateTimeField(default=timezone.now, editable=False)

    def __str__(self):
        return '{}'.format(self.created.strftime('%Y-%m-%d %H:%M:%S'))

    def save(self, *args, **kwargs):
        super(Request, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        path = os.path.join(settings.MEDIA_ROOT, str(self.path))
        # delete files
        for fn in os.listdir(path):
            full_path = os.path.join(path, fn)
            print('Removing file {}'.format(full_path))
            os.remove(full_path)
        print('Removing directory {}'.format(path))
        os.rmdir(path)
        super(Request, self).delete(*args, **kwargs)


class Datalogger(models.Model):
    user = models.ForeignKey(User, blank=True, null=True, on_delete=models.SET_NULL, verbose_name=_('Owner'))
    uid = models.CharField(max_length=40, unique=True, db_index=True, default=get_uid, editable=False)
    devid = models.CharField(max_length=64, unique=True, verbose_name=_('Unique device id'))
    name = models.CharField(max_length=50, blank=True)
    description = models.CharField(max_length=200, blank=True)
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    location = models.PointField(null=True, blank=True)
    activity_at = models.DateTimeField(null=True, editable=True)
    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(default=timezone.now, editable=False)

    # Returns the string representation of the model.
    def __str__(self):
        return '{} ({})'.format(self.name, self.devid)
