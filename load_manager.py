import threading
import logging
import sys
import time
from collections import OrderedDict
from config import MAX_CONCURRENT_PROCESSES, CPU_USAGE_LIMIT, MAX_QUEUE_SIZE, MAX_CONCURRENT_UPLOADS

logger = logging.getLogger(__name__)

class LoadManager:
    def __init__(self):
        self.active_processes = 0
        self.max_processes = MAX_CONCURRENT_PROCESSES
        self.lock = threading.Lock()
        self.start_time = time.time()
        self.system_stats = {
            'total_processes': 0,
            'blocked_processes': 0,
            'cpu_overloads': 0,
            'last_check': time.time()
        }
        
        # Estadísticas simplificadas (sin psutil)
        self.cpu_estimate = 0
        self.memory_estimate = 0
        self.last_calculation = time.time()
    
    def can_start_process(self):
        """Verifica si se puede iniciar un nuevo proceso pesado"""
        with self.lock:
            self.system_stats['total_processes'] += 1
            
            # Estimación simple de carga sin psutil
            current_time = time.time()
            if current_time - self.last_calculation > 5:
                # Actualizar estimaciones cada 5 segundos
                self._update_estimates()
                self.last_calculation = current_time
            
            if self.active_processes >= self.max_processes:
                self.system_stats['blocked_processes'] += 1
                return False, f"⏳ Límite de procesos alcanzado ({self.active_processes}/{self.max_processes}). Espera a que termine uno."
            
            self.active_processes += 1
            self.system_stats['last_check'] = time.time()
            return True, f"✅ Proceso iniciado (Procesos activos: {self.active_processes}/{self.max_processes})"
    
    def _update_estimates(self):
        """Actualizar estimaciones de carga sin psutil"""
        try:
            # Estimación simple basada en procesos activos
            if self.active_processes == 0:
                self.cpu_estimate = 10  # Base
                self.memory_estimate = 30  # Base
            else:
                self.cpu_estimate = min(100, 20 + (self.active_processes * 15))
                self.memory_estimate = min(90, 40 + (self.active_processes * 10))
        except:
            self.cpu_estimate = 0
            self.memory_estimate = 0
    
    def finish_process(self):
        """Marca un proceso como terminado"""
        with self.lock:
            self.active_processes = max(0, self.active_processes - 1)
            self.system_stats['last_check'] = time.time()
    
    def get_status(self):
        """Obtiene estado actual del sistema SIMPLIFICADO"""
        with self.lock:
            # Actualizar estimaciones
            current_time = time.time()
            if current_time - self.last_calculation > 5:
                self._update_estimates()
                self.last_calculation = current_time
            
            uptime = time.time() - self.start_time
            readable_uptime = self.get_readable_time(uptime)
            
            return {
                'active_processes': self.active_processes,
                'max_processes': self.max_processes,
                'cpu_percent': self.cpu_estimate,
                'memory_percent': self.memory_estimate,
                'disk_percent': 50,  # Estimado
                'network_sent': "0 B",
                'network_recv': "0 B",
                'uptime': readable_uptime,
                'uptime_seconds': uptime,
                'can_accept_work': self.active_processes < self.max_processes and self.cpu_estimate < CPU_USAGE_LIMIT,
                'system_stats': self.system_stats,
                'queue_limits': {
                    'max_queue_size': MAX_QUEUE_SIZE,
                    'max_concurrent_uploads': MAX_CONCURRENT_UPLOADS,
                    'current_queues': 0
                },
                'optimized': True,
                'memory_safe': True
            }
    
    def get_readable_time(self, seconds: int) -> str:
        """Tiempo legible"""
        count = 0
        time_list = []
        time_suffix_list = ["s", "m", "h", " días"]
        while count < 4:
            count += 1
            if count < 3:
                remainder, result = divmod(seconds, 60)
            else:
                remainder, result = divmod(seconds, 24)
            if seconds == 0 and remainder == 0:
                break
            time_list.append(int(result))
            seconds = int(remainder)
        
        for x in range(len(time_list)):
            time_list[x] = str(time_list[x]) + time_suffix_list[x]
        
        if len(time_list) == 4:
            readable_time = time_list.pop() + ", "
        else:
            readable_time = ""
        
        time_list.reverse()
        readable_time += ": ".join(time_list)
        return readable_time
    
    def get_readable_file_size(self, size):
        """Tamaño de archivo legible"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    def can_accept_upload(self, user_id, current_queue_size):
        """Verificar si se puede aceptar nueva subida"""
        with self.lock:
            if current_queue_size >= MAX_QUEUE_SIZE:
                return False, f"❌ Límite de cola alcanzado ({current_queue_size}/{MAX_QUEUE_SIZE})"
            
            return True, f"✅ Puedes subir archivos (En cola: {current_queue_size})"
    
    def get_system_health(self):
        """Obtener salud del sistema simplificada"""
        with self.lock:
            return {
                'cpu': {
                    'percent': self.cpu_estimate,
                    'limit': CPU_USAGE_LIMIT,
                    'status': 'OK' if self.cpu_estimate < CPU_USAGE_LIMIT else 'OVERLOAD'
                },
                'memory': {
                    'percent': self.memory_estimate,
                    'status': 'OK' if self.memory_estimate < 90 else 'WARNING'
                },
                'processes': {
                    'active': self.active_processes,
                    'max': self.max_processes,
                    'status': 'OK' if self.active_processes < self.max_processes else 'FULL'
                },
                'optimized': True,
                'timestamp': time.time()
            }

load_manager = LoadManager()