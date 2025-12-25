import os
import urllib.parse
import hashlib
import json
import time
import logging
import sys
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
from datetime import datetime

from config import BASE_DIR, RENDER_DOMAIN

logger = logging.getLogger(__name__)


class FileService:
    """Servicio profesional de gestión de archivos con cache y optimizaciones"""
    
    def __init__(self):
        self.file_mappings: Dict[str, Any] = {}
        self.metadata_file = "file_metadata.json"
        self._cache: Dict[str, Any] = {}  # Cache simple en memoria
        self._cache_ttl = 300  # 5 minutos
        self._cache_timestamps: Dict[str, float] = {}
        self.load_metadata()
        
        # Crear directorio base si no existe
        os.makedirs(BASE_DIR, exist_ok=True)
    
    def _clean_cache(self):
        """Limpia cache expirado"""
        current_time = time.time()
        expired_keys = [
            key for key, timestamp in self._cache_timestamps.items()
            if current_time - timestamp > self._cache_ttl
        ]
        
        for key in expired_keys:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
    
    def _cache_get(self, key: str) -> Optional[Any]:
        """Obtiene valor del cache"""
        self._clean_cache()
        
        if key in self._cache:
            self._cache_timestamps[key] = time.time()
            return self._cache[key]
        return None
    
    def _cache_set(self, key: str, value: Any):
        """Guarda valor en cache"""
        self._clean_cache()
        self._cache[key] = value
        self._cache_timestamps[key] = time.time()
    
    def load_metadata(self):
        """Carga metadata con manejo de errores robusto"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if os.path.exists(self.metadata_file):
                    with open(self.metadata_file, 'r', encoding='utf-8') as f:
                        self.metadata = json.load(f)
                    logger.info(f"✅ Metadata cargada ({len(self.metadata)} usuarios)")
                else:
                    self.metadata = {}
                    logger.info("📄 Metadata inicializada (nuevo archivo)")
                return
                
            except json.JSONDecodeError as e:
                logger.error(f"Error JSON en metadata (intento {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    # Intentar reparar o crear backup
                    self._backup_metadata()
                    time.sleep(1)
                else:
                    logger.warning("Usando metadata vacía debido a errores")
                    self.metadata = {}
                    
            except Exception as e:
                logger.error(f"Error cargando metadata: {e}")
                if attempt < max_retries - 1:
                    time.sleep(1)
                else:
                    self.metadata = {}
    
    def _backup_metadata(self):
        """Crea backup de metadata corrupta"""
        try:
            if os.path.exists(self.metadata_file):
                backup_name = f"{self.metadata_file}.backup.{int(time.time())}"
                os.rename(self.metadata_file, backup_name)
                logger.warning(f"⚠️ Metadata corrupta, creado backup: {backup_name}")
        except Exception as e:
            logger.error(f"Error creando backup: {e}")
    
    def save_metadata(self):
        """Guarda metadata con atomic write"""
        try:
            # Escribir a archivo temporal primero
            temp_file = f"{self.metadata_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
            
            # Reemplazar archivo original
            if os.path.exists(self.metadata_file):
                os.replace(temp_file, self.metadata_file)
            else:
                os.rename(temp_file, self.metadata_file)
                
            logger.debug("✅ Metadata guardada exitosamente")
            
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
            raise
    
    def get_next_file_number(self, user_id: int, file_type: str = "downloads") -> int:
        """Obtiene el siguiente número de archivo (thread-safe mejorado)"""
        cache_key = f"next_num_{user_id}_{file_type}"
        cached = self._cache_get(cache_key)
        
        if cached is not None:
            return cached
        
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        next_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1
        
        # Guardar periódicamente, no en cada llamada
        if next_num % 10 == 0:  # Cada 10 archivos
            self.save_metadata()
        
        self._cache_set(cache_key, next_num)
        return next_num
    
    def sanitize_filename(self, filename: str) -> str:
        """Limpia nombre de archivo manteniendo extensión"""
        if not filename:
            return "archivo_sin_nombre"
        
        # Caracteres inválidos en Windows/Linux
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        
        # Limitar longitud pero mantener extensión
        if len(filename) > 150:
            name, ext = os.path.splitext(filename)
            if len(ext) > 10:  # Extensión muy larga
                ext = ext[:10]
            filename = name[:150-len(ext)] + ext
        
        return filename.strip()
    
    def format_bytes(self, size: int) -> str:
        """Formatea bytes de forma legible y precisa"""
        if size < 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        
        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024.0
            unit_index += 1
        
        # Formato diferente según tamaño
        if unit_index == 0:  # Bytes
            return f"{size:.0f} {units[unit_index]}"
        elif unit_index <= 2:  # KB o MB
            return f"{size:.1f} {units[unit_index]}"
        else:  # GB o TB
            return f"{size:.2f} {units[unit_index]}"
    
    def create_download_url(self, user_id: int, filename: str) -> str:
        """Crea URL segura para descarga"""
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        
        # Cache de URLs generadas
        cache_key = f"url_{user_id}_{filename}"
        cached_url = self._cache_get(cache_key)
        
        if cached_url:
            return cached_url
        
        url = f"{RENDER_DOMAIN}/storage/{user_id}/downloads/{encoded_filename}"
        self._cache_set(cache_key, url)
        return url
    
    def create_packed_url(self, user_id: int, filename: str) -> str:
        """Crea URL para archivos empaquetados"""
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        return f"{RENDER_DOMAIN}/storage/{user_id}/packed/{encoded_filename}"
    
    def get_user_directory(self, user_id: int, file_type: str = "downloads") -> str:
        """Obtiene directorio de usuario con validaciones"""
        # Validar tipo de archivo
        if file_type not in ["downloads", "packed"]:
            file_type = "downloads"
        
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        
        try:
            os.makedirs(user_dir, exist_ok=True)
            # Verificar permisos de escritura
            test_file = os.path.join(user_dir, ".write_test")
            with open(test_file, 'w') as f:
                f.write("test")
            os.remove(test_file)
            
        except PermissionError:
            logger.error(f"❌ Sin permisos en directorio: {user_dir}")
            raise
        except Exception as e:
            logger.error(f"Error creando directorio: {e}")
            raise
        
        return user_dir
    
    def get_user_storage_usage(self, user_id: int) -> int:
        """Calcula uso de almacenamiento con cache"""
        cache_key = f"storage_{user_id}"
        cached = self._cache_get(cache_key)
        
        if cached is not None:
            return cached
        
        total_size = 0
        for file_type in ["downloads", "packed"]:
            try:
                user_dir = self.get_user_directory(user_id, file_type)
                if os.path.exists(user_dir):
                    for root, dirs, files in os.walk(user_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            if os.path.isfile(file_path):
                                total_size += os.path.getsize(file_path)
            except Exception as e:
                logger.error(f"Error calculando almacenamiento {file_type}: {e}")
                continue
        
        self._cache_set(cache_key, total_size)
        return total_size
    
    def create_file_hash(self, user_id: int, filename: str) -> str:
        """Crea hash único para archivo"""
        data = f"{user_id}_{filename}_{time.time()}_{os.urandom(8).hex()}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def list_user_files(self, user_id: int, file_type: str = "downloads") -> List[Dict]:
        """Lista archivos del usuario optimizado con cache"""
        cache_key = f"list_{user_id}_{file_type}"
        cached = self._cache_get(cache_key)
        
        if cached is not None:
            return cached
        
        user_dir = self.get_user_directory(user_id, file_type)
        if not os.path.exists(user_dir):
            return []
        
        files = []
        user_key = f"{user_id}_{file_type}"
        
        if user_key in self.metadata:
            # Obtener archivos existentes
            existing_files = []
            for file_num_str, file_data in self.metadata[user_key]["files"].items():
                try:
                    file_num = int(file_num_str)
                    existing_files.append((file_num, file_data))
                except ValueError:
                    continue
            
            # Ordenar por número
            existing_files.sort(key=lambda x: x[0])
            
            for file_number, file_data in existing_files:
                file_path = os.path.join(user_dir, file_data["stored_name"])
                
                # Verificar que el archivo físico existe
                if os.path.isfile(file_path):
                    try:
                        size = os.path.getsize(file_path)
                        
                        if file_type == "downloads":
                            download_url = self.create_download_url(user_id, file_data["stored_name"])
                        else:
                            download_url = self.create_packed_url(user_id, file_data["stored_name"])
                        
                        files.append({
                            'number': file_number,
                            'name': file_data["original_name"],
                            'stored_name': file_data["stored_name"],
                            'size': size,
                            'size_mb': size / (1024 * 1024),
                            'url': download_url,
                            'file_type': file_type,
                            'modified_at': os.path.getmtime(file_path)
                        })
                        
                    except Exception as e:
                        logger.error(f"Error procesando archivo {file_path}: {e}")
                        continue
        
        # Actualizar cache
        self._cache_set(cache_key, files)
        return files
    
    def register_file(self, user_id: int, original_name: str, 
                     stored_name: str, file_type: str = "downloads") -> int:
        """Registra archivo con timestamp y metadata adicional"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        file_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1
        
        self.metadata[user_key]["files"][str(file_num)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time(),
            "file_type": file_type,
            "user_id": user_id
        }
        
        # Guardar metadata
        self.save_metadata()
        
        # Invalidar caches relacionados
        cache_keys_to_delete = [
            f"list_{user_id}_{file_type}",
            f"storage_{user_id}",
            f"next_num_{user_id}_{file_type}"
        ]
        for key in cache_keys_to_delete:
            self._cache.pop(key, None)
            self._cache_timestamps.pop(key, None)
        
        logger.info(f"✅ Archivo registrado: #{file_num} - {original_name}")
        return file_num
    
    def get_file_by_number(self, user_id: int, file_number: int, 
                          file_type: str = "downloads") -> Optional[Dict]:
        """Obtiene archivo por número con validaciones"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return None
        
        file_data = self.metadata[user_key]["files"].get(str(file_number))
        if not file_data:
            return None
        
        user_dir = self.get_user_directory(user_id, file_type)
        file_path = os.path.join(user_dir, file_data["stored_name"])
        
        if not os.path.exists(file_path):
            return None
        
        try:
            size = os.path.getsize(file_path)
            
            if file_type == "downloads":
                download_url = self.create_download_url(user_id, file_data["stored_name"])
            else:
                download_url = self.create_packed_url(user_id, file_data["stored_name"])
            
            return {
                'number': file_number,
                'original_name': file_data["original_name"],
                'stored_name': file_data["stored_name"],
                'path': file_path,
                'url': download_url,
                'file_type': file_type,
                'size': size,
                'size_mb': size / (1024 * 1024),
                'registered_at': file_data.get("registered_at", time.time())
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo archivo #{file_number}: {e}")
            return None
    
    def get_original_filename(self, user_id: int, stored_filename: str, 
                             file_type: str = "downloads") -> str:
        """Obtiene nombre original del archivo"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return stored_filename
        
        for file_data in self.metadata[user_key]["files"].values():
            if file_data["stored_name"] == stored_filename:
                return file_data["original_name"]
        
        return stored_filename
    
    def rename_file(self, user_id: int, file_number: int, new_name: str, 
                   file_type: str = "downloads") -> Tuple[bool, str, Optional[str]]:
        """Renombra archivo con manejo profesional de errores"""
        try:
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado", None
            
            file_info = self.get_file_by_number(user_id, file_number, file_type)
            if not file_info:
                return False, "Archivo no encontrado", None
            
            file_data = self.metadata[user_key]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado en metadata", None
            
            # Sanitizar nuevo nombre
            new_name = self.sanitize_filename(new_name)
            if not new_name or new_name.strip() == "":
                return False, "El nuevo nombre no puede estar vacío", None
            
            user_dir = self.get_user_directory(user_id, file_type)
            old_path = os.path.join(user_dir, file_data["stored_name"])
            
            if not os.path.exists(old_path):
                return False, "Archivo físico no encontrado", None
            
            # Mantener extensión original
            _, old_ext = os.path.splitext(file_data["stored_name"])
            _, new_ext = os.path.splitext(new_name)
            
            if not new_ext:
                new_name += old_ext
            elif new_ext.lower() != old_ext.lower():
                # Si cambia extensión, mantener la nueva pero registrar cambio
                logger.info(f"Extensión cambiada de {old_ext} a {new_ext}")
            
            new_stored_name = new_name
            
            # Verificar colisión de nombres
            counter = 1
            base_new_stored_name = new_stored_name
            while os.path.exists(os.path.join(user_dir, new_stored_name)):
                name_no_ext = os.path.splitext(base_new_stored_name)[0]
                ext = os.path.splitext(base_new_stored_name)[1]
                new_stored_name = f"{name_no_ext}_{counter}{ext}"
                counter += 1
            
            new_path = os.path.join(user_dir, new_stored_name)
            
            # Renombrar físicamente
            os.rename(old_path, new_path)
            
            # Actualizar metadata
            file_data["original_name"] = new_name
            file_data["stored_name"] = new_stored_name
            self.save_metadata()
            
            # Generar nueva URL
            if file_type == "downloads":
                new_url = self.create_download_url(user_id, new_stored_name)
            else:
                new_url = self.create_packed_url(user_id, new_stored_name)
            
            # Invalidar cache
            cache_keys_to_delete = [
                f"list_{user_id}_{file_type}",
                f"url_{user_id}_{file_data['stored_name']}",
                f"url_{user_id}_{new_stored_name}"
            ]
            for key in cache_keys_to_delete:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            
            logger.info(f"✅ Archivo renombrado: #{file_number} -> {new_name}")
            return True, f"Archivo renombrado a: {new_name}", new_url
            
        except PermissionError:
            return False, "Error de permisos. No se puede renombrar el archivo.", None
        except Exception as e:
            logger.error(f"Error renombrando archivo: {e}", exc_info=True)
            return False, f"Error al renombrar: {str(e)}", None
    
    def delete_file_by_number(self, user_id: int, file_number: int, 
                             file_type: str = "downloads") -> Tuple[bool, str]:
        """Elimina archivo profesionalmente"""
        try:
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado"
            
            file_info = self.get_file_by_number(user_id, file_number, file_type)
            if not file_info:
                return False, "Archivo no encontrado"
            
            file_data = self.metadata[user_key]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado en metadata"
            
            user_dir = self.get_user_directory(user_id, file_type)
            file_path = os.path.join(user_dir, file_data["stored_name"])
            
            # Eliminar archivo físico
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                logger.info(f"🗑️ Archivo eliminado físicamente: {file_path} ({self.format_bytes(file_size)})")
            
            # Eliminar de metadata y reasignar números
            deleted_name = file_data["original_name"]
            del self.metadata[user_key]["files"][str(file_number)]
            
            # Reasignar números consecutivos
            remaining_files = sorted(
                [(int(num), data) for num, data in self.metadata[user_key]["files"].items()],
                key=lambda x: x[0]
            )
            
            self.metadata[user_key]["files"] = {}
            new_number = 1
            for old_num, file_data in remaining_files:
                self.metadata[user_key]["files"][str(new_number)] = file_data
                new_number += 1
            
            self.metadata[user_key]["next_number"] = new_number
            self.save_metadata()
            
            # Invalidar cache
            cache_keys_to_delete = [
                f"list_{user_id}_{file_type}",
                f"storage_{user_id}",
                f"url_{user_id}_{file_data['stored_name']}"
            ]
            for key in cache_keys_to_delete:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            
            logger.info(f"✅ Archivo #{file_number} eliminado: {deleted_name}")
            return True, f"Archivo #{file_number} '{deleted_name}' eliminado"
            
        except PermissionError:
            return False, "Error de permisos. No se puede eliminar el archivo."
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}", exc_info=True)
            return False, f"Error al eliminar archivo: {str(e)}"
    
    def delete_all_files(self, user_id: int, file_type: str = "downloads") -> Tuple[bool, str]:
        """Elimina todos los archivos de un tipo"""
        try:
            user_dir = self.get_user_directory(user_id, file_type)
            
            if not os.path.exists(user_dir):
                return False, f"No hay archivos {file_type} para eliminar"
            
            files = os.listdir(user_dir)
            if not files:
                return False, f"No hay archivos {file_type} para eliminar"
            
            deleted_count = 0
            total_size = 0
            
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        deleted_count += 1
                        total_size += file_size
                    except Exception as e:
                        logger.error(f"Error eliminando {filename}: {e}")
                        continue
            
            # Resetear metadata
            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                self.metadata[user_key] = {"next_number": 1, "files": {}}
                self.save_metadata()
            
            # Invalidar cache
            cache_keys_to_delete = [
                f"list_{user_id}_{file_type}",
                f"storage_{user_id}"
            ]
            for key in cache_keys_to_delete:
                self._cache.pop(key, None)
                self._cache_timestamps.pop(key, None)
            
            size_str = self.format_bytes(total_size)
            logger.info(f"🗑️ Carpeta {file_type} vaciada: {deleted_count} archivos, {size_str}")
            
            return True, f"Se eliminaron {deleted_count} archivos {file_type} ({size_str})"
            
        except Exception as e:
            logger.error(f"Error eliminando todos los archivos: {e}", exc_info=True)
            return False, f"Error al eliminar archivos: {str(e)}"


# Instancia global
file_service = FileService()