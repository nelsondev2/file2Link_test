import os
import aiofiles
import asyncio
import json
import time
import logging
import urllib.parse
from typing import Dict, List, Optional, Tuple

from config import BASE_DIR, RENDER_DOMAIN, DOWNLOAD_LINK_EXPIRY_HOURS, SECRET_KEY, MAX_USER_STORAGE_MB, MAX_FILES_PER_USER
import hmac
import hashlib

logger = logging.getLogger(__name__)

class AsyncFileService:
    def __init__(self):
        self.metadata_file = os.path.join(BASE_DIR, ".metadata.json")
        self.metadata: Dict = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self._load_metadata_sync()
        
    def _load_metadata_sync(self):
        """Carga inicial síncrona (solo al inicio)"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
            logger.info("Metadata cargada")
        except Exception as e:
            logger.error(f"Error cargando metadata: {e}")
            self.metadata = {}
    
    async def save_metadata(self):
        """Guarda metadata de forma asíncrona"""
        try:
            async with aiofiles.open(self.metadata_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(self.metadata, ensure_ascii=False, indent=2))
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
    
    def _get_user_lock(self, user_id: int) -> asyncio.Lock:
        """Obtiene lock por usuario"""
        if user_id not in self.locks:
            self.locks[user_id] = asyncio.Lock()
        return self.locks[user_id]
    
    def sanitize_filename(self, filename: str) -> str:
        """Limpia nombre de archivo"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100-len(ext)] + ext
        return filename
    
    async def get_user_directory(self, user_id: int, file_type: str = "downloads") -> str:
        """Crea y retorna directorio del usuario"""
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        await asyncio.to_thread(os.makedirs, user_dir, exist_ok=True)
        return user_dir
    
    async def get_user_storage_usage(self, user_id: int) -> int:
        """Calcula uso de almacenamiento"""
        download_dir = await self.get_user_directory(user_id, "downloads")
        packed_dir = await self.get_user_directory(user_id, "packed")
        
        total_size = 0
        
        for directory in [download_dir, packed_dir]:
            if not os.path.exists(directory):
                continue
            
            loop = asyncio.get_event_loop()
            try:
                files = await loop.run_in_executor(None, os.listdir, directory)
                
                for file in files:
                    file_path = os.path.join(directory, file)
                    if os.path.isfile(file_path):
                        size = await loop.run_in_executor(None, os.path.getsize, file_path)
                        total_size += size
            except Exception as e:
                logger.error(f"Error calculando tamaño {directory}: {e}")
        
        return total_size
    
    async def check_user_quota(self, user_id: int, additional_size: int = 0) -> Tuple[bool, str]:
        """Verifica cuota del usuario"""
        total_size = await self.get_user_storage_usage(user_id)
        total_size_mb = total_size / (1024 * 1024)
        
        if total_size_mb + (additional_size / (1024 * 1024)) > MAX_USER_STORAGE_MB:
            return False, f"Límite de {MAX_USER_STORAGE_MB}MB alcanzado"
        
        downloads = await self.list_user_files(user_id, "downloads")
        packed = await self.list_user_files(user_id, "packed")
        
        if len(downloads) + len(packed) >= MAX_FILES_PER_USER:
            return False, f"Máximo {MAX_FILES_PER_USER} archivos"
        
        return True, ""
    
    async def register_file(self, user_id: int, original_name: str, stored_name: str, file_type: str = "downloads") -> int:
        """Registra archivo en metadata"""
        async with self._get_user_lock(user_id):
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                self.metadata[user_key] = {"next_number": 1, "files": {}}
            
            file_num = self.metadata[user_key]["next_number"]
            self.metadata[user_key]["next_number"] += 1
            
            self.metadata[user_key]["files"][str(file_num)] = {
                "original_name": original_name,
                "stored_name": stored_name,
                "registered_at": time.time(),
                "size": 0
            }
            
            await self.save_metadata()
            logger.info(f"Archivo registrado: #{file_num} - {original_name}")
            return file_num
    
    async def update_file_size(self, user_id: int, file_number: int, size: int, file_type: str = "downloads"):
        """Actualiza tamaño del archivo"""
        async with self._get_user_lock(user_id):
            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                file_str = str(file_number)
                if file_str in self.metadata[user_key]["files"]:
                    self.metadata[user_key]["files"][file_str]["size"] = size
                    await self.save_metadata()
    
    async def list_user_files(self, user_id: int, file_type: str = "downloads") -> List[Dict]:
        """Lista archivos del usuario"""
        user_dir = await self.get_user_directory(user_id, file_type)
        
        if not os.path.exists(user_dir):
            return []
        
        user_key = f"{user_id}_{file_type}"
        files = []
        
        async with self._get_user_lock(user_id):
            if user_key in self.metadata:
                existing_files = []
                for file_num_str, file_data in self.metadata[user_key]["files"].items():
                    file_path = os.path.join(user_dir, file_data["stored_name"])
                    if os.path.exists(file_path):
                        existing_files.append((int(file_num_str), file_data))
                
                existing_files.sort(key=lambda x: x[0])
                
                for file_number, file_data in existing_files:
                    file_path = os.path.join(user_dir, file_data["stored_name"])
                    if os.path.isfile(file_path):
                        loop = asyncio.get_event_loop()
                        size = await loop.run_in_executor(None, os.path.getsize, file_path)
                        
                        if file_data.get("size", 0) != size:
                            self.metadata[user_key]["files"][str(file_number)]["size"] = size
                        
                        if file_type == "downloads":
                            download_url = await self.create_download_url(user_id, file_data["stored_name"])
                        else:
                            download_url = await self.create_packed_url(user_id, file_data["stored_name"])
                        
                        files.append({
                            'number': file_number,
                            'name': file_data["original_name"],
                            'stored_name': file_data["stored_name"],
                            'size': size,
                            'size_mb': size / (1024 * 1024),
                            'url': download_url,
                            'file_type': file_type
                        })
                
                if files:
                    await self.save_metadata()
        
        return files
    
    async def create_download_url(self, user_id: int, filename: str) -> str:
        """Crea URL de descarga con token temporal"""
        # Importar aquí para evitar circular imports
        from flask_app import generate_download_token
        
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        
        token, expiry = generate_download_token(user_id, safe_filename)
        
        return f"{RENDER_DOMAIN}/storage/{user_id}/downloads/{encoded_filename}?token={token}&expiry={expiry}"
    
    async def create_packed_url(self, user_id: int, filename: str) -> str:
        """Crea URL para archivos empaquetados con token"""
        from flask_app import generate_download_token
        
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        
        token, expiry = generate_download_token(user_id, safe_filename)
        
        return f"{RENDER_DOMAIN}/storage/{user_id}/packed/{encoded_filename}?token={token}&expiry={expiry}"
    
    async def get_file_by_number(self, user_id: int, file_number: int, file_type: str = "downloads") -> Optional[Dict]:
        """Obtiene información de archivo por número"""
        user_key = f"{user_id}_{file_type}"
        
        async with self._get_user_lock(user_id):
            if user_key not in self.metadata:
                return None
            
            file_data = self.metadata[user_key]["files"].get(str(file_number))
            if not file_data:
                return None
        
        user_dir = await self.get_user_directory(user_id, file_type)
        file_path = os.path.join(user_dir, file_data["stored_name"])
        
        if not os.path.exists(file_path):
            return None
        
        loop = asyncio.get_event_loop()
        size = await loop.run_in_executor(None, os.path.getsize, file_path)
        
        if file_type == "downloads":
            download_url = await self.create_download_url(user_id, file_data["stored_name"])
        else:
            download_url = await self.create_packed_url(user_id, file_data["stored_name"])
        
        return {
            'number': file_number,
            'original_name': file_data["original_name"],
            'stored_name': file_data["stored_name"],
            'path': file_path,
            'size': size,
            'url': download_url,
            'file_type': file_type
        }
    
    async def rename_file(self, user_id: int, file_number: int, new_name: str, file_type: str = "downloads") -> Tuple[bool, str, Optional[str]]:
        """Renombra un archivo"""
        try:
            user_key = f"{user_id}_{file_type}"
            
            async with self._get_user_lock(user_id):
                if user_key not in self.metadata:
                    return False, "Usuario no encontrado", None
                
                file_info = await self.get_file_by_number(user_id, file_number, file_type)
                if not file_info:
                    return False, "Archivo no encontrado", None
                
                file_data = self.metadata[user_key]["files"].get(str(file_number))
                if not file_data:
                    return False, "Archivo no encontrado en metadata", None
                
                new_name = self.sanitize_filename(new_name)
                user_dir = await self.get_user_directory(user_id, file_type)
                old_path = os.path.join(user_dir, file_data["stored_name"])
                
                if not os.path.exists(old_path):
                    return False, "Archivo físico no encontrado", None
                
                _, ext = os.path.splitext(file_data["stored_name"])
                new_stored_name = new_name + ext
                
                counter = 1
                base_new_stored_name = new_stored_name
                while os.path.exists(os.path.join(user_dir, new_stored_name)):
                    name_no_ext = os.path.splitext(base_new_stored_name)[0]
                    new_stored_name = f"{name_no_ext}_{counter}{ext}"
                    counter += 1
                
                new_path = os.path.join(user_dir, new_stored_name)
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, os.rename, old_path, new_path)
                
                file_data["original_name"] = new_name
                file_data["stored_name"] = new_stored_name
                await self.save_metadata()
                
                if file_type == "downloads":
                    new_url = await self.create_download_url(user_id, new_stored_name)
                else:
                    new_url = await self.create_packed_url(user_id, new_stored_name)
                
                return True, f"Archivo renombrado a: {new_name}", new_url
            
        except Exception as e:
            logger.error(f"Error renombrando: {e}")
            return False, f"Error: {str(e)}", None
    
    async def delete_file_by_number(self, user_id: int, file_number: int, file_type: str = "downloads") -> Tuple[bool, str]:
        """Elimina archivo por número"""
        try:
            user_key = f"{user_id}_{file_type}"
            
            async with self._get_user_lock(user_id):
                if user_key not in self.metadata:
                    return False, "Usuario no encontrado"
                
                file_info = await self.get_file_by_number(user_id, file_number, file_type)
                if not file_info:
                    return False, "Archivo no encontrado"
                
                file_data = self.metadata[user_key]["files"].get(str(file_number))
                if not file_data:
                    return False, "Archivo no encontrado en metadata"
                
                user_dir = await self.get_user_directory(user_id, file_type)
                file_path = os.path.join(user_dir, file_data["stored_name"])
                
                if os.path.exists(file_path):
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, os.remove, file_path)
                
                del self.metadata[user_key]["files"][str(file_number)]
                
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
                await self.save_metadata()
                
                return True, f"Archivo #{file_number} eliminado"
            
        except Exception as e:
            logger.error(f"Error eliminando: {e}")
            return False, f"Error: {str(e)}"
    
    async def delete_all_files(self, user_id: int, file_type: str = "downloads") -> Tuple[bool, str]:
        """Elimina todos los archivos del usuario"""
        try:
            user_dir = await self.get_user_directory(user_id, file_type)
            
            if not os.path.exists(user_dir):
                return False, f"No hay archivos {file_type}"
            
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(None, os.listdir, user_dir)
            
            if not files:
                return False, f"No hay archivos {file_type}"
            
            deleted_count = 0
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    await loop.run_in_executor(None, os.remove, file_path)
                    deleted_count += 1
            
            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                self.metadata[user_key] = {"next_number": 1, "files": {}}
                await self.save_metadata()
            
            return True, f"Eliminados {deleted_count} archivos"
            
        except Exception as e:
            logger.error(f"Error eliminando todos: {e}")
            return False, f"Error: {str(e)}"
    
    def get_original_filename(self, user_id: int, stored_filename: str, file_type: str = "downloads") -> str:
        """Obtiene nombre original del archivo (síncrono para Flask)"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return stored_filename
        
        for file_data in self.metadata[user_key]["files"].values():
            if file_data["stored_name"] == stored_filename:
                return file_data["original_name"]
        
        return stored_filename
    
    def format_bytes(self, size: int) -> str:
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

# Instancia global
async_file_service = AsyncFileService()