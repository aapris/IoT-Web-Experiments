import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = '1_y=*j=_7oc2gasdasdasd&-qzz+hon#m+og$_@wyw7o9a$98)'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'endpoints',
]

ROOT_URLCONF = 'iotendpoints.urls'

# Database
# https://docs.djangoproject.com/en/1.11/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}

TIME_ZONE = 'Europe/Helsinki'

# CELERY_BROKER_URL = 'redis://localhost:6379/0'

# LOG_FILE = '/site/path.to/logs/django.log'
LOG_FILE = os.path.normpath(os.path.join(BASE_DIR, "django.log"))

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
        'detailed': {
            'format': '[%(asctime)s] %(levelname)-8s %(module)s.%(funcName)s:%(lineno)d "%(message)s"'
        },
        'simple': {
            'format': '[%(asctime)s] %(levelname)-8s"%(message)s"'
        },
    },
    'handlers': {
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.handlers.TimedRotatingFileHandler',
            'filename': LOG_FILE,
            'formatter': 'detailed',
            'delay': False,
            'when': 'midnight',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['mail_admins'],
            'level': 'ERROR',
            'propagate': True,
        },
        'endpoints': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    }
}
