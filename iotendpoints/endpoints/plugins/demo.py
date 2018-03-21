"""
Demo endpoint.

You must declare environment variable DEMO_URL to activate this plugin.

If you are running development server (`python manage.py runserver`), you can
`export DEMO_URL=path_without_leading_slash`
before starting runserver.

If you use supervisord to keep gunicorn or similar running, you can add line
`environment = DEMO_URL=path_without_leading_slash` in your superisor/site.conf.

Raw gunicorn seems to accept `--env DEMO_URL=path_without_leading_slash` command line argument.
"""

import os
from django.conf.urls import url
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from endpoints.utils import BasePlugin

ENV_NAME = 'DEMO_URL'
URL = os.environ.get(ENV_NAME)


class Plugin(BasePlugin):
    """
    Example plugin. Checks if endpoint's URL has been set in env.
    """
    name = 'demo'
    viewname = 'demohandler'

    def __init__(self):
        """Check that `ENV_NAME` is in env variables."""
        super().__init__()
        if URL is not None:
            self.in_use = True

    def register(self):
        print('Registering plugin "{}"'.format(self.name))

    def get_urlpatterns(self):
        if self.in_use is False:
            print('{} environment variable is not set. Demo endpoint is not in use.'.format(ENV_NAME))
            urlpatterns = []
        else:
            url_pattern = r'^{}$'.format(URL)
            urlpatterns = [
                url(url_pattern, self.view_func, name=self.viewname),
            ]
        return urlpatterns

    @csrf_exempt
    def view_func(self, request):
        print('Requested {} {}'.format(request.method, request.META['PATH_INFO']))
        return HttpResponse('OK')
