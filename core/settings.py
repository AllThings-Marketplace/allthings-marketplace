"""
Django settings for core project (Development + Railway Production Ready).
"""
import os
from pathlib import Path
from celery.schedules import crontab
from dotenv import load_dotenv
import cloudinary

try:
    import dj_database_url
except ImportError:
    dj_database_url = None

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / '.env')

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    os.environ.get('SECRET_KEY', 'dev-fallback-secret-key-change-in-production')
)

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = os.environ.get('DEBUG', 'False').lower() in ('true', '1', 'yes')

# ==============================================================================
# 1. HOSTS, RAILWAY DOMAIN AUTO-DETECTION & CSRF
# ==============================================================================
RAILWAY_PUBLIC_DOMAIN = os.environ.get('RAILWAY_PUBLIC_DOMAIN', '').strip()
RAILWAY_PRIVATE_DOMAIN = os.environ.get('RAILWAY_PRIVATE_DOMAIN', '').strip()

DEFAULT_HOSTS = [
    '127.0.0.1',
    'localhost',
    '.ngrok-free.dev',
    '.onrender.com',
    '.up.railway.app',
    '.railway.internal',
]
ENV_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', '').split(',') if h.strip()]
if RAILWAY_PUBLIC_DOMAIN:
    ENV_HOSTS.append(RAILWAY_PUBLIC_DOMAIN)
if RAILWAY_PRIVATE_DOMAIN:
    ENV_HOSTS.append(RAILWAY_PRIVATE_DOMAIN)

ALLOWED_HOSTS = list(set(DEFAULT_HOSTS + ENV_HOSTS))

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
USE_X_FORWARDED_HOST = True

DEFAULT_CSRF_ORIGINS = [
    'https://resonant-baggy-hunk.ngrok-free.dev',
    'https://*.ngrok-free.dev',
    'https://*.onrender.com',
    'https://*.up.railway.app',
    'http://127.0.0.1:8000',
    'http://localhost:8000',
]
ENV_CSRF_ORIGINS = [o.strip() for o in os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',') if o.strip()]
if RAILWAY_PUBLIC_DOMAIN:
    ENV_CSRF_ORIGINS.append(f"https://{RAILWAY_PUBLIC_DOMAIN}")

CSRF_TRUSTED_ORIGINS = list(set(DEFAULT_CSRF_ORIGINS + ENV_CSRF_ORIGINS))


# ==============================================================================
# 2. APPLICATION DEFINITION
# ==============================================================================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',

    # Cloud Media Storage
    'cloudinary_storage',
    'cloudinary',

    # Third-Party Apps
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    # Local Apps
    'accounts',
    'marketplace',
    'orders',
    'feedback',
    'notifications',
    'dashboard',
]

SITE_ID = int(os.environ.get('SITE_ID', 1))

AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

# Allauth Configuration
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True
ACCOUNT_LOGOUT_ON_GET = True
ACCOUNT_SIGNUP_FIELDS = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_LOGIN_METHODS = {'email'}

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': [
            'profile',
            'email',
        ],
        'AUTH_PARAMS': {
            'access_type': 'online',
        },
        'OAUTH_PKCE_ENABLED': True,
    }
}

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'marketplace.context_processors.cart_item_count',
                'marketplace.context_processors.global_categories',
                'notifications.context_processors.global_notifications',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# ==============================================================================
# 3. DATABASE (Railway PostgreSQL via DATABASE_URL, SQLite Fallback Locally)
# ==============================================================================
DATABASE_URL = os.environ.get('DATABASE_URL', '').strip()
if DATABASE_URL and dj_database_url:
    # Railway private networking (*.railway.internal) does not use SSL
    is_internal_railway_db = '.railway.internal' in DATABASE_URL or 'localhost' in DATABASE_URL or '127.0.0.1' in DATABASE_URL
    require_db_ssl = os.environ.get('DB_SSL_REQUIRE', str(not DEBUG and not is_internal_railway_db)).lower() in ('true', '1', 'yes')

    DATABASES = {
        'default': dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            conn_health_checks=True,
            ssl_require=require_db_ssl,
        )
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }


# ==============================================================================
# 4. PASSWORD VALIDATION & I18N
# ==============================================================================
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Lagos'
USE_I18N = True
USE_TZ = True


