import os
from pathlib import Path
import environ
import dj_database_url



# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

USE_TZ = True
TIME_ZONE = 'UTC'


env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))


ON_RENDER = os.environ.get('ON_RENDER', 'False') == 'True'

# DEBUG must be its own explicit, default-closed flag — it must never be
# inferred from ON_RENDER, or any deployment target other than this specific
# Render service (self-hosted Docker, another PaaS) runs wide open by default.
DEBUG = os.getenv('DEBUG', 'False') == 'True'

if ON_RENDER:
    
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            ssl_require=True,
        )
    }
    DATABASES['default']['OPTIONS'] = {
        'connect_timeout': 10,
        'application_name': 'vulor-app',
    }
    DATABASES['default']['ATOMIC_REQUESTS'] = True

else:
    
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }
    DATABASES['default']['ATOMIC_REQUESTS'] = True




SECRET_KEY = os.getenv('SECRET_KEY')
if DEBUG:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'vulor.onrender.com']
else:
    ALLOWED_HOSTS = os.getenv('ALLOWED_HOSTS', '').split(',')

# Applications
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'django.contrib.humanize',
    'django_celery_beat',
    
    # Third-party
    'allauth',
    'allauth.account',


    # Local apps
    'products',
    'accounts',
    'cart',
    'orders',
    'error_pages',
    'payments',
    'dashboard',
    'services',
    'csp',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'vulor.middleware.BodySizeLimitMiddleware',
    'csp.middleware.CSPMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
]

# Security settings
SECURE_SSL_REDIRECT = not DEBUG
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
SESSION_COOKIE_AGE = 60*60*2 

SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'

# Content-Security-Policy — Report-Only for now: violations are logged by
# the browser (visible in devtools) but nothing is blocked. This lets the
# policy be verified against real traffic across every page (Google Fonts,
# the Chart.js CDN script on the dashboard, several un-nonced inline
# <script> blocks) before a future change switches to
# CONTENT_SECURITY_POLICY (enforcing). Do not add an enforcing policy
# without first confirming Report-Only shows zero unexpected violations.
CONTENT_SECURITY_POLICY_REPORT_ONLY = {
    'DIRECTIVES': {
        'default-src': ["'self'"],
        # 'unsafe-inline' reflects current reality (the mobile-menu toggle,
        # dashboard polling, and Chart.js setup are all inline, un-nonced
        # scripts today) — tightening this to nonces is follow-up work, not
        # part of standing this policy up in Report-Only mode.
        'script-src': [
            "'self'", "'unsafe-inline'",
            'https://cdn.jsdelivr.net',  # Chart.js (dashboard sales chart)
        ],
        'style-src': ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com'],
        'font-src': ["'self'", 'https://fonts.gstatic.com'],
        'img-src': ["'self'", 'data:'],
        'connect-src': ["'self'"],
    },
}


ROOT_URLCONF = 'vulor.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            BASE_DIR / "frontend" / "templates",
            ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart_context',
            ],
        },
    },
]
if DEBUG:
    TEMPLATES[0]['OPTIONS']['context_processors'].append(   
        'django.template.context_processors.debug',
    )

WSGI_APPLICATION = 'vulor.wsgi.application'

# Password validation
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

# Debug settings
if DEBUG:
    CSRF_TRUSTED_ORIGINS = [
        "https://*.ngrok-free.app",
        "https://*.ngrok-free.dev",
    ]
else:
    # Django's wildcard subdomain matching (https://*.example.com) never
    # matches the apex host itself, so a wildcard-only list here silently
    # fails CSRF for the bare production domain. Read the real origin(s)
    # from env instead.
    CSRF_TRUSTED_ORIGINS = [
        origin.strip()
        for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",")
        if origin.strip()
    ]
# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True



# Default primary key
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom user model
AUTH_USER_MODEL = 'accounts.CustomUser'

# AllAuth Configuration
SITE_ID = 1
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'mandatory'
# Signup is two fields (email + password): allauth auto-generates the
# username and the confirm-password field is dropped.
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = False
# Clicking the verification link logs the user in (same browser) — no
# re-typing credentials after confirming.
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_UNIQUE_EMAIL = True
# Registration is intentionally open. /accounts/register/ is the single
# signup door (accounts.views.RegisterView, a thin subclass of allauth's
# SignupView on the project template); allauth's own /accounts/signup/ URL
# redirects there.
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[VULOR] '
# Allauth emails (verification, password reset) are sent synchronously inside
# the request; the resilient adapter logs SMTP failures instead of 500ing the
# signup/reset flow after the user row is already committed.
ACCOUNT_ADAPTER = 'accounts.adapter.ResilientAccountAdapter'

#login/logout redirects
ACCOUNT_SIGNUP_REDIRECT_URL = '/'
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = False
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Bank transfer configuration — shown to customers at checkout
BANK_TRANSFER_BANK_NAME = os.getenv('BANK_TRANSFER_BANK_NAME', '')
BANK_TRANSFER_ACCOUNT_NAME = os.getenv('BANK_TRANSFER_ACCOUNT_NAME', '')
BANK_TRANSFER_ACCOUNT_NUMBER = os.getenv('BANK_TRANSFER_ACCOUNT_NUMBER', '')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_FORMS = {
    'signup': 'accounts.forms.SignupForm',
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = os.getenv("EMAIL_PORT", 587)
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True") == "True"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "False") == "True"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "")

EMAIL_SUBJECT_PREFIX = '[VULOR] '


#admin dashboard settings

ADMIN_SITE_HEADER = "VULOR Admin Dashboard"
ADMIN_SITE_TITLE = "VULOR Admin"
ADMIN_INDEX_TITLE = "Welcome to VULOR Dashboard"
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")

# Static files
STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'frontend' / 'static',
]

STATIC_ROOT = BASE_DIR / 'staticfiles'

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'



# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = os.getenv('MEDIA_ROOT', os.path.join(BASE_DIR, 'media'))

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB


#Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        # stdout, not a local file: Render's filesystem is ephemeral, so a
        # FileHandler here silently lost every login-event record on each
        # restart/redeploy. Container-native platforms capture stdout for
        # log aggregation; a local file does not survive to be aggregated.
        'auth_console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.security.login': {
            'handlers': ['auth_console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

if DEBUG:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.filebased.FileBasedCache',
            'LOCATION': BASE_DIR / 'django_cache',
        }
    }
elif os.getenv('REDIS_URL'):
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.getenv('REDIS_URL'),
        }
    }
else:
    # No Redis is deployed today, and django-ratelimit reads this cache too
    # — hardcoding RedisCache here made register/login/checkout/receipt
    # upload all 500 in production. LocMemCache makes rate limits
    # per-process rather than global, which is accepted at current scale.
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }


# Celery config
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"

# Customer emails are sent synchronously unless a Celery worker + broker
# actually run in the environment (the Render web service has neither).
EMAIL_ASYNC_ENABLED = os.getenv('EMAIL_ASYNC_ENABLED', 'False') == 'True'
