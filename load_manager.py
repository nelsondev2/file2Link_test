import threading
import psutil
import logging
import sys
from config import MAX_CONCURRENT_PROCESSES, CPU_USAGE_LIMIT

logger = logging.getLogger(__name__)

class LoadManager:
    def __init__(self):
        self.active_processes = 0
        self.max_processes = MAX_CONCURRENT_PROCESSES
        self.lock = threading.Lock()
    
    def can_start_process(self):
        """Verifica si se puede iniciar un nuevo proceso pesado"""
        with self.lock:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
            except:
                cpu_percent = 0
            
            if cpu_percent > CPU_USAGE_LIMIT:
                return False, f"CPU sobrecargada ({cpu_percent:.1f}%). Espera un momento."
            
            if self.active_processes >= self.max_processes:
                return False, "Ya hay un proceso en ejecución. Espera a que termine."
            
            self.active_processes += 1
            return True, f"Proceso iniciado (CPU: {cpu_percent:.1f}%)"
    
    def finish_process(self):
        """Marca un proceso como terminado"""
        with self.lock:
            self.active_processes = max(0, self.active_processes - 1)
    
    def get_status(self):
        """Obtiene estado actual del sistema"""
        with self.lock:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
            except:
                cpu_percent = 0
                memory_percent = 0
            
            return {
                'active_processes': self.active_processes,
                'max_processes': self.max_processes,
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'can_accept_work': self.active_processes < self.max_processes and cpu_percent < CPU_USAGE_LIMIT
            }

load_manager = LoadManager()
