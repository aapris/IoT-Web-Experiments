def get_plugins(plugins_dir):
    for name in plugins_dir.__all__:
        plugin = getattr(plugins_dir, name)
        try:
            # see if the plugin has a 'Plugin' class
            p = plugin.Plugin()
        except AttributeError:
            # raise an exception, log a message,
            # or just ignore the problem
            raise
            pass
        yield p


def plugin_urlpatterns(plugins_dir):
    plugins = get_plugins(plugins_dir)
    urlpatterns = []
    for p in plugins:
        register_plugin = p.register
        register_plugin()
        urlpatterns += p.get_urlpatterns()
    return urlpatterns


class BasePlugin:
    """
    Every plugin must inherit BasePlugin and implement at least get_urlpatterns()
    and a view function, which returns HttpResponse object.
    """

    name = None
    viewname = None

    def __init__(self):
        if self.name is None or self.viewname is None:
            raise ValueError('self.name or self.viewname must be defined')

    def register(self):
        print('Registering plugin "{}"'.format(self.name))

    def get_urlpatterns(self):
        return []
