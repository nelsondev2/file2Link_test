import os
import time
import threading
from config import BASEDIR, MAXFILE_SIZE
from fileservice import fileservice
from logservice import systemlogger

class CleanupService:
    def init(self, interval_seconds: int = 6 * 3600):
        self.interval = interval_seconds
        self._stop = False
        self.thread = threading.Thread(target=self.runloop, daemon=True)

    def start(self):
        system_logger.info("Iniciando servicio de limpieza automática...")
        self.thread.start()

    def stop(self):
        self._stop = True

    def runloop(self):
        while not self._stop:
            try:
                self.run_cleanup()
            except Exception as e:
                systemlogger.error(f"Error en limpieza automática: {e}", excinfo=True)
            time.sleep(self.interval)

    def run_cleanup(self):
        system_logger.info("Ejecutando limpieza de archivos y metadata...")
        total_removed = 0

        if not os.path.exists(BASE_DIR):
            systemlogger.info("BASEDIR no existe, nada que limpiar.")
            return

        for useriddir in os.listdir(BASE_DIR):
            userpath = os.path.join(BASEDIR, useriddir)
            if not os.path.isdir(user_path):
                continue

            for folder in ["downloads", "packed"]:
                folderpath = os.path.join(userpath, folder)
                if not os.path.exists(folder_path):
                    continue

                for filename in os.listdir(folder_path):
                    filepath = os.path.join(folderpath, filename)
                    if not os.path.isfile(file_path):
                        continue

                    try:
                        size = os.path.getsize(file_path)
                        if size > MAXFILESIZE:
                            os.remove(file_path)
                            total_removed += 1
                            system_logger.warning(
                                f"Archivo eliminado por exceder tamaño máximo: {file_path} ({size} bytes)"
                            )
                    except Exception as e:
                        systemlogger.error(f"Error evaluando archivo {filepath}: {e}")

        systemlogger.info(f"Limpieza completada. Archivos eliminados: {totalremoved}")

cleanup_service = CleanupService()