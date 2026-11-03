import os
import secrets
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent
PUBLIC_MODE = os.environ.get('TRACKER_PUBLIC') == '1'
STATE_DIR = Path(os.environ.get('TRACKER_STATE_DIR', BASE_DIR / '.state')).resolve()
STATE_DIR.mkdir(parents=True, exist_ok=True)
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY:
    if PUBLIC_MODE:
        raise ImproperlyConfigured('DJANGO_SECRET_KEY is required in public mode')
    secret_path = STATE_DIR / 'secret.key'
    try:
        with secret_path.open('x', encoding='ascii') as stream:
            stream.write(secrets.token_urlsafe(64))
    except FileExistsError:
        pass
    SECRET_KEY = secret_path.read_text(encoding='ascii').strip()
if len(SECRET_KEY) < 50:
    raise ImproperlyConfigured('DJANGO_SECRET_KEY must contain at least 50 characters')
DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.environ.get('DJANGO_ALLOWED_HOSTS', '127.0.0.1,localhost').split(',') if host.strip()]
CSRF_TRUSTED_ORIGINS = [value.strip() for value in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if value.strip()]
if '*' in ALLOWED_HOSTS or any('*' in origin for origin in CSRF_TRUSTED_ORIGINS):
    raise ImproperlyConfigured('Wildcard hosts/origins are forbidden')
if PUBLIC_MODE and (not CSRF_TRUSTED_ORIGINS or ALLOWED_HOSTS == ['127.0.0.1', 'localhost']):
    raise ImproperlyConfigured('Explicit public hosts and HTTPS CSRF origins are required')
INSTALLED_APPS = ['django.contrib.auth', 'django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.messages', 'django.contrib.staticfiles', 'boards']
MIDDLEWARE = ['django.middleware.security.SecurityMiddleware', 'whitenoise.middleware.WhiteNoiseMiddleware', 'boards.middleware.BoundaryMiddleware', 'django.contrib.sessions.middleware.SessionMiddleware', 'django.middleware.common.CommonMiddleware', 'django.middleware.csrf.CsrfViewMiddleware', 'django.contrib.auth.middleware.AuthenticationMiddleware', 'django.contrib.messages.middleware.MessageMiddleware', 'django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [BASE_DIR / 'templates'], 'APP_DIRS': True, 'OPTIONS': {'context_processors': ['django.template.context_processors.request', 'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION = 'config.wsgi.application'
DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': STATE_DIR / 'tracker.sqlite3', 'TEST': {'NAME': STATE_DIR / 'tests.sqlite3'}, 'OPTIONS': {'timeout': 5, 'transaction_mode': 'IMMEDIATE'}}}
AUTH_PASSWORD_VALIDATORS = [{'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'}, {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}}, {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'}, {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'}]
LANGUAGE_CODE = 'ru'
TIME_ZONE = 'Europe/Moscow'
USE_I18N = True
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'}, 'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage' if PUBLIC_MODE else 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
WHITENOISE_AUTOREFRESH = not PUBLIC_MODE
WHITENOISE_USE_FINDERS = not PUBLIC_MODE
LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/boards/'
LOGOUT_REDIRECT_URL = LOGIN_URL
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = PUBLIC_MODE
CSRF_COOKIE_SECURE = PUBLIC_MODE
SECURE_SSL_REDIRECT = PUBLIC_MODE
SECURE_HSTS_SECONDS = 31536000 if PUBLIC_MODE else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = PUBLIC_MODE
SECURE_HSTS_PRELOAD = False
SECURE_REFERRER_POLICY = 'same-origin'
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
if PUBLIC_MODE:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
DATA_UPLOAD_MAX_MEMORY_SIZE = 32768
DATA_UPLOAD_MAX_NUMBER_FIELDS = 30
CSRF_FAILURE_VIEW = 'boards.views.csrf_failure'
# Public hosting remains gated until deployment-specific login throttling is reviewed.
