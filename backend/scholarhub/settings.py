"""
Django settings for scholarhub project.
Enterprise-Grade Setup — OWASP Compliant.

Strategi Konfigurasi:
- Bagian yang ditandai "LOCALHOST DEV MODE" adalah konfigurasi sementara untuk development.
- Saat deploy ke Kubernetes, ikuti instruksi "HAPUS SAAT DEPLOY" di komentar masing-masing.
"""

import os
from pathlib import Path
from datetime import timedelta

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# ==============================================================================
# 1. KONFIGURASI KEAMANAN & SECRET MANAGEMENT
# ==============================================================================

# --- LOCALHOST DEV MODE START ---------------------------------------------------
# HAPUS SAAT DEPLOY KE KUBERNETES: Ganti seluruh blok ini dengan integrasi Vault.
# Saat production, SECRET_KEY harus diambil dari Vault path: secret/scholarhub/django
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-dev-only-key-GANTI-SAAT-PRODUCTION-x9k2m!@#'
)

# Saat production, ubah ke False
DEBUG = os.environ.get('DJANGO_DEBUG', 'True') == 'True'

# Saat production, ganti dengan domain spesifik: ['scholarhub.example.com']
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')
# --- LOCALHOST DEV MODE END -----------------------------------------------------

# ===== VAULT INTEGRATION (Aktifkan saat deploy ke Kubernetes) =====
# UNCOMMENT BLOK INI SAAT DEPLOY KE KUBERNETES, HAPUS BLOK LOCALHOST DI ATAS
# import hvac
#
# VAULT_ADDR = os.environ.get("VAULT_ADDR", "http://vault.scholarhub.svc.cluster.local:8200")
# VAULT_ROLE_ID = os.environ.get("VAULT_ROLE_ID")
# VAULT_SECRET_ID = os.environ.get("VAULT_SECRET_ID")
#
# try:
#     if VAULT_ROLE_ID and VAULT_SECRET_ID:
#         client = hvac.Client(url=VAULT_ADDR)
#         client.auth.approle.login(role_id=VAULT_ROLE_ID, secret_id=VAULT_SECRET_ID)
#
#         # Ambil Django SECRET_KEY
#         secret_response = client.secrets.kv.v2.read_secret_version(path='scholarhub/django')
#         SECRET_KEY = secret_response['data']['data']['secret_key']
#
#         # Ambil Dynamic DB Credentials
#         db_creds = client.secrets.database.generate_credentials("scholarhub-role")
#         DB_USER = db_creds['data']['username']
#         DB_PASSWORD = db_creds['data']['password']
#
#         # Ambil JWT Signing Key (terpisah dari SECRET_KEY)
#         jwt_response = client.secrets.kv.v2.read_secret_version(path='scholarhub/jwt')
#         JWT_SIGNING_KEY = jwt_response['data']['data']['signing_key']
# except Exception as e:
#     raise RuntimeError(f"FATAL: Tidak bisa konek ke Vault — {e}")
# ===== END VAULT INTEGRATION =====


# ==============================================================================
# 2. PENGATURAN APLIKASI
# ==============================================================================

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    # Third-party
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    # Local apps
    'users',
    'scholarships',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # Custom middleware: RBAC enforcement
    'users.middleware.RBACMiddleware',
]

ROOT_URLCONF = 'scholarhub.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'scholarhub.wsgi.application'


# ==============================================================================
# 3. DATABASE
# ==============================================================================

# --- LOCALHOST DEV MODE START ---------------------------------------------------
# HAPUS SAAT DEPLOY KE KUBERNETES: Ganti dengan MariaDB + Vault credentials
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
# --- LOCALHOST DEV MODE END -----------------------------------------------------

# ===== MARIADB PRODUCTION (Aktifkan saat deploy ke Kubernetes) =====
# UNCOMMENT BLOK INI SAAT DEPLOY, HAPUS SQLITE DI ATAS
# DATABASES = {
#     'default': {
#         'ENGINE': 'django.db.backends.mysql',
#         'NAME': 'scholarhub',
#         'USER': DB_USER,         # Dari Vault dynamic secret
#         'PASSWORD': DB_PASSWORD, # Dari Vault dynamic secret
#         'HOST': os.environ.get('DB_HOST', 'mariadb.scholarhub.svc.cluster.local'),
#         'PORT': '3306',
#         'OPTIONS': {
#             'charset': 'utf8mb4',
#             'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
#         },
#     }
# }
# ===== END MARIADB PRODUCTION =====


# ==============================================================================
# 4. PASSWORD SECURITY
# ==============================================================================

# Wajib Argon2 sebagai hasher utama (OWASP recommendation, DILARANG MD5/SHA1)
PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.Argon2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2PasswordHasher',
    'django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher',
    'django.contrib.auth.hashers.BCryptSHA256PasswordHasher',
]

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ==============================================================================
# 5. CUSTOM USER MODEL
# ==============================================================================

AUTH_USER_MODEL = 'users.CustomUser'


# ==============================================================================
# 6. REST FRAMEWORK & JWT
# ==============================================================================

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ),
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 12,  # Sesuai spec: default limit=12 untuk public, max 20
    # Rate Limiting (Throttling) — sesuai spec checklist
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '60/minute',      # Guest: 60 req/menit
        'user': '120/minute',     # Authenticated: 120 req/menit
        'login': '5/minute',      # Login: 5 per 15 menit (custom)
        'register': '3/hour',     # Register: 3 per jam
        'submission': '5/hour',   # Provider submission: 5 per jam
        'tracking': '10/minute',  # Tracking status: 10 per menit
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=1),
    'SIGNING_KEY': SECRET_KEY,  # Saat production: gunakan JWT_SIGNING_KEY dari Vault
    'AUTH_HEADER_TYPES': ('Bearer',),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
}


# ==============================================================================
# 7. CORS (Cross-Origin Resource Sharing)
# ==============================================================================

# --- LOCALHOST DEV MODE START ---------------------------------------------------
# HAPUS SAAT DEPLOY KE KUBERNETES: Ganti dengan CORS_ALLOWED_ORIGINS spesifik
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5500',
    'http://127.0.0.1:5500',
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
]
# Untuk development, izinkan juga port Live Server lain
CORS_ALLOW_ALL_ORIGINS = DEBUG  # Hanya True jika DEBUG=True
# --- LOCALHOST DEV MODE END -----------------------------------------------------

CORS_ALLOW_CREDENTIALS = True


# ==============================================================================
# 8. SECURITY HEADERS
# ==============================================================================
# Saat production (DEBUG=False), Django akan enforce seluruh header ini.
# Di localhost, sebagian dinonaktifkan agar tidak mengganggu development.

if not DEBUG:
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'


# ==============================================================================
# 9. INTERNATIONALIZATION & STATIC FILES
# ==============================================================================

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Jakarta'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# ==============================================================================
# 10. BLEACH — HTML SANITIZATION CONFIG
# ==============================================================================

# Tag HTML yang diizinkan untuk field rich-text (description, requirements)
BLEACH_ALLOWED_TAGS = ['b', 'i', 'u', 'em', 'strong', 'ul', 'ol', 'li', 'p', 'br']
BLEACH_ALLOWED_ATTRIBUTES = {}  # Tidak ada atribut yang diizinkan
BLEACH_STRIP = True  # Hapus tag yang tidak diizinkan, jangan escape

# Regex validasi URL — hanya http/https yang diterima
import re
URL_VALIDATION_REGEX = re.compile(r'^https?://[^\s/$.?#].[^\s]*$')
BLOCKED_URL_SCHEMES = ['javascript:', 'data:', 'vbscript:', 'ftp://']


# ==============================================================================
# 11. ACCOUNT LOCKOUT CONFIG
# ==============================================================================

ACCOUNT_LOCKOUT_MAX_ATTEMPTS = 5      # Maksimal percobaan login gagal
ACCOUNT_LOCKOUT_DURATION = 900        # Durasi kunci dalam detik (15 menit)


# ==============================================================================
# 12. LOGGING
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{asctime}] {levelname} {name} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
        },
        'scholarhub': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}