"""
Django settings para el proyecto "proyectocabañas".
Archivo listo para pegar en proyectocabañas/settings.py

Notas rápidas:
- Ajusta SECRET_KEY y ALLOWED_HOSTS antes de pasar a producción.
- Si usas MySQL asegúrate de instalar 'mysqlclient' (pip install mysqlclient).
- Para ImageField instala Pillow: pip install Pillow
- Asegúrate de añadir en tu proyectocabañas/urls.py el servicio de media en DEBUG:
    from django.conf import settings
    from django.conf.urls.static import static
    if settings.DEBUG:
        urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
"""

from pathlib import Path
import os

# Ruta base del proyecto (manage.py está en BASE_DIR)
BASE_DIR = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Configuración básica
# ---------------------------------------------------------------------------
# SECURITY WARNING: mantener esto secreto en producción (usar variables de entorno)
SECRET_KEY = 'django-insecure-%66s$2=#=bh2a^^h17gjr%!oh7+%ysg3_60oyd7u=+cs(z%#mv'

# DEBUG = True SOLO en desarrollo
DEBUG = True

# Hosts permitidos en producción deben añadirse aquí
ALLOWED_HOSTS = ['localhost', '127.0.0.1']

# ---------------------------------------------------------------------------
# Aplicaciones instaladas
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    # Apps Django
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Tu app
    'core',
]

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'proyectocabañas.urls'

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [
            # Si tienes plantillas globales fuera de las apps: BASE_DIR / 'templates',
        ],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',      # útil en dev
                'django.template.context_processors.request',
                'django.template.context_processors.i18n',
                'django.template.context_processors.media',
                'django.template.context_processors.static',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'proyectocabañas.wsgi.application'

# ---------------------------------------------------------------------------
# Base de datos
# ---------------------------------------------------------------------------
# Configuración para MySQL (ajusta credenciales según tu entorno).
# Si prefieres SQLite en desarrollo, cambia ENGINE a 'django.db.backends.sqlite3'
# y pon NAME = BASE_DIR / 'db.sqlite3'
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'bd_cabañas',
        'USER': 'root',
        'PASSWORD': '123456',
        'HOST': 'localhost',
        'PORT': '3306',
        # puedes añadir OPTIONS si lo necesitas
        # 'OPTIONS': {'init_command': "SET sql_mode='STRICT_TRANS_TABLES'"},
    }
}

# ---------------------------------------------------------------------------
# Validadores de contraseña (puedes mantenerlos)
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# ---------------------------------------------------------------------------
# Internacionalización y zona horaria
# ---------------------------------------------------------------------------
LANGUAGE_CODE = 'es-cl'            # español Chile (ajusta si lo prefieres)
TIME_ZONE = 'America/Santiago'     # horario local de Chile (ajusta si necesario)
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Archivos estáticos (CSS, JS, imágenes públicas)
# ---------------------------------------------------------------------------
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'   # para collectstatic en producción

# Apuntamos explícitamente al static de la app core (evita el warning W004)
STATICFILES_DIRS = [
    BASE_DIR / 'core' / 'static',
]

# ---------------------------------------------------------------------------
# Archivos subidos por usuarios (media) - necesarios para ImageField
# ---------------------------------------------------------------------------
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'


# ---------------------------------------------------------------------------
# Configuración adicional
# ---------------------------------------------------------------------------
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Logging básico para desarrollo (te ayudará a ver errores en la consola)
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {'class': 'logging.StreamHandler',},
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG' if DEBUG else 'ERROR',
            'propagate': False,
        },
    },
}

# ---------------------------------------------------------------------------
# Smtp
# ---------------------------------------------------------------------------
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'ing.ignaciomadriaga@gmail.com'
EMAIL_HOST_PASSWORD = 'dhkj ojhw akge jjcc'
DEFAULT_FROM_EMAIL = 'Cabañas Valle Central <no-reply@cabanas.local>'
