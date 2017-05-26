import os
from django.db import models
from django.utils import timezone
from django.conf import settings


class Request(models.Model):
    """
    Metadata about Request.
    """
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
        path = os.path.join(settings.MEDIA_ROOT, self.path)
        # delete files
        for fn in os.listdir(path):
            full_path = os.path.join(path, fn)
            print('Removing file {}'.format(full_path))
            os.remove(full_path)
        print('Removing directory {}'.format(path))
        os.rmdir(path)
        super(Request, self).delete(*args, **kwargs)
