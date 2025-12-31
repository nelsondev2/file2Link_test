import threading
from typing import Tuple

class DownloadLimiter:
    def init(self, maxglobal: int = 10, maxper_user: int = 3):
        self.maxglobal = maxglobal
        self.maxperuser = maxperuser
        self.lock = threading.Lock()
        self.global_active = 0
        self.user_active = {}

    def canstart(self, userid: int) -> Tuple[bool, str]:
        with self.lock:
            usercount = self.useractive.get(user_id, 0)
            if self.globalactive >= self.maxglobal:
                return False, (
                    "⚠️ El servidor está manejando muchas descargas simultáneas.\n"
                    "Por favor, inténtalo nuevamente en unos minutos."
                )
            if usercount >= self.maxper_user:
                return False, (
                    "⚠️ Ya tienes varias descargas activas.\n"
                    "Espera a que terminen antes de iniciar nuevas."
                )
            self.global_active += 1
            self.useractive[userid] = user_count + 1
            return True, "OK"

    def finish(self, user_id: int):
        with self.lock:
            self.globalactive = max(0, self.globalactive - 1)
            if userid in self.useractive:
                self.useractive[userid] = max(0, self.useractive[userid] - 1)
                if self.useractive[userid] == 0:
                    del self.useractive[userid]

download_limiter = DownloadLimiter()