import os
import sqlite3
import sys
import threading
import time
import webbrowser
from pathlib import Path
from socketserver import ThreadingMixIn
from wsgiref.simple_server import WSGIServer, WSGIRequestHandler, make_server

RUNTIME_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
os.chdir(RUNTIME_DIR)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

import django
django.setup()
from django.conf import settings
from django.core.management import call_command
from django.contrib.staticfiles.handlers import StaticFilesHandler
from config.wsgi import application

class ThreadingServer(ThreadingMixIn, WSGIServer):
    daemon_threads = True


TABLA_ESQUEMA_CDYMS = "desconexiones_catalogoconductorcens"


def inicializar_esquema_si_falta():
    """Crea las tablas internas una sola vez en bases históricas sin esquema CDYMS."""
    with sqlite3.connect(settings.DATABASE_FILE, timeout=60) as conexion:
        existe = conexion.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
            (TABLA_ESQUEMA_CDYMS,),
        ).fetchone()
    if existe:
        return
    print("Inicializando por única vez las tablas internas de CDYMS...")
    call_command("migrate", interactive=False, verbosity=1)


def abrir_navegador(url):
    # El servidor ya queda creado inmediatamente después de lanzar el hilo.
    # Una pausa corta evita la carrera sin retrasar perceptiblemente la UI.
    time.sleep(0.2)
    webbrowser.open(url)


def main():
    if not Path(settings.DATABASE_FILE).exists():
        raise SystemExit(f"No se encontró la base de datos junto al ejecutable: {settings.DATABASE_FILE}")
    inicializar_esquema_si_falta()
    host = os.getenv("CDYM_HOST", "127.0.0.1")
    port = int(os.getenv("CDYM_PORT", "8000"))
    url = f"http://{host}:{port}"
    app = StaticFilesHandler(application)
    if os.getenv("CDYM_NO_BROWSER", "").lower() not in {"1", "true", "yes"}:
        threading.Thread(target=abrir_navegador, args=(url,), daemon=True).start()
    print(f"CDYM disponible en {url}")
    print(f"Base de datos: {settings.DATABASE_FILE}")
    print(f"Configuración: {RUNTIME_DIR / '.env'}")
    with make_server(host, port, app, server_class=ThreadingServer, handler_class=WSGIRequestHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("Servidor finalizado.")

if __name__ == "__main__":
    main()
