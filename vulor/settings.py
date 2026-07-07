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

DEBUG = not ON_RENDER

if ON_RENDER:
    
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            ssl_require=True,

            options={
                'connect_timeout': 10,  
                'application_name': 'vulor-app',
            },
        )
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
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',

    
    # Local apps
    'products',
    'accounts',
    'cart',
    'orders',
    'error_pages',
    'payments',
    'dashboard',
    'django_recaptcha',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
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

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF =True


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
    CSRF_TRUSTED_ORIGINS = [
        "https://*.vulor.onrender.com",
        "https://*.vulor.com",
        "https://*.vulor-1.onrender.com",
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
ACCOUNT_LOGOUT_REDIRECT_URL = '/'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_ALLOW_REGISTRATION = False
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[VULOR] '

#social account settings
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

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

# Paystack Configuration
PAYSTACK_SECRET_KEY = os.getenv('PAYSTACK_SECRET_KEY')
PAYSTACK_PUBLIC_KEY = os.getenv('PAYSTACK_PUBLIC_KEY')
PAYSTACK_WEBHOOK_SECRET = os.getenv('PAYSTACK_WEBHOOK_SECRET')
SITE_URL = os.getenv('SITE_URL', 'http://127.0.0.1:8000')

# Google OAuth Configuration
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
        'APP': {
            'client_id': os.getenv('GOOGLE_CLIENT_ID', default=''),
            'secret': os.getenv('GOOGLE_SECRET_KEY', default=''),
            'key': ''
        }
    }
}

# Authentication backends
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]

ACCOUNT_FORMS = {
    'signup': 'accounts.forms.CustomUserCreationForm',
}
SOCIALACCOUNT_FORMS = {
    'signup': 'accounts.forms.CustomSocialSignupForm',
}

EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = os.getenv("EMAIL_PORT", 587)
EMAIL_USE_TLS = True  # IMPORTANT
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
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  # 10 MB


# Custom error handlers
if not DEBUG:
    # Production error handlers
    handler404 = 'error_pages.views.custom_404'  
    handler500 = 'error_pages.views.custom_500'
    handler403 = 'error_pages.views.custom_403'
    handler400 = 'error_pages.views.custom_400'

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
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'auth.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django.security.login': {
            'handlers': ['file'],
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
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': os.getenv('REDIS_URL', 'redis://localhost:6379'),
        }
    }


# Celery config
CELERY_BROKER_URL = "redis://127.0.0.1:6379/0"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"


SILENCED_SYSTEM_CHECKS = ['django_recaptcha.recaptcha_test_key_error']
