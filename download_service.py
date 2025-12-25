import asyncio
import os
import time
import logging
import hashlib
from typing import Optional, Tuple, Callable, Dict, Any
from contextlib import asynccontextmanager
from datetime import datetime

import aiofiles
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, BadRequest, ConnectionError

from config import config

logger = logging.getLogger(__name__)


class DownloadMetrics:
    """Métricas de descarga para análisis y optimización"""
    
    def __init__(self):
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.bytes_downloaded: int = 0
        self.chunks_downloaded: int = 0
        self.retry_count: int = 0
        self.errors: list = []
        self.speeds: list = []  # Velocidades en bytes/segundo
    
    @property
    def duration(self) -> float:
        """Duración total de la descarga"""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    @property
    def avg_speed(self) -> float:
        """Velocidad promedio"""
        if self.speeds:
            return sum(self.speeds) / len(self.speeds)
        return 0.0
    
    @property
    def max_speed(self) -> float:
        """Velocidad máxima alcanzada"""
        return max(self.speeds) if self.speeds else 0.0
    
    def add_speed_sample(self, bytes_per_second: float):
        """Agrega muestra de velocidad"""
        self.speeds.append(bytes_per_second)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario"""
        return {
            'duration': self.duration,
            'bytes_downloaded': self.bytes_downloaded,
            'chunks_downloaded': self.chunks_downloaded,
            'retry_count': self.retry_count,
            'error_count': len(self.errors),
            'avg_speed_bps': self.avg_speed,
            'avg_speed_mbps': self.avg_speed / (1024 * 1024),
            'max_speed_bps': self.max_speed,
            'max_speed_mbps': self.max_speed / (1024 * 1024)
        }


class SmartDownloadService:
    """Servicio de descarga inteligente con optimizaciones avanzadas"""
    
    def __init__(self):
        self.active_downloads: Dict[int, Dict] = {}
        self.download_cache: Dict[str, str] = {}  # Cache de file_id -> ruta local
        self.metrics_history: Dict[str, DownloadMetrics] = {}
        self._concurrent_semaphore = asyncio.Semaphore(config.MAX_CONCURRENT_PROCESSES)
        
    async def _extract_file_info(self, message: Message) -> Optional[Dict]:
        """Extrae información del archivo con validación"""
        try:
            file_obj = None
            file_type = "unknown"
            original_filename = "archivo"
            file_size = 0
            
            # Detectar tipo de archivo
            if message.document:
                file_obj = message.document
                file_type = "document"
                original_filename = message.document.file_name or "documento"
                file_size = file_obj.file_size or 0
                
            elif message.video:
                file_obj = message.video
                file_type = "video"
                original_filename = message.video.file_name or "video.mp4"
                file_size = file_obj.file_size or 0
                
            elif message.audio:
                file_obj = message.audio
                file_type = "audio"
                title = message.audio.title or "Audio"
                performer = message.audio.performer or "Desconocido"
                original_filename = f"{performer} - {title}.mp3"
                file_size = file_obj.file_size or 0
                
            elif message.photo:
                file_obj = message.photo[-1]  # Mayor calidad
                file_type = "photo"
                original_filename = f"foto_{message.id}.jpg"
                file_size = file_obj.file_size or 0
                
            elif message.sticker:
                file_obj = message.sticker
                file_type = "sticker"
                original_filename = f"sticker_{message.sticker.file_unique_id}.webp"
                file_size = file_obj.file_size or 0
                
            else:
                logger.warning(f"Tipo de archivo no soportado: {message.media}")
                return None
            
            # Validar tamaño
            if file_size > config.MAX_FILE_SIZE:
                logger.error(f"Archivo excede límite: {file_size} > {config.MAX_FILE_SIZE}")
                return None
            
            return {
                'object': file_obj,
                'type': file_type,
                'name': original_filename,
                'size': file_size,
                'file_id': getattr(file_obj, 'file_id', None),
                'unique_id': getattr(file_obj, 'file_unique_id', None),
                'mime_type': getattr(file_obj, 'mime_type', None),
                'width': getattr(file_obj, 'width', None),
                'height': getattr(file_obj, 'height', None),
                'duration': getattr(file_obj, 'duration', None),
            }
            
        except Exception as e:
            logger.error(f"Error extrayendo info de archivo: {e}")
            return None
    
    async def download_file_fast(self, client: Client, message: Message, 
                                file_path: str, 
                                progress_callback: Optional[Callable] = None,
                                metrics: Optional[DownloadMetrics] = None) -> Tuple[bool, int]:
        """
        Descarga archivos con múltiples optimizaciones
        
        Args:
            client: Cliente Pyrogram
            message: Mensaje con el archivo
            file_path: Ruta donde guardar
            progress_callback: Función para reportar progreso
            metrics: Objeto para recolectar métricas
        
        Returns:
            Tuple[success, bytes_downloaded]
        """
        user_id = message.from_user.id
        
        # Inicializar métricas si no se proporcionan
        if metrics is None:
            metrics = DownloadMetrics()
        metrics.start_time = time.time()
        
        try:
            self.active_downloads[user_id] = {
                'start_time': time.time(),
                'file_path': file_path
            }
            
            # Extraer información del archivo
            file_info = await self._extract_file_info(message)
            if not file_info:
                return False, 0
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Configurar timeout dinámico basado en tamaño
            timeout = config.DOWNLOAD_TIMEOUT
            if file_info['size'] > 500 * 1024 * 1024:  # > 500MB
                timeout = 7200  # 2 horas
            elif file_info['size'] > 100 * 1024 * 1024:  # > 100MB
                timeout = 3600  # 1 hora
            
            logger.info(
                f"⚡ Iniciando descarga: {file_info['name']} "
                f"({file_info['size'] / (1024*1024):.1f} MB)"
            )
            
            downloaded = 0
            last_callback_time = metrics.start_time
            last_bytes = 0
            
            # Usar file_id si está disponible (más eficiente)
            if file_info.get('file_id'):
                logger.debug(f"Usando file_id para descarga eficiente: {file_info['file_id'][:20]}...")
            
            # Descargar con stream_media (método más eficiente de Pyrogram)
            async with aiofiles.open(file_path, 'wb') as f:
                async for chunk in client.stream_media(
                    file_info['object'],
                    limit=config.DOWNLOAD_BUFFER_SIZE
                ):
                    if not chunk:
                        continue
                    
                    await f.write(chunk)
                    downloaded += len(chunk)
                    metrics.bytes_downloaded = downloaded
                    metrics.chunks_downloaded += 1
                    
                    # Calcular velocidad instantánea
                    current_time = time.time()
                    time_diff = current_time - last_callback_time
                    
                    if time_diff >= 0.1:  # Cada 100ms calcular velocidad
                        bytes_diff = downloaded - last_bytes
                        instant_speed = bytes_diff / time_diff if time_diff > 0 else 0
                        metrics.add_speed_sample(instant_speed)
                        last_bytes = downloaded
                        last_callback_time = current_time
                    
                    # Llamar callback de progreso si se proporciona
                    if progress_callback and current_time - last_callback_time >= 0.5:
                        try:
                            await progress_callback(downloaded, file_info['size'])
                        except Exception as e:
                            logger.warning(f"Error en progress_callback: {e}")
            
            # Llamada final al callback
            if progress_callback and downloaded > 0:
                try:
                    await progress_callback(downloaded, file_info['size'])
                except Exception as e:
                    logger.warning(f"Error en progress_callback final: {e}")
            
            metrics.end_time = time.time()
            
            # Verificar integridad del archivo descargado
            final_size = os.path.getsize(file_path)
            if file_info['size'] > 0 and final_size != file_info['size']:
                logger.warning(
                    f"Tamaño diferencial: esperado {file_info['size']}, "
                    f"obtenido {final_size} (diff: {final_size - file_info['size']})"
                )
            
            # Calcular métricas finales
            elapsed = metrics.duration
            avg_speed = downloaded / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"✅ Descarga completada: {file_info['name']} en {elapsed:.1f}s "
                f"({avg_speed/(1024*1024):.1f} MB/s)"
            )
            
            # Cachear file_id para futuras descargas rápidas
            if file_info.get('unique_id'):
                self.download_cache[file_info['unique_id']] = file_path
            
            return True, downloaded
            
        except FloodWait as e:
            logger.warning(f"FloodWait: Esperando {e.value} segundos")
            await asyncio.sleep(e.value + 1)
            metrics.retry_count += 1
            metrics.errors.append(f"FloodWait: {e.value}s")
            
            # Reintentar con backoff
            return await self.download_file_fast(
                client, message, file_path, progress_callback, metrics
            )
            
        except (BadRequest, NetworkError) as e:
            logger.error(f"Error de red/Pyrogram: {e}")
            metrics.errors.append(str(e))
            return False, 0
            
        except Exception as e:
            logger.error(f"Error crítico en descarga: {e}", exc_info=True)
            metrics.errors.append(str(e))
            return False, 0
            
        finally:
            # Limpiar registro de descarga activa
            if user_id in self.active_downloads:
                del self.active_downloads[user_id]
            
            # Guardar métricas
            if metrics.bytes_downloaded > 0:
                file_hash = hashlib.md5(file_path.encode()).hexdigest()[:8]
                self.metrics_history[file_hash] = metrics
    
    async def download_with_retry(self, client: Client, message: Message, 
                                 file_path: str, 
                                 progress_callback: Optional[Callable] = None,
                                 max_retries: int = config.MAX_RETRIES) -> Tuple[bool, int]:
        """
        Descarga con reintentos inteligentes y backoff exponencial
        """
        total_metrics = DownloadMetrics()
        
        for attempt in range(max_retries + 1):
            try:
                logger.info(f"Intento {attempt + 1}/{max_retries + 1}")
                
                success, downloaded = await self.download_file_fast(
                    client, message, file_path, progress_callback, total_metrics
                )
                
                if success:
                    return True, downloaded
                
                if attempt < max_retries:
                    # Backoff exponencial
                    wait_time = 2 ** attempt
                    logger.info(f"Reintentando en {wait_time}s...")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
        
        logger.error(f"Fallo después de {max_retries} intentos")
        return False, 0
    
    @asynccontextmanager
    async def download_context(self, client: Client, message: Message, 
                              file_path: str, user_id: int):
        """
        Context manager para descargas con gestión automática de recursos
        
        Uso:
        async with download_service.download_context(...) as success:
            if success:
                # Descarga exitosa
        """
        success = False
        try:
            # Verificar si ya existe en cache
            file_info = await self._extract_file_info(message)
            if file_info and file_info.get('unique_id'):
                cached_path = self.download_cache.get(file_info['unique_id'])
                if cached_path and os.path.exists(cached_path):
                    logger.info(f"Usando archivo cacheado: {cached_path}")
                    # Copiar archivo cacheado
                    import shutil
                    shutil.copy2(cached_path, file_path)
                    success = True
                    yield success
                    return
            
            # Descargar normalmente
            success, _ = await self.download_with_retry(client, message, file_path)
            yield success
            
        except Exception as e:
            logger.error(f"Error en download_context: {e}")
            yield False
    
    def get_active_downloads(self) -> Dict[int, Dict]:
        """Obtiene descargas activas"""
        return self.active_downloads.copy()
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de métricas de todas las descargas"""
        total_downloads = len(self.metrics_history)
        if total_downloads == 0:
            return {}
        
        total_bytes = sum(m.bytes_downloaded for m in self.metrics_history.values())
        total_duration = sum(m.duration for m in self.metrics_history.values())
        total_retries = sum(m.retry_count for m in self.metrics_history.values())
        
        avg_speed = total_bytes / total_duration if total_duration > 0 else 0
        
        return {
            'total_downloads': total_downloads,
            'total_bytes': total_bytes,
            'total_duration': total_duration,
            'avg_speed_mbps': avg_speed / (1024 * 1024),
            'total_retries': total_retries,
            'cache_hits': len(self.download_cache),
            'active_downloads': len(self.active_downloads)
        }
    
    def clear_cache(self):
        """Limpia el cache de descargas"""
        self.download_cache.clear()
        logger.info("Cache de descargas limpiado")


# Instancia global
fast_download_service = SmartDownloadService()