import os
import urllib.parse
import hashlib
import json
import time
import logging
import sys
from config import BASE_DIR, RENDER_DOMAIN, HASH_SALT, HASH_EXPIRE_DAYS
from filename_utils import clean_for_url, clean_for_filesystem, get_url_safe_name

logger = logging.getLogger(__name__)

# Importar telegram_db aquí para evitar import circular
try:
    from telegram_db import telegram_db
    HAS_TELEGRAM_DB = True
except ImportError:
    HAS_TELEGRAM_DB = False
    logger.warning("⚠️ telegram_db no disponible")

class FileService:
    def __init__(self):
        self.HASH_EXPIRE_DAYS = HASH_EXPIRE_DAYS
        
        # Inicializar sistema de almacenamiento
        self.use_telegram_db = False
        
        # Cargar datos iniciales
        self._initialize_storage()
        
        logger.info(f"✅ FileService iniciado con HASH_EXPIRE_DAYS={self.HASH_EXPIRE_DAYS}")
    
    def _initialize_storage(self):
        """Inicializar sistema de almacenamiento"""
        # Verificar si Telegram DB está disponible
        if HAS_TELEGRAM_DB and telegram_db is not None:
            # Intentaremos usar Telegram DB
            self.use_telegram_db = True
            logger.info("✅ Intentando usar Telegram DB (PERSISTENTE)")
        else:
            # Usar almacenamiento local
            self.use_telegram_db = False
            logger.warning("⚠️ Usando almacenamiento local JSON (NO PERSISTENTE)")
            self._load_local_data()
    
    # ===== FUNCIONES ASYNC PARA TELEGRAM DB =====
    
    async def _telegram_db_available(self):
        """Verificar si Telegram DB está disponible"""
        if not self.use_telegram_db or not HAS_TELEGRAM_DB:
            return False
        
        try:
            return await telegram_db.is_available()
        except:
            return False
    
    async def total_users_count_async(self):
        """Contar usuarios totales (async para Telegram DB)"""
        if await self._telegram_db_available():
            users = await telegram_db.get_all_users()
            return len(users) if users else 0
        else:
            return len(self.users) if hasattr(self, 'users') else 0
    
    async def is_user_exist_async(self, user_id):
        """Verificar si usuario existe (async)"""
        if await self._telegram_db_available():
            user = await telegram_db.load_data("USER", str(user_id))
            return user is not None
        else:
            return str(user_id) in self.users if hasattr(self, 'users') else False
    
    async def add_user_async(self, user_id, user_first_name=""):
        """Agregar nuevo usuario (async)"""
        user_id_str = str(user_id)
        
        if await self._telegram_db_available():
            existing = await self.is_user_exist_async(user_id)
            
            if not existing:
                user_data = {
                    "user_id": user_id,
                    "first_name": user_first_name,
                    "first_seen": time.time(),
                    "last_seen": time.time(),
                    "files_count": 0,
                    "total_size": 0
                }
                
                success = await telegram_db.save_data("USER", user_id_str, user_data)
                if success:
                    logger.info(f"👤 Nuevo usuario registrado en Telegram DB: {user_id} - {user_first_name}")
                    return True
                return False
            else:
                # Actualizar último acceso
                user = await telegram_db.load_data("USER", user_id_str)
                if user and 'data' in user:
                    user_data = user['data']
                    user_data['last_seen'] = time.time()
                    if user_first_name:
                        user_data['first_name'] = user_first_name
                    
                    await telegram_db.update_data("USER", user_id_str, user_data)
                return False
        else:
            # Código local
            return self._add_user_local(user_id, user_first_name)
    
    async def get_all_users_async(self):
        """Obtener todos los usuarios (async)"""
        if await self._telegram_db_available():
            users_data = await telegram_db.get_all_users()
            if users_data:
                user_list = []
                for item in users_data:
                    if 'data' in item:
                        user_list.append(item['data'])
                return user_list
            return []
        else:
            return list(self.users.values()) if hasattr(self, 'users') else []
    
    async def get_next_file_number_async(self, user_id, file_type="downloads"):
        """Obtiene el siguiente número de archivo (async)"""
        if await self._telegram_db_available():
            files = await telegram_db.get_all_files(user_id)
            if files:
                # Filtrar por tipo
                user_files = []
                for f in files:
                    if 'data' in f and f['data'].get('file_type') == file_type:
                        user_files.append(f['data'])
                
                if user_files:
                    max_num = max([f.get('file_number', 0) for f in user_files])
                    return max_num + 1
            return 1
        else:
            # Código local
            return self._get_next_file_number_local(user_id, file_type)
    
    async def register_file_async(self, user_id, original_name, stored_name, file_type="downloads"):
        """Registra un archivo (async)"""
        file_number = await self.get_next_file_number_async(user_id, file_type)
        file_id = f"{user_id}_{file_type}_{file_number}"
        
        file_data = {
            "user_id": user_id,
            "file_type": file_type,
            "file_number": file_number,
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time()
        }
        
        if await self._telegram_db_available():
            success = await telegram_db.save_data("FILE", file_id, file_data)
            
            if success:
                # Actualizar contador de archivos del usuario
                user = await telegram_db.load_data("USER", str(user_id))
                if user and 'data' in user:
                    user_data = user['data']
                    user_data['files_count'] = user_data.get('files_count', 0) + 1
                    await telegram_db.update_data("USER", str(user_id), user_data)
                    
                    logger.info(f"✅ Archivo registrado en Telegram DB: #{file_number} - {original_name}")
                    return file_number
            return None
        else:
            # Código local
            return self._register_file_local(user_id, original_name, stored_name, file_type, file_number)
    
    async def list_user_files_async(self, user_id, file_type="downloads"):
        """Lista archivos del usuario (async)"""
        if await self._telegram_db_available():
            files_data = await telegram_db.get_all_files(user_id)
            files = []
            
            if files_data:
                for file_item in files_data:
                    if 'data' in file_item:
                        file_data = file_item['data']
                        if file_data.get('file_type') == file_type:
                            # Verificar que el archivo físico existe
                            file_path = self.get_file_path(user_id, file_type, file_data['stored_name'])
                            
                            if os.path.exists(file_path):
                                size = os.path.getsize(file_path)
                                
                                # Generar URL
                                if file_type == "downloads":
                                    download_url = self.create_download_url(user_id, file_data['stored_name'])
                                else:
                                    download_url = self.create_packed_url(user_id, file_data['stored_name'])
                                
                                files.append({
                                    'number': file_data['file_number'],
                                    'name': file_data['original_name'],
                                    'stored_name': file_data['stored_name'],
                                    'size': size,
                                    'size_mb': size / (1024 * 1024),
                                    'url': download_url,
                                    'file_type': file_type
                                })
            
            return files
        else:
            # Código local
            return self._list_user_files_local(user_id, file_type)
    
    async def delete_file_by_number_async(self, user_id, file_number, file_type="downloads"):
        """Elimina un archivo por número (async)"""
        # Primero obtener información del archivo
        files = await self.list_user_files_async(user_id, file_type)
        file_info = None
        
        for f in files:
            if f['number'] == file_number:
                file_info = f
                break
        
        if not file_info:
            return False, "Archivo no encontrado"
        
        # Eliminar archivo físico
        user_dir = self.get_user_directory(user_id, file_type)
        file_path = os.path.join(user_dir, file_info['stored_name'])
        
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # Eliminar de la base de datos
        if await self._telegram_db_available():
            file_id = f"{user_id}_{file_type}_{file_number}"
            success = await telegram_db.delete_data("FILE", file_id)
            
            if success:
                # Actualizar contador de usuario
                user = await telegram_db.load_data("USER", str(user_id))
                if user and 'data' in user:
                    user_data = user['data']
                    user_data['files_count'] = max(0, user_data.get('files_count', 0) - 1)
                    await telegram_db.update_data("USER", str(user_id), user_data)
                
                # Reasignar números de archivos restantes
                remaining_files = await self.list_user_files_async(user_id, file_type)
                
                # Actualizar números en Telegram DB
                new_number = 1
                for file_data in remaining_files:
                    file_id_old = f"{user_id}_{file_type}_{file_data['number']}"
                    file_id_new = f"{user_id}_{file_type}_{new_number}"
                    
                    # Obtener datos actuales
                    file_item = await telegram_db.load_data("FILE", file_id_old)
                    if file_item and 'data' in file_item:
                        file_data_updated = file_item['data']
                        file_data_updated['file_number'] = new_number
                        
                        # Actualizar con nuevo número
                        await telegram_db.update_data("FILE", file_id_old, file_data_updated)
                        
                        # Renombrar el ID si es diferente
                        if file_id_old != file_id_new:
                            await telegram_db.save_data("FILE", file_id_new, file_data_updated)
                            await telegram_db.delete_data("FILE", file_id_old)
                        
                        new_number += 1
                
                return True, f"Archivo #{file_number} '{file_info['name']}' eliminado"
            
            return False, "Error eliminando de la base de datos"
        else:
            # Código local
            return self._delete_file_by_number_local(user_id, file_number, file_type)
    
    async def rename_file_async(self, user_id, file_number, new_name, file_type="downloads"):
        """Renombra un archivo (async)"""
        # Obtener información del archivo
        files = await self.list_user_files_async(user_id, file_type)
        file_info = None
        
        for f in files:
            if f['number'] == file_number:
                file_info = f
                break
        
        if not file_info:
            return False, "Archivo no encontrado", None
        
        # Usar clean_for_filesystem para el nombre en disco
        new_name_clean = clean_for_filesystem(new_name)
        
        user_dir = self.get_user_directory(user_id, file_type)
        old_path = os.path.join(user_dir, file_info['stored_name'])
        
        if not os.path.exists(old_path):
            return False, "Archivo físico no encontrado", None
        
        _, ext = os.path.splitext(file_info['stored_name'])
        new_stored_name = new_name_clean + ext
        
        counter = 1
        base_new_stored_name = new_stored_name
        while os.path.exists(os.path.join(user_dir, new_stored_name)):
            name_no_ext = os.path.splitext(base_new_stored_name)[0]
            ext = os.path.splitext(base_new_stored_name)[1]
            new_stored_name = f"{name_no_ext}_{counter}{ext}"
            counter += 1
        
        new_path = os.path.join(user_dir, new_stored_name)
        os.rename(old_path, new_path)
        
        if await self._telegram_db_available():
            file_id = f"{user_id}_{file_type}_{file_number}"
            file_item = await telegram_db.load_data("FILE", file_id)
            
            if file_item and 'data' in file_item:
                file_data = file_item['data']
                file_data['original_name'] = new_name
                file_data['stored_name'] = new_stored_name
                
                await telegram_db.update_data("FILE", file_id, file_data)
        else:
            # Código local
            self._rename_file_local(user_id, file_number, new_name, new_stored_name, file_type)
        
        if file_type == "downloads":
            new_url = self.create_download_url(user_id, new_stored_name)
        else:
            new_url = self.create_packed_url(user_id, new_stored_name)
        
        return True, f"Archivo renombrado a: {new_name}", new_url
    
    async def delete_all_files_async(self, user_id, file_type="downloads"):
        """Elimina todos los archivos del usuario (async)"""
        user_dir = self.get_user_directory(user_id, file_type)
        
        if not os.path.exists(user_dir):
            return False, f"No hay archivos {file_type} para eliminar"
        
        files = os.listdir(user_dir)
        if not files:
            return False, f"No hay archivos {file_type} para eliminar"
        
        deleted_count = 0
        for filename in files:
            file_path = os.path.join(user_dir, filename)
            if os.path.isfile(file_path):
                os.remove(file_path)
                deleted_count += 1
        
        if await self._telegram_db_available():
            # Eliminar todos los archivos de este tipo para el usuario
            files_data = await telegram_db.get_all_files(user_id)
            
            if files_data:
                for file_item in files_data:
                    if 'data' in file_item and file_item['data'].get('file_type') == file_type:
                        file_id = file_item['id']
                        await telegram_db.delete_data("FILE", file_id)
            
            # Actualizar contador de usuario
            user = await telegram_db.load_data("USER", str(user_id))
            if user and 'data' in user:
                # Contar archivos restantes de otros tipos
                remaining_files = await telegram_db.get_all_files(user_id)
                remaining_count = len(remaining_files) if remaining_files else 0
                
                user_data = user['data']
                user_data['files_count'] = remaining_count
                await telegram_db.update_data("USER", str(user_id), user_data)
        else:
            # Código local
            self._delete_all_files_local(user_id, file_type)
        
        return True, f"Se eliminaron {deleted_count} archivos {file_type}"
    
    async def cleanup_expired_hashes_async(self):
        """Limpiar hashes expirados (async)"""
        if await self._telegram_db_available():
            return await telegram_db.cleanup_old_hashes()
        else:
            return self._cleanup_expired_hashes_local()
    
    # ===== FUNCIONES SÍNCRONAS (WRAPPERS) =====
    
    def total_users_count(self):
        """Contar usuarios totales (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Ejecutar en thread separado
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.total_users_count_async()))
                    return future.result()
            else:
                return asyncio.run(self.total_users_count_async())
        except:
            # Fallback
            return len(self.users) if hasattr(self, 'users') else 0
    
    def is_user_exist(self, user_id):
        """Verificar si usuario existe (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Para handlers, usaremos async directamente
                pass
            else:
                return asyncio.run(self.is_user_exist_async(user_id))
        except:
            pass
        
        # Fallback local
        return str(user_id) in self.users if hasattr(self, 'users') else False
    
    def add_user(self, user_id, user_first_name=""):
        """Agregar nuevo usuario (sync wrapper) - para uso en handlers async"""
        # Esta función será llamada desde contextos async
        # Retornamos una coroutine para que el caller la await
        return self.add_user_async(user_id, user_first_name)
    
    def get_all_users(self):
        """Obtener todos los usuarios (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.get_all_users_async()))
                    return future.result()
            else:
                return asyncio.run(self.get_all_users_async())
        except:
            return list(self.users.values()) if hasattr(self, 'users') else []
    
    def get_next_file_number(self, user_id, file_type="downloads"):
        """Obtiene el siguiente número de archivo (sync wrapper)"""
        try:
            import asyncio
            return asyncio.run(self.get_next_file_number_async(user_id, file_type))
        except:
            return self._get_next_file_number_local(user_id, file_type)
    
    def register_file(self, user_id, original_name, stored_name, file_type="downloads"):
        """Registra un archivo (sync wrapper) - para uso en handlers async"""
        return self.register_file_async(user_id, original_name, stored_name, file_type)
    
    def list_user_files(self, user_id, file_type="downloads"):
        """Lista archivos del usuario (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.list_user_files_async(user_id, file_type)))
                    return future.result()
            else:
                return asyncio.run(self.list_user_files_async(user_id, file_type))
        except:
            return self._list_user_files_local(user_id, file_type)
    
    def delete_file_by_number(self, user_id, file_number, file_type="downloads"):
        """Elimina un archivo por número (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.delete_file_by_number_async(user_id, file_number, file_type)))
                    return future.result()
            else:
                return asyncio.run(self.delete_file_by_number_async(user_id, file_number, file_type))
        except:
            return self._delete_file_by_number_local(user_id, file_number, file_type)
    
    def rename_file(self, user_id, file_number, new_name, file_type="downloads"):
        """Renombra un archivo (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.rename_file_async(user_id, file_number, new_name, file_type)))
                    return future.result()
            else:
                return asyncio.run(self.rename_file_async(user_id, file_number, new_name, file_type))
        except:
            return self._rename_file_local_sync(user_id, file_number, new_name, file_type)
    
    def delete_all_files(self, user_id, file_type="downloads"):
        """Elimina todos los archivos del usuario (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.delete_all_files_async(user_id, file_type)))
                    return future.result()
            else:
                return asyncio.run(self.delete_all_files_async(user_id, file_type))
        except:
            return self._delete_all_files_local(user_id, file_type)
    
    def cleanup_expired_hashes(self):
        """Limpiar hashes expirados (sync wrapper)"""
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.cleanup_expired_hashes_async()))
                    return future.result()
            else:
                return asyncio.run(self.cleanup_expired_hashes_async())
        except:
            return self._cleanup_expired_hashes_local()
    
    # ===== FUNCIONES COMPATIBLES (igual que antes) =====
    
    def sanitize_filename(self, filename):
        """Limpia el nombre de archivo para que sea URL-safe"""
        return clean_for_url(filename)

    def format_bytes(self, size):
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def create_download_url(self, user_id, filename):
        """Crea una URL de descarga segura CON HASH"""
        safe_filename = clean_for_url(filename)
        file_hash = self.create_file_hash(user_id, safe_filename, "downloads")
        
        encoded_filename = get_url_safe_name(safe_filename)
        base_url = RENDER_DOMAIN.rstrip('/')
        return f"{base_url}/download/{file_hash}?file={encoded_filename}"

    def create_packed_url(self, user_id, filename):
        """Crea una URL para archivos empaquetados CON HASH"""
        safe_filename = clean_for_url(filename)
        file_hash = self.create_file_hash(user_id, safe_filename, "packed")
        
        encoded_filename = get_url_safe_name(safe_filename)
        base_url = RENDER_DOMAIN.rstrip('/')
        return f"{base_url}/packed/{file_hash}?file={encoded_filename}"

    def get_user_directory(self, user_id, file_type="downloads"):
        """Obtiene el directorio del usuario"""
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    
    def get_file_path(self, user_id, file_type, filename):
        """Obtiene la ruta completa del archivo"""
        user_dir = self.get_user_directory(user_id, file_type)
        return os.path.join(user_dir, filename)

    def get_user_storage_usage(self, user_id):
        """Calcula el uso de almacenamiento por usuario"""
        download_dir = self.get_user_directory(user_id, "downloads")
        packed_dir = self.get_user_directory(user_id, "packed")
        
        total_size = 0
        for directory in [download_dir, packed_dir]:
            if not os.path.exists(directory):
                continue
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
        
        return total_size

    def get_file_by_number(self, user_id, file_number, file_type="downloads"):
        """Obtiene información de archivo por número"""
        files = self.list_user_files(user_id, file_type)
        for file_info in files:
            if file_info['number'] == file_number:
                return file_info
        return None

    def get_original_filename(self, user_id, stored_filename, file_type="downloads"):
        """Obtiene el nombre original del archivo basado en el nombre almacenado"""
        files = self.list_user_files(user_id, file_type)
        for file_info in files:
            if file_info['stored_name'] == stored_filename:
                return file_info['name']
        return stored_filename
    
    def get_file_by_hash(self, file_hash):
        """Obtener archivo por hash (para servidor web)"""
        # Esta función necesita acceso a hashes, que están en Telegram DB o local
        # Implementación simplificada para compatibilidad
        from flask_app import app
        with app.app_context():
            # Este método será llamado desde flask_app.py
            # flask_app.py tiene su propia lógica para verificar hashes
            pass
        
        # Retornar None, flask_app manejará el resto
        return None
    
    # ===== SISTEMA DE HASHES =====
    
    def create_file_hash(self, user_id, filename, file_type="downloads"):
        """Crear hash único de seguridad"""
        timestamp = int(time.time())
        random_part = os.urandom(8).hex()
        
        hash_data = f"{user_id}_{filename}_{file_type}_{timestamp}_{HASH_SALT}_{random_part}"
        file_hash = hashlib.md5(hash_data.encode()).hexdigest()[:12]
        
        hash_record = {
            'file_hash': file_hash,
            'user_id': user_id,
            'filename': filename,
            'file_type': file_type,
            'created_at': timestamp,
            'expires_at': timestamp + (self.HASH_EXPIRE_DAYS * 24 * 3600)
        }
        
        # Guardar hash
        if HAS_TELEGRAM_DB and telegram_db is not None:
            # Guardar de forma asíncrona
            try:
                import asyncio
                # Intentar ejecutar en el loop actual
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.create_task(self._save_hash_async(file_hash, hash_record))
                else:
                    asyncio.run(self._save_hash_async(file_hash, hash_record))
            except:
                # Fallback local
                self._save_hash_local(file_hash, hash_record)
        else:
            # Guardar localmente
            self._save_hash_local(file_hash, hash_record)
        
        logger.info(f"🔐 Hash creado para {filename}: {file_hash} (expira en {self.HASH_EXPIRE_DAYS} días)")
        return file_hash
    
    async def _save_hash_async(self, file_hash, hash_record):
        """Guardar hash en Telegram DB (async)"""
        try:
            if await self._telegram_db_available():
                await telegram_db.save_data("HASH", file_hash, hash_record)
        except Exception as e:
            logger.error(f"Error guardando hash en Telegram DB: {e}")
            self._save_hash_local(file_hash, hash_record)
    
    def verify_hash(self, file_hash):
        """Verificar validez del hash (sync - para flask_app)"""
        # Esta es una versión simplificada para flask_app
        # flask_app.py manejará la verificación real
        return False, "Usando Telegram DB para verificación"
    
    # ===== MÉTODOS LOCALES (fallback) =====
    
    def _load_local_data(self):
        """Cargar datos locales (solo para fallback)"""
        self.metadata_file = "file_metadata.json"
        self.users_file = "users.json"
        self.hashes_file = "file_hashes.json"
        
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
        except Exception as e:
            logger.error(f"Error cargando metadata: {e}")
            self.metadata = {}
        
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
            else:
                self.users = {}
        except Exception as e:
            logger.error(f"Error cargando usuarios: {e}")
            self.users = {}
        
        try:
            if os.path.exists(self.hashes_file):
                with open(self.hashes_file, 'r', encoding='utf-8') as f:
                    self.file_hashes = json.load(f)
            else:
                self.file_hashes = {}
        except Exception as e:
            logger.error(f"Error cargando hashes: {e}")
            self.file_hashes = {}
    
    def _save_hash_local(self, file_hash, hash_record):
        """Guardar hash localmente"""
        if not hasattr(self, 'file_hashes'):
            self.file_hashes = {}
        
        self.file_hashes[file_hash] = hash_record
        self._save_hashes_local()
    
    def _save_metadata_local(self):
        """Guardar metadata localmente"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
    
    def _save_users_local(self):
        """Guardar usuarios localmente"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando usuarios: {e}")
    
    def _save_hashes_local(self):
        """Guardar hashes localmente"""
        try:
            with open(self.hashes_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_hashes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando hashes: {e}")
    
    def _add_user_local(self, user_id, user_first_name=""):
        """Agregar usuario localmente (fallback)"""
        user_id_str = str(user_id)
        
        if not hasattr(self, 'users'):
            self.users = {}
        
        if user_id_str not in self.users:
            self.users[user_id_str] = {
                'id': user_id,
                'first_name': user_first_name,
                'first_seen': time.time(),
                'last_seen': time.time(),
                'files_count': 0,
                'total_size': 0
            }
            self._save_users_local()
            logger.info(f"👤 Nuevo usuario registrado localmente: {user_id} - {user_first_name}")
            return True
        else:
            self.users[user_id_str]['last_seen'] = time.time()
            if user_first_name:
                self.users[user_id_str]['first_name'] = user_first_name
            self._save_users_local()
            return False
    
    def _get_next_file_number_local(self, user_id, file_type="downloads"):
        """Obtener siguiente número de archivo localmente"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        next_num = self.metadata[user_key]["next_number"]
        return next_num
    
    def _register_file_local(self, user_id, original_name, stored_name, file_type="downloads", file_number=None):
        """Registrar archivo localmente"""
        if file_number is None:
            file_number = self._get_next_file_number_local(user_id, file_type)
        
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        self.metadata[user_key]["files"][str(file_number)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time()
        }
        self.metadata[user_key]["next_number"] = file_number + 1
        self._save_metadata_local()
        
        # Actualizar usuario local
        if str(user_id) in self.users:
            self.users[str(user_id)]['files_count'] = self.users[str(user_id)].get('files_count', 0) + 1
            self._save_users_local()
        
        logger.info(f"✅ Archivo registrado localmente: #{file_number} - {original_name}")
        return file_number
    
    def _list_user_files_local(self, user_id, file_type="downloads"):
        """Listar archivos localmente"""
        user_dir = self.get_user_directory(user_id, file_type)
        if not os.path.exists(user_dir):
            return []
        
        files = []
        user_key = f"{user_id}_{file_type}"
        
        if user_key in self.metadata:
            existing_files = []
            for file_num, file_data in self.metadata[user_key]["files"].items():
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.exists(file_path):
                    existing_files.append((int(file_num), file_data))
            
            existing_files.sort(key=lambda x: x[0])
            
            for file_number, file_data in existing_files:
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.isfile(file_path):
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
                        'file_type': file_type
                    })
        
        return files
    
    def _delete_file_by_number_local(self, user_id, file_number, file_type="downloads"):
        """Eliminar archivo localmente"""
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
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
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
            self._save_metadata_local()
            
            return True, f"Archivo #{file_number} '{file_data['original_name']}' eliminado y números reasignados"
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False, f"Error al eliminar archivo: {str(e)}"
    
    def _rename_file_local(self, user_id, file_number, new_name, new_stored_name, file_type="downloads"):
        """Renombrar archivo localmente"""
        user_key = f"{user_id}_{file_type}"
        if user_key in self.metadata and str(file_number) in self.metadata[user_key]["files"]:
            file_data = self.metadata[user_key]["files"][str(file_number)]
            file_data["original_name"] = new_name
            file_data["stored_name"] = new_stored_name
            self._save_metadata_local()
    
    def _rename_file_local_sync(self, user_id, file_number, new_name, file_type="downloads"):
        """Renombrar archivo localmente (sync completo)"""
        try:
            file_info = self.get_file_by_number(user_id, file_number, file_type)
            if not file_info:
                return False, "Archivo no encontrado", None
            
            new_name_clean = clean_for_filesystem(new_name)
            user_dir = self.get_user_directory(user_id, file_type)
            old_path = os.path.join(user_dir, file_info['stored_name'])
            
            if not os.path.exists(old_path):
                return False, "Archivo físico no encontrado", None
            
            _, ext = os.path.splitext(file_info['stored_name'])
            new_stored_name = new_name_clean + ext
            
            counter = 1
            base_new_stored_name = new_stored_name
            while os.path.exists(os.path.join(user_dir, new_stored_name)):
                name_no_ext = os.path.splitext(base_new_stored_name)[0]
                ext = os.path.splitext(base_new_stored_name)[1]
                new_stored_name = f"{name_no_ext}_{counter}{ext}"
                counter += 1
            
            new_path = os.path.join(user_dir, new_stored_name)
            os.rename(old_path, new_path)
            
            self._rename_file_local(user_id, file_number, new_name, new_stored_name, file_type)
            
            if file_type == "downloads":
                new_url = self.create_download_url(user_id, new_stored_name)
            else:
                new_url = self.create_packed_url(user_id, new_stored_name)
            
            return True, f"Archivo renombrado a: {new_name}", new_url
            
        except Exception as e:
            logger.error(f"Error renombrando archivo: {e}")
            return False, f"Error al renombrar: {str(e)}", None
    
    def _delete_all_files_local(self, user_id, file_type="downloads"):
        """Eliminar todos los archivos localmente"""
        try:
            user_dir = self.get_user_directory(user_id, file_type)
            
            if not os.path.exists(user_dir):
                return False, f"No hay archivos {file_type} para eliminar"
            
            files = os.listdir(user_dir)
            if not files:
                return False, f"No hay archivos {file_type} para eliminar"
            
            deleted_count = 0
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                self.metadata[user_key] = {"next_number": 1, "files": {}}
                self._save_metadata_local()
            
            return True, f"Se eliminaron {deleted_count} archivos {file_type} y se resetearon los números"
            
        except Exception as e:
            logger.error(f"Error eliminando todos los archivos: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"
    
    def _cleanup_expired_hashes_local(self):
        """Limpiar hashes expirados localmente"""
        try:
            current_time = time.time()
            expired_hashes = []
            
            for file_hash, hash_data in self.file_hashes.items():
                if current_time > hash_data['expires_at']:
                    expired_hashes.append(file_hash)
            
            for file_hash in expired_hashes:
                del self.file_hashes[file_hash]
            
            if expired_hashes:
                self._save_hashes_local()
                logger.info(f"🧹 Hashes expirados limpiados localmente: {len(expired_hashes)}")
            
            return len(expired_hashes)
        except Exception as e:
            logger.error(f"Error limpiando hashes: {e}")
            return 0
    
    def get_statistics(self):
        """Obtener estadísticas del sistema"""
        try:
            total_users = self.total_users_count()
            
            # Contar archivos
            total_files_downloads = 0
            total_files_packed = 0
            total_size = 0
            
            if self.use_telegram_db and HAS_TELEGRAM_DB:
                # Para Telegram DB, necesitamos contar de forma diferente
                # Esta es una implementación simplificada
                all_users = self.get_all_users()
                for user in all_users:
                    files_count = user.get('files_count', 0)
                    # Estimación: mitad downloads, mitad packed
                    total_files_downloads += files_count // 2
                    total_files_packed += files_count // 2
            else:
                for user_id in self.users:
                    user_id_int = int(user_id)
                    downloads = len(self._list_user_files_local(user_id_int, "downloads"))
                    packed = len(self._list_user_files_local(user_id_int, "packed"))
                    user_size = self.get_user_storage_usage(user_id_int)
                    
                    total_files_downloads += downloads
                    total_files_packed += packed
                    total_size += user_size
            
            total_files = total_files_downloads + total_files_packed
            
            # Contar hashes activos
            if self.use_telegram_db and HAS_TELEGRAM_DB:
                active_hashes = "N/A (Telegram DB)"
            else:
                active_hashes = len(self.file_hashes) if hasattr(self, 'file_hashes') else 0
            
            return {
                'total_users': total_users,
                'total_files': total_files,
                'total_files_downloads': total_files_downloads,
                'total_files_packed': total_files_packed,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'active_hashes': active_hashes,
                'hash_expire_days': self.HASH_EXPIRE_DAYS
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}

# Instancia global
file_service = FileService()