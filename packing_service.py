import os
import zipfile
import time
import logging
import shutil
import tempfile
import concurrent.futures
from typing import List, Tuple, Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from config import config
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)


class PackingMetrics:
    """Métricas de empaquetado"""
    
    def __init__(self):
        self.start_time = time.time()
        self.end_time = None
        self.total_files = 0
        self.total_size = 0
        self.output_size = 0
        self.compression_ratio = 0.0
        self.parts_created = 0
    
    def complete(self):
        """Marca como completado y calcula métricas"""
        self.end_time = time.time()
        if self.total_size > 0:
            self.compression_ratio = self.output_size / self.total_size
    
    @property
    def duration(self) -> float:
        """Duración del empaquetado"""
        if self.end_time:
            return self.end_time - self.start_time
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario"""
        return {
            'duration': self.duration,
            'total_files': self.total_files,
            'total_size': self.total_size,
            'output_size': self.output_size,
            'compression_ratio': self.compression_ratio,
            'parts_created': self.parts_created,
            'speed_mbps': (self.total_size / self.duration) / (1024 * 1024) if self.duration > 0 else 0
        }


class ProfessionalPackingService:
    """Servicio de empaquetado profesional con múltiples optimizaciones"""
    
    def __init__(self):
        self.max_part_size_mb = config.MAX_PART_SIZE_MB
        self.temp_dir = tempfile.mkdtemp(prefix="packing_")
        self.metrics_history = []
        logger.info(f"📦 Servicio de empaquetado inicializado. Temp dir: {self.temp_dir}")
    
    def _cleanup_temp_files(self):
        """Limpia archivos temporales"""
        try:
            if os.path.exists(self.temp_dir):
                shutil.rmtree(self.temp_dir, ignore_errors=True)
                logger.debug(f"Directorio temporal limpiado: {self.temp_dir}")
        except Exception as e:
            logger.warning(f"Error limpiando temp files: {e}")
    
    def _validate_input(self, user_id: int, split_size_mb: Optional[int] = None) -> Tuple[bool, str]:
        """Valida entrada antes de empaquetar"""
        try:
            user_dir = file_service.get_user_directory(user_id, "downloads")
            
            if not os.path.exists(user_dir):
                return False, "No tienes archivos para empaquetar"
            
            files = os.listdir(user_dir)
            if not files:
                return False, "No tienes archivos para empaquetar"
            
            # Validar split_size
            if split_size_mb is not None:
                if split_size_mb <= 0:
                    return False, "El tamaño de división debe ser mayor a 0 MB"
                if split_size_mb > self.max_part_size_mb:
                    return False, f"El tamaño máximo por parte es {self.max_part_size_mb} MB"
            
            return True, "Validación exitosa"
            
        except Exception as e:
            logger.error(f"Error en validación: {e}")
            return False, f"Error de validación: {str(e)}"
    
    def pack_folder(self, user_id: int, split_size_mb: Optional[int] = None) -> Tuple[Optional[List[Dict]], str]:
        """
        Empaqueta la carpeta del usuario de manera profesional
        
        Returns:
            Tuple[files_list, status_message]
        """
        metrics = PackingMetrics()
        
        # Usar context manager para gestión de procesos
        with load_manager.process_context() as can_start:
            if not can_start:
                return None, "No se puede iniciar proceso. Sistema sobrecargado."
            
            try:
                # Validar entrada
                is_valid, validation_msg = self._validate_input(user_id, split_size_mb)
                if not is_valid:
                    return None, validation_msg
                
                user_dir = file_service.get_user_directory(user_id, "downloads")
                packed_dir = file_service.get_user_directory(user_id, "packed")
                os.makedirs(packed_dir, exist_ok=True)
                
                # Crear timestamp único
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                # Elegir método de empaquetado
                if split_size_mb:
                    result = self._pack_and_split_optimized(user_id, user_dir, packed_dir, 
                                                           base_filename, split_size_mb, metrics)
                else:
                    result = self._pack_single_optimized(user_id, user_dir, packed_dir, 
                                                        base_filename, metrics)
                
                # Completar métricas
                metrics.complete()
                self.metrics_history.append(metrics)
                
                # Limpiar archivos temporales
                self._cleanup_temp_files()
                
                return result
                
            except Exception as e:
                logger.error(f"Error en empaquetado: {e}", exc_info=True)
                self._cleanup_temp_files()
                return None, f"Error al empaquetar: {str(e)}"
    
    def _pack_single_optimized(self, user_id: int, user_dir: str, packed_dir: str, 
                              base_filename: str, metrics: PackingMetrics) -> Tuple[List[Dict], str]:
        """Empaqueta en un solo archivo ZIP optimizado"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            # Recolectar archivos con información detallada
            all_files = []
            total_size = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    all_files.append((filename, file_path, file_size))
                    total_size += file_size
                    metrics.total_size += file_size
            
            if not all_files:
                raise ValueError("No se encontraron archivos para empaquetar")
            
            metrics.total_files = len(all_files)
            logger.info(f"📦 Empaquetando {metrics.total_files} archivos ({total_size/(1024*1024):.1f} MB)")
            
            # Crear ZIP optimizado
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED, 
                                compresslevel=0, allowZip64=True) as zipf:
                for filename, file_path, file_size in all_files:
                    try:
                        # Usar escritura directa sin compresión para velocidad
                        zipf.write(file_path, filename)
                        logger.debug(f"Agregado al ZIP: {filename} ({file_size/(1024*1024):.1f} MB)")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            # Obtener métricas del archivo resultante
            output_size = os.path.getsize(output_file)
            metrics.output_size = output_size
            size_mb = output_size / (1024 * 1024)
            
            # Registrar archivo empaquetado
            file_num = file_service.register_file(user_id, f"{base_filename}.zip", 
                                                 f"{base_filename}.zip", "packed")
            
            download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            logger.info(f"✅ ZIP creado: {output_file} ({size_mb:.1f} MB)")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb,
                'total_files': metrics.total_files,
                'total_size_mb': total_size / (1024 * 1024),
                'compression_ratio': output_size / total_size if total_size > 0 else 1
            }], f"Empaquetado completado: {metrics.total_files} archivos, {size_mb:.1f}MB"
            
        except Exception as e:
            # Limpiar archivo en caso de error
            if os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"Error en _pack_single_optimized: {e}", exc_info=True)
            raise
    
    def _pack_and_split_optimized(self, user_id: int, user_dir: str, packed_dir: str, 
                                 base_filename: str, split_size_mb: int, 
                                 metrics: PackingMetrics) -> Tuple[List[Dict], str]:
        """Crea archivo ZIP y lo divide en partes optimizadas"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            # Crear archivo ZIP temporal primero
            temp_zip_name = f"{base_filename}.zip"
            temp_zip_path = os.path.join(self.temp_dir, temp_zip_name)
            
            # Recolectar archivos
            all_files = []
            total_size = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    file_size = os.path.getsize(file_path)
                    all_files.append((filename, file_path, file_size))
                    total_size += file_size
                    metrics.total_size += file_size
            
            if not all_files:
                raise ValueError("No se encontraron archivos para empaquetar")
            
            metrics.total_files = len(all_files)
            logger.info(
                f"📦 Creando ZIP y dividiendo en partes de {split_size_mb}MB. "
                f"Total: {metrics.total_files} archivos, {total_size/(1024*1024):.1f} MB"
            )
            
            # Crear ZIP temporal
            with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_STORED, 
                                compresslevel=0, allowZip64=True) as zipf:
                for filename, file_path, file_size in all_files:
                    try:
                        zipf.write(file_path, filename)
                        logger.debug(f"Agregado al ZIP temporal: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            zip_size = os.path.getsize(temp_zip_path)
            metrics.output_size = zip_size
            logger.info(f"ZIP temporal creado: {temp_zip_path} ({zip_size/(1024*1024):.2f}MB)")
            
            # Dividir el archivo ZIP en partes
            part_files = []
            part_num = 1
            
            with open(temp_zip_path, 'rb') as zip_file:
                while True:
                    chunk = zip_file.read(split_size_bytes)
                    if not chunk:
                        break
                    
                    # Crear nombre de parte
                    part_filename = f"{base_filename}.zip.{part_num:03d}"
                    part_path = os.path.join(packed_dir, part_filename)
                    
                    # Escribir la parte
                    with open(part_path, 'wb') as part_file:
                        part_file.write(chunk)
                    
                    part_size = len(chunk)
                    part_size_mb = part_size / (1024 * 1024)
                    
                    # Registrar la parte
                    file_num = file_service.register_file(user_id, part_filename, 
                                                         part_filename, "packed")
                    download_url = file_service.create_packed_url(user_id, part_filename)
                    
                    part_files.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'size_mb': part_size_mb,
                        'part_number': part_num,
                        'total_files': metrics.total_files if part_num == 1 else 0,
                        'total_size_mb': total_size / (1024 * 1024) if part_num == 1 else 0
                    })
                    
                    logger.info(
                        f"Parte {part_num} creada: {part_filename} ({part_size_mb:.2f}MB)"
                    )
                    part_num += 1
                    metrics.parts_created += 1
            
            # Eliminar archivo ZIP temporal
            os.remove(temp_zip_path)
            logger.debug(f"Archivo temporal eliminado: {temp_zip_path}")
            
            if not part_files:
                raise ValueError("No se crearon partes. Error en la división del archivo.")
            
            # Calcular tamaño total
            total_output_size = sum(part['size_mb'] for part in part_files)
            
            # Preparar mensaje de éxito
            status_message = (
                f"✅ Empaquetado completado: {metrics.parts_created} partes, "
                f"{metrics.total_files} archivos, {total_output_size:.1f}MB total"
            )
            
            if metrics.parts_created > 1:
                status_message += (
                    f"\n📦 Tamaño por parte: {split_size_mb}MB"
                    f"\n💾 Ratio compresión: {(total_output_size * 1024 * 1024) / total_size:.2%}"
                )
            
            return part_files, status_message
            
        except Exception as e:
            logger.error(f"Error en _pack_and_split_optimized: {e}", exc_info=True)
            # Limpiar archivos temporales
            temp_zip_path = os.path.join(self.temp_dir, f"{base_filename}.zip")
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
            raise
    
    def clear_packed_folder(self, user_id: int) -> Tuple[bool, str]:
        """Elimina todos los archivos empaquetados del usuario"""
        try:
            packed_dir = file_service.get_user_directory(user_id, "packed")
            
            if not os.path.exists(packed_dir):
                return False, "No tienes archivos empaquetados para eliminar"
            
            files = os.listdir(packed_dir)
            if not files:
                return False, "No tienes archivos empaquetados para eliminar"
            
            deleted_count = 0
            total_size = 0
            errors = []
            
            for filename in files:
                file_path = os.path.join(packed_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        total_size += file_size
                    except Exception as e:
                        errors.append(f"{filename}: {str(e)}")
                        logger.error(f"Error eliminando {filename}: {e}")
            
            # Limpiar metadata
            user_key = f"{user_id}_packed"
            if user_key in file_service.metadata:
                file_service.metadata[user_key] = {"next_number": 1, "files": {}}
                file_service.save_metadata()
            
            result_message = f"Se eliminaron {deleted_count} archivos empaquetados"
            
            if total_size > 0:
                result_message += f" ({file_service.format_bytes(total_size)})"
            
            if errors:
                result_message += f"\nErrores: {len(errors)} archivos no se pudieron eliminar"
            
            logger.info(f"🗑️ Carpeta packed vaciada: {deleted_count} archivos")
            return True, result_message
            
        except Exception as e:
            logger.error(f"Error limpiando carpeta empaquetada: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"
    
    def get_packing_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de empaquetado"""
        if not self.metrics_history:
            return {}
        
        total_packs = len(self.metrics_history)
        total_files = sum(m.total_files for m in self.metrics_history)
        total_size = sum(m.total_size for m in self.metrics_history)
        avg_ratio = sum(m.compression_ratio for m in self.metrics_history) / total_packs
        avg_duration = sum(m.duration for m in self.metrics_history) / total_packs
        
        return {
            'total_packs': total_packs,
            'total_files_processed': total_files,
            'total_size_processed_mb': total_size / (1024 * 1024),
            'average_compression_ratio': avg_ratio,
            'average_duration_seconds': avg_duration,
            'last_pack_time': self.metrics_history[-1].end_time if self.metrics_history[-1].end_time else None
        }


# Instancia global
packing_service = ProfessionalPackingService()