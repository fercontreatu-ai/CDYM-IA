from pathlib import Path
import os
import sys
from dotenv import load_dotenv

FROZEN = bool(getattr(sys, "frozen", False))
BASE_DIR = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
RUNTIME_DIR = Path(sys.executable).resolve().parent if FROZEN else Path(__file__).resolve().parent.parent
PROJECT_ROOT = RUNTIME_DIR
load_dotenv(RUNTIME_DIR / ".env")
load_dotenv(PROJECT_ROOT / ".env")

SECRET_KEY=os.getenv('DJANGO_SECRET_KEY','dev-only')
DEBUG=os.getenv('DJANGO_DEBUG','False').lower() in {'1','true','yes'}
ALLOWED_HOSTS=[x.strip() for x in os.getenv('DJANGO_ALLOWED_HOSTS','127.0.0.1,localhost').split(',') if x.strip()]
INSTALLED_APPS=['django.contrib.admin','django.contrib.auth','django.contrib.contenttypes','django.contrib.sessions','django.contrib.messages','django.contrib.staticfiles','desconexiones']
MIDDLEWARE=['django.middleware.security.SecurityMiddleware','django.contrib.sessions.middleware.SessionMiddleware','django.middleware.common.CommonMiddleware','django.middleware.csrf.CsrfViewMiddleware','django.contrib.auth.middleware.AuthenticationMiddleware','django.contrib.messages.middleware.MessageMiddleware','django.middleware.clickjacking.XFrameOptionsMiddleware']
ROOT_URLCONF='config.urls'
TEMPLATES=[{'BACKEND':'django.template.backends.django.DjangoTemplates','DIRS':[BASE_DIR/'templates'],'APP_DIRS':True,'OPTIONS':{'context_processors':['django.template.context_processors.request','django.contrib.auth.context_processors.auth','django.contrib.messages.context_processors.messages']}}]
WSGI_APPLICATION='config.wsgi.application'
ASGI_APPLICATION='config.asgi.application'
DATABASE_FILE=Path(os.getenv('CDYM_IA_DATABASE',os.getenv('CDYM_DATABASE',str(PROJECT_ROOT/'alimentadores_reducida.sqlite')))).expanduser().resolve()
DATA_DIR=Path(os.getenv('CDYM_IA_DATA_DIR',str(PROJECT_ROOT/'datos'))).expanduser().resolve()
CDYM_EDITION='IA'
DATABASES={'default':{'ENGINE':'django.db.backends.sqlite3','NAME':DATABASE_FILE,'OPTIONS':{'timeout':60}}}
AUTH_PASSWORD_VALIDATORS=[]
LANGUAGE_CODE='es-co'; TIME_ZONE='America/Bogota'; USE_I18N=True; USE_TZ=True
STATIC_URL='static/'; STATICFILES_DIRS=[BASE_DIR/'static']
DEFAULT_AUTO_FIELD='django.db.models.BigAutoField'; LOGIN_URL='/admin/login/'
