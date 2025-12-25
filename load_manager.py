import threading
import psutil
import logging
import time
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from contextlib import contextmanager

from config import config

logger = logging.getLogger(__name__)

@dataclass
class SystemMetrics:
    """Métricas del sistema en un momento dado"""
    cpu_percent: float
    memory_percent: float
    active_processes: int
    max_processes: int
    disk_usage_percent: Optional[float] = None
    timestamp: float = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
    
    @property
    def is_overloaded(self) -> bool:
        """Determina si el sistema está sobrecargado"""
        return (
            self.cpu_percent > config.CPU_USAGE_LIMIT or
            self.memory_percent > config.MEMORY_USAGE_LIMIT or
            self.active_processes >= self.max_processes
        )
    
    def to_dict(self) -> Dict:
        """Convierte a diccionario"""
        return {
            'active_processes': self.active_processes,
            'max_processes': self.max_processes,
            'cpu_percent': self.cpu_percent,
            'memory_percent': self.memory_percent,
            'disk_usage_percent': self.disk_usage_percent,
            'timestamp': self.timestamp,
            'can_accept_work': not self.is_overloaded,
            'is_overloaded': self.is_overloaded
        }


class LoadManager:
    """Gestor profesional de carga del sistema con métricas históricas"""
    
    def __init__(self):
        self.active_processes = 0
        self.max_processes = config.MAX_CONCURRENT_PROCESSES
        self.lock = threading.RLock()  # Reentrant lock para más flexibilidad
        self.metrics_history = []  # Historial de métricas (últimas 100)
        self.max_history_size = 100
        self.process_timers = {}  # Temporizadores por proceso
        self._last_metrics_time = 0
        self._cached_metrics: Optional[SystemMetrics] = None
        self._cache_duration = 1.0  # Cache de 1 segundo
    
    def _collect_metrics(self, force: bool = False) -> SystemMetrics:
        """Recolecta métricas del sistema con cache"""
        current_time = time.time()
        
        # Usar cache si está disponible y no ha expirado
        if (not force and self._cached_metrics and 
            current_time - self._last_metrics_time < self._cache_duration):
            return self._cached_metrics
        
        try:
            # Obtener métricas del sistema
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Obtener uso de disco (opcional)
            try:
                disk_usage = psutil.disk_usage(config.BASE_DIR)
                disk_usage_percent = disk_usage.percent
            except:
                disk_usage_percent = None
            
            # Crear objeto de métricas
            metrics = SystemMetrics(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                active_processes=self.active_processes,
                max_processes=self.max_processes,
                disk_usage_percent=disk_usage_percent,
                timestamp=current_time
            )
            
            # Guardar en cache
            self._cached_metrics = metrics
            self._last_metrics_time = current_time
            
            # Agregar al historial
            self.metrics_history.append(metrics)
            if len(self.metrics_history) > self.max_history_size:
                self.metrics_history.pop(0)
            
            return metrics
            
        except Exception as e:
            logger.error(f"Error recolectando métricas: {e}")
            # Retornar métricas por defecto en caso de error
            return SystemMetrics(
                cpu_percent=0,
                memory_percent=0,
                active_processes=self.active_processes,
                max_processes=self.max_processes,
                timestamp=current_time
            )
    
    def can_start_process(self) -> Tuple[bool, str]:
        """
        Verifica si se puede iniciar un nuevo proceso.
        Retorna: (success, message)
        """
        with self.lock:
            metrics = self._collect_metrics()
            
            # Verificar límites
            if metrics.is_overloaded:
                reasons = []
                if metrics.cpu_percent > config.CPU_USAGE_LIMIT:
                    reasons.append(f"CPU: {metrics.cpu_percent:.1f}% > {config.CPU_USAGE_LIMIT}%")
                if metrics.memory_percent > config.MEMORY_USAGE_LIMIT:
                    reasons.append(f"Memoria: {metrics.memory_percent:.1f}% > {config.MEMORY_USAGE_LIMIT}%")
                if metrics.active_processes >= metrics.max_processes:
                    reasons.append(f"Procesos: {metrics.active_processes} >= {metrics.max_processes}")
                
                reason_msg = ", ".join(reasons)
                return False, f"Sistema sobrecargado ({reason_msg}). Espera un momento."
            
            # Incrementar contador
            self.active_processes += 1
            
            # Iniciar temporizador para este proceso
            process_id = threading.get_ident()
            self.process_timers[process_id] = time.time()
            
            logger.info(f"✅ Proceso iniciado. Activos: {self.active_processes}/{self.max_processes}")
            return True, f"Proceso iniciado (CPU: {metrics.cpu_percent:.1f}%, Mem: {metrics.memory_percent:.1f}%)"
    
    def finish_process(self):
        """Marca un proceso como terminado con logging"""
        with self.lock:
            if self.active_processes > 0:
                process_id = threading.get_ident()
                start_time = self.process_timers.pop(process_id, None)
                
                if start_time:
                    duration = time.time() - start_time
                    logger.info(f"✅ Proceso terminado. Duración: {duration:.1f}s")
                
                self.active_processes = max(0, self.active_processes - 1)
            else:
                logger.warning("Intento de terminar proceso cuando no hay activos")
    
    @contextmanager
    def process_context(self):
        """
        Context manager para procesos. Uso:
        
        with load_manager.process_context():
            # Tu código aquí
        """
        success, message = self.can_start_process()
        if not success:
            raise RuntimeError(message)
        
        try:
            yield
        finally:
            self.finish_process()
    
    def get_status(self) -> Dict:
        """Obtiene estado actual del sistema con métricas detalladas"""
        metrics = self._collect_metrics()
        
        # Calcular estadísticas del historial
        avg_cpu = 0
        avg_memory = 0
        if self.metrics_history:
            avg_cpu = sum(m.cpu_percent for m in self.metrics_history) / len(self.metrics_history)
            avg_memory = sum(m.memory_percent for m in self.metrics_history) / len(self.metrics_history)
        
        status = metrics.to_dict()
        status.update({
            'avg_cpu_percent': round(avg_cpu, 1),
            'avg_memory_percent': round(avg_memory, 1),
            'history_size': len(self.metrics_history),
            'process_timers_count': len(self.process_timers),
            'recommendation': self._get_recommendation(metrics)
        })
        
        return status
    
    def _get_recommendation(self, metrics: SystemMetrics) -> str:
        """Genera recomendación basada en métricas"""
        if metrics.is_overloaded:
            if metrics.cpu_percent > 90:
                return "⚠️ Sistema críticamente sobrecargado. Espera varios minutos."
            elif metrics.cpu_percent > 80:
                return "⚠️ Sistema muy cargado. Espera 1-2 minutos."
            else:
                return "⚠️ Sistema cargado. Espera unos momentos."
        elif metrics.cpu_percent > 60:
            return "✅ Sistema aceptable. Puede ralentizarse con archivos grandes."
        else:
            return "✅ Sistema óptimo. Listo para procesar."
    
    def get_historical_data(self, limit: int = 10) -> list:
        """Obtiene datos históricos de métricas"""
        with self.lock:
            return [
                m.to_dict() for m in self.metrics_history[-limit:]
            ]
    
    def reset(self):
        """Reinicia el gestor (para testing o recuperación)"""
        with self.lock:
            self.active_processes = 0
            self.metrics_history.clear()
            self.process_timers.clear()
            self._cached_metrics = None
            logger.warning("LoadManager reiniciado")


# Instancia global
load_manager = LoadManager()