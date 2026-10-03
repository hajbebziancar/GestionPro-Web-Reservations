"""Monte le relais privé sans compromettre le démarrage du site public."""
import os
import threading
from pathlib import Path
from gestionpro_android.relay import Relay

class MobileMount:
    def __init__(self):
        self.relay = None
        self.lock = threading.Lock()
    def __call__(self, environ, start_response):
        if self.relay is None:
            with self.lock:
                if self.relay is None:
                    try:
                        base = Path(os.environ.get('GESTIONPRO_DATA_DIR', '/data'))
                        database = os.environ.get('GP_RELAY_DB', str(base / 'gestionpro_mobile.sqlite3'))
                        self.relay = Relay(database=database)
                    except Exception:
                        body = b'Application mobile non configuree. Definir GP_MOBILE_TOKEN, GP_PC_TOKEN et GP_RELAY_DB dans Railway.'
                        start_response('503 Service Unavailable', [('Content-Type', 'text/plain; charset=utf-8'), ('Content-Length', str(len(body))), ('Cache-Control', 'no-store')])
                        return [body]
        return self.relay(environ, start_response)
