import threading
import psutil
import logging
import sys
import time
from config import MAX_CONCURRENT_PROCESSES, CPU_USAGE_LIMIT, MAX_QUEUE_SIZE, MAX_CONCURRENT_UPLOADS

logger = logging.getLogger(__name__)

class LoadManager:
    def __init__(self):
        self.active_processes = 0
        self.max_processes = MAX_CONCURRENT_PROCESSES
        self.lock = threading.Lock()
        self.start_time = time.time()  # NUEVO: Para uptime
        self.system_stats = {  # NUEVO: Estadísticas como primer bot
            'total_processes': 0,
            'blocked_processes': 0,
            'cpu_overloads': 0,
            'last_check': time.time()
        }
    
    def can_start_process(self):
        """Verifica si se puede iniciar un nuevo proceso pesado"""
        with self.lock:
            self.system_stats['total_processes'] += 1
            
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
            except:
                cpu_percent = 0
                memory_percent = 0
            
            # NUEVO: Lógica mejorada como primer bot
            if cpu_percent > CPU_USAGE_LIMIT:
                self.system_stats['cpu_overloads'] += 1
                self.system_stats['last_check'] = time.time()
                return False, f"🚨 CPU sobrecargada ({cpu_percent:.1f}% > {CPU_USAGE_LIMIT}%). Espera un momento."
            
            if memory_percent > 90:
                return False, f"🚨 Memoria crítica ({memory_percent:.1f}%). Sistema sobrecargado."
            
            if self.active_processes >= self.max_processes:
                self.system_stats['blocked_processes'] += 1
                return False, f"⏳ Límite de procesos alcanzado ({self.active_processes}/{self.max_processes}). Espera a que termine uno."
            
            self.active_processes += 1
            self.system_stats['last_check'] = time.time()
            return True, f"✅ Proceso iniciado (CPU: {cpu_percent:.1f}%, Mem: {memory_percent:.1f}%)"
    
    def finish_process(self):
        """Marca un proceso como terminado"""
        with self.lock:
            self.active_processes = max(0, self.active_processes - 1)
            self.system_stats['last_check'] = time.time()
    
    def get_status(self):
        """Obtiene estado actual del sistema COMPLETO como primer bot"""
        with self.lock:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                memory_percent = memory.percent
                disk = psutil.disk_usage('/').percent
                
                # NUEVO: Estadísticas de red como primer bot
                net_io = psutil.net_io_counters()
                bytes_sent = net_io.bytes_sent
                bytes_recv = net_io.bytes_recv
                
                # NUEVO: Uptime calculado
                uptime = time.time() - self.start_time
                
            except Exception as e:
                logger.error(f"Error obteniendo stats del sistema: {e}")
                cpu_percent = 0
                memory_percent = 0
                disk = 0
                bytes_sent = 0
                bytes_recv = 0
                uptime = 0
            
            # NUEVO: Formato de tiempo legible como primer bot
            readable_uptime = self.get_readable_time(uptime)
            
            # NUEVO: Formato de bytes legible
            readable_sent = self.get_readable_file_size(bytes_sent)
            readable_recv = self.get_readable_file_size(bytes_recv)
            
            return {
                'active_processes': self.active_processes,
                'max_processes': self.max_processes,
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'disk_percent': disk,
                'network_sent': readable_sent,
                'network_recv': readable_recv,
                'uptime': readable_uptime,
                'uptime_seconds': uptime,
                'can_accept_work': self.active_processes < self.max_processes and cpu_percent < CPU_USAGE_LIMIT,
                'system_stats': self.system_stats,
                'queue_limits': {
                    'max_queue_size': MAX_QUEUE_SIZE,
                    'max_concurrent_uploads': MAX_CONCURRENT_UPLOADS,
                    'current_queues': 0  # Se actualizará desde telegram_handlers
                }
            }
    
    # NUEVO: Métodos auxiliares para formato como primer bot
    def get_readable_time(self, seconds: int) -> str:
        """Tiempo legible (del primer bot)"""
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
        """Tamaño de archivo legible (del primer bot)"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"
    
    # NUEVO: Métodos para gestión de cola mejorada
    def can_accept_upload(self, user_id, current_queue_size):
        """Verificar si se puede aceptar nueva subida (límites anti-abuso)"""
        with self.lock:
            if current_queue_size >= MAX_QUEUE_SIZE:
                return False, f"❌ Límite de cola alcanzado ({current_queue_size}/{MAX_QUEUE_SIZE})"
            
            try:
                cpu_percent = psutil.cpu_percent(interval=0.5)
            except:
                cpu_percent = 0
            
            if cpu_percent > CPU_USAGE_LIMIT:
                return False, f"⚠️ Sistema sobrecargado (CPU: {cpu_percent:.1f}%)"
            
            return True, f"✅ Puedes subir archivos (CPU: {cpu_percent:.1f}%)"
    
    def get_system_health(self):
        """Obtener salud del sistema para /status"""
        with self.lock:
            try:
                cpu_percent = psutil.cpu_percent(interval=1)
                memory = psutil.virtual_memory()
                disk = psutil.disk_usage('/')
                
                return {
                    'cpu': {
                        'percent': cpu_percent,
                        'limit': CPU_USAGE_LIMIT,
                        'status': 'OK' if cpu_percent < CPU_USAGE_LIMIT else 'OVERLOAD'
                    },
                    'memory': {
                        'percent': memory.percent,
                        'total_gb': memory.total / (1024**3),
                        'available_gb': memory.available / (1024**3),
                        'status': 'OK' if memory.percent < 90 else 'CRITICAL'
                    },
                    'disk': {
                        'percent': disk.percent,
                        'free_gb': disk.free / (1024**3),
                        'status': 'OK' if disk.percent < 90 else 'WARNING'
                    },
                    'processes': {
                        'active': self.active_processes,
                        'max': self.max_processes,
                        'status': 'OK' if self.active_processes < self.max_processes else 'FULL'
                    },
                    'timestamp': time.time()
                }
            except Exception as e:
                logger.error(f"Error en get_system_health: {e}")
                return {'error': str(e)}

load_manager = LoadManager()