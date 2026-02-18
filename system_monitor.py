"""
Monitor de recursos del servidor.

Controla que no se lancen procesos pesados (empaquetado)
cuando el sistema ya está bajo carga elevada.
"""
import logging
import threading

import psutil

from config import CPU_LIMIT_PERCENT, MAX_CONCURRENT_PACKS

logger = logging.getLogger(__name__)


class SystemMonitor:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active = 0
        self.max_packs = MAX_CONCURRENT_PACKS

    # ── Procesos pesados ──────────────────────────────────────────────────────

    def request_slot(self) -> tuple[bool, str]:
        """
        Solicita un slot para un proceso pesado.
        Devuelve (concedido, mensaje).
        """
        with self._lock:
            cpu = psutil.cpu_percent(interval=0.5)
            if cpu > CPU_LIMIT_PERCENT:
                return False, (
                    f"El servidor está muy ocupado ahora mismo (CPU al {cpu:.0f}%). "
                    "Inténtalo de nuevo en unos minutos."
                )
            if self._active >= self.max_packs:
                return False, (
                    "Ya hay un proceso en marcha. "
                    "Espera a que termine antes de lanzar otro."
                )
            self._active += 1
            return True, "OK"

    def release_slot(self) -> None:
        """Libera el slot ocupado por un proceso pesado."""
        with self._lock:
            self._active = max(0, self._active - 1)

    # ── Estado general ────────────────────────────────────────────────────────

    def status(self) -> dict:
        with self._lock:
            cpu = psutil.cpu_percent(interval=0.5)
            mem = psutil.virtual_memory()
            return {
                "active_packs": self._active,
                "max_packs": self.max_packs,
                "cpu_percent": round(cpu, 1),
                "memory_percent": round(mem.percent, 1),
                "available": self._active < self.max_packs and cpu < CPU_LIMIT_PERCENT,
            }


monitor = SystemMonitor()
