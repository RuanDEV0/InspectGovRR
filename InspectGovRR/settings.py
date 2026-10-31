"""Configuração do Django, banco e sincronização a partir do ambiente."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent
env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')


SECRET_KEY = env('DJANGO_SECRET_KEY')
DEBUG = env.bool('DJANGO_DEBUG', default=False)

ALLOWED_HOSTS = env.list('DJANGO_ALLOWED_HOSTS', default=[])
for local_hostname in ('localhost', '127.0.0.1'):
    if local_hostname not in ALLOWED_HOSTS:
        ALLOWED_HOSTS.append(local_hostname)
render_hostname = env('RENDER_EXTERNAL_HOSTNAME', default='')
if render_hostname and render_hostname not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(render_hostname)
CSRF_TRUSTED_ORIGINS = env.list('DJANGO_CSRF_TRUSTED_ORIGINS', default=[])
if render_hostname:
    CSRF_TRUSTED_ORIGINS.append(f'https://{render_hostname}')

# Ative a confiança no cabeçalho somente atrás de um proxy que o controle.
if env.bool('DJANGO_TRUST_PROXY_SSL_HEADER', default=False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('DJANGO_SECURE_SSL_REDIRECT', default=False)
SECURE_REDIRECT_EXEMPT = [r'^healthz/$']
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_HSTS_SECONDS = env.int('DJANGO_HSTS_SECONDS', default=0)

FIPLAN_AUTO_SYNC_ENABLED = env.bool('FIPLAN_AUTO_SYNC_ENABLED', default=False)
FIPLAN_SYNC_INTERVAL_MINUTES = env.int('FIPLAN_SYNC_INTERVAL_MINUTES', default=1440)
FIPLAN_SYNC_YEAR = env.int('FIPLAN_SYNC_YEAR', default=2026)
FIPLAN_NATURE_CODE = env('FIPLAN_NATURE_CODE', default='33903900')
FIPLAN_SYNC_DIARIAS_ENABLED = env.bool('FIPLAN_SYNC_DIARIAS_ENABLED', default=False)
FIPLAN_USERNAME = env('FIPLAN_USERNAME', default='')
FIPLAN_PASSWORD = env('FIPLAN_PASSWORD', default='')

if FIPLAN_SYNC_INTERVAL_MINUTES < 1:
    raise ValueError('FIPLAN_SYNC_INTERVAL_MINUTES deve ser maior que zero')
if FIPLAN_SYNC_YEAR < 2000 or FIPLAN_SYNC_YEAR > 9999:
    raise ValueError('FIPLAN_SYNC_YEAR deve ser um ano entre 2000 e 9999')


INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'integrations',
    'unidades',
    'receita_arrecadada',
    'remuneracoes',
    'contratos',
    'portal',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]
if not DEBUG:
    MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')

ROOT_URLCONF = 'InspectGovRR.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates']
        ,
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'portal.context_processors.portal',
            ],
        },
    },
]

WSGI_APPLICATION = 'InspectGovRR.wsgi.application'


DATABASES = {
    'default': env.db_url('DATABASE_URL') if env('DATABASE_URL', default='') else {
        'ENGINE': 'django.db.backends.postgresql',
        "NAME": env("DB_NAME"),
        "USER": env("DB_USER"),
        "PASSWORD": env("DB_PASSWORD"),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT")
    }
}
DATABASES['default']['CONN_HEALTH_CHECKS'] = True


AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'
if not DEBUG:
    STORAGES = {
        'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
        'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
    }