# ==============================================================================
# 5. STATIC FILES, MEDIA & CLOUDINARY STORAGE
# ==============================================================================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
WHITENOISE_MANIFEST_STRICT = False

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Request-body upload limits (35 MB total request payload, 5 MB per in-memory file)
DATA_UPLOAD_MAX_MEMORY_SIZE = 35 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024

CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', '').strip(),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', '').strip(),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', '').strip(),
}

if CLOUDINARY_STORAGE['CLOUD_NAME']:
    cloudinary.config(
        cloud_name=CLOUDINARY_STORAGE['CLOUD_NAME'],
        api_key=CLOUDINARY_STORAGE['API_KEY'],
        api_secret=CLOUDINARY_STORAGE['API_SECRET'],
        secure=True,
    )
    STORAGES = {
        "default": {
            "BACKEND": "cloudinary_storage.storage.MediaCloudinaryStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

# Required for django-cloudinary-storage compatibility on Django 5.1+ / 6.1
STATICFILES_STORAGE = 'whitenoise.storage.CompressedStaticFilesStorage'


# ==============================================================================
# 6. EMAIL CONFIGURATION
# ==============================================================================
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '').strip()
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '').strip()
BREVO_API_KEY = os.environ.get('BREVO_API_KEY', '').strip()
EMAIL_TIMEOUT = 8  # Prevents Gunicorn worker hangs when SMTP ports are blocked

if EMAIL_HOST_USER and EMAIL_HOST_PASSWORD:
    EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
    EMAIL_HOST = os.environ.get('EMAIL_HOST', 'smtp-relay.brevo.com')
    EMAIL_PORT = int(os.environ.get('EMAIL_PORT', 587))
    EMAIL_USE_TLS = True
else:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

DEFAULT_FROM_EMAIL = os.environ.get(
    'DEFAULT_FROM_EMAIL',
    f"AllThings Marketplace <{EMAIL_HOST_USER or 'noreply@allthings.com'}>"
)


# ==============================================================================
# 7. CELERY & REDIS (Graceful In-Memory Fallback if Redis isn't attached yet)
# ==============================================================================
REDIS_URL = os.environ.get('REDIS_URL', os.environ.get('CELERY_BROKER_URL', '')).strip()
if REDIS_URL:
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CELERY_BROKER_URL = 'memory://'
    CELERY_RESULT_BACKEND = 'cache+memory://'
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True

CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'

CELERY_BEAT_SCHEDULE = {
    'auto-clear-ghost-escrows-hourly': {
        'task': 'orders.tasks.auto_clear_ghost_escrows',
        'schedule': crontab(minute=0),
    },
}


# ==============================================================================
# 8. AUTHENTICATION REDIRECTS & THIRD-PARTY GATEWAYS
# ==============================================================================
AUTH_USER_MODEL = 'accounts.User'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_REDIRECT_URL = 'marketplace:home'
LOGOUT_REDIRECT_URL = 'marketplace:home'
LOGIN_URL = 'accounts:login'

PAYSTACK_PUBLIC_KEY = os.environ.get('PAYSTACK_PUBLIC_KEY', '')
PAYSTACK_SECRET_KEY = os.environ.get('PAYSTACK_SECRET_KEY', '')
GIGL_API_KEY = os.environ.get('GIGL_API_KEY', 'your_test_key_here')
TERMII_API_KEY = os.environ.get('TERMII_API_KEY', '').strip()
TERMII_SENDER_ID = os.environ.get('TERMII_SENDER_ID', 'AllThings').strip()
TERMII_CHANNEL = os.environ.get('TERMII_CHANNEL', 'generic').strip()
TERMII_BASE_URL = os.environ.get('TERMII_BASE_URL', 'https://v3.api.termii.com').strip()
SHOW_OTP_FALLBACK = os.environ.get('SHOW_OTP_FALLBACK', 'False').lower() in ('true', '1', 'yes')

# Uses explicit SITE_URL if set, else auto-detects Railway public URL, else falls back to ngrok
if os.environ.get('SITE_URL'):
    SITE_URL = os.environ.get('SITE_URL').rstrip('/')
elif RAILWAY_PUBLIC_DOMAIN:
    SITE_URL = f"https://{RAILWAY_PUBLIC_DOMAIN}"
else:
    SITE_URL = 'https://resonant-baggy-hunk.ngrok-free.dev'


# ==============================================================================
# 9. PRODUCTION SECURITY HEADERS (Active automatically when DEBUG=False)
# ==============================================================================
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'