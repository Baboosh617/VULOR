import os
from pathlib import Path
import environ
import dj_database_url



# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

USE_TZ = True
TIME_ZONE = 'UTC'

# Initialize environment variables
env = environ.Env()
environ.Env.read_env(os.path.join(BASE_DIR, '.env'))

# Debug settings and Allowed hosts
SECRET_KEY = 'django-insecure-development-key-1234567890-change-in-production'
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'victorious-ivan-uncharily.ngrok-free.dev', 'vulor.com', 'vulor.onrender.com', 'vulor-1.onrender.com']

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





INSTALLED_APPS += ["channels"]

# Channels config

ASGI_APPLICATION = "backend.asgi.application"

# Optional: In-memory channel layer for development

CHANNEL_LAYERS = {


    "default": {


        "BACKEND": "channels.layers.InMemoryChannelLayer",


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
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'cart.context_processors.cart_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'vulor.wsgi.application'

# This checks if we're running on Render (production) or locally
ON_RENDER = os.environ.get('ON_RENDER', 'False') == 'True'

DEBUG = not ON_RENDER

if ON_RENDER:
    # Production: Use PostgreSQL on Render
    DATABASES = {
        'default': dj_database_url.config(
            default=os.environ.get('DATABASE_URL'),
            conn_max_age=600,
            ssl_require=True,

            options={
                'connect_timeout': 10,  # Fail fast if DB is slow
                'application_name': 'vulor-app',
            },
        )
    }
else:
    # Development: Use SQLite locally (no PostgreSQL needed)
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }

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

CSRF_TRUSTED_ORIGINS = [
    "https://*.vulor.onrender.com",
    "https://*.vulor.com",
    "https://*.vulor-1.onrender.com",
    "https://*.ngrok-free.app",
    "https://*.ngrok-free.dev",
    "https://*.victorious-ivan-uncharily.ngrok-free.dev",
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
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_LOGOUT_REDIRECT_URL = '/products/'
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = '[VULOR] '

#social account settings
SOCIALACCOUNT_QUERY_EMAIL = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_STORE_TOKENS = False
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_LOGIN_ON_GET = True

#login/logout redirects
LOGIN_REDIRECT_URL = '/'
ACCOUNT_LOGOUT_ON_GET = True
LOGOUT_REDIRECT_URL = '/'
LOGIN_URL = '/accounts/login/'



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


# Custom error handlers
if not DEBUG:
    # Production error handlers
    handler404 = 'error_pages.views.custom_404'  
    handler500 = 'error_pages.views.custom_500'
    handler403 = 'error_pages.views.custom_403'
    handler400 = 'error_pages.views.custom_400'
