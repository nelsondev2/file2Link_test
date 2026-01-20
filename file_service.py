import os
import urllib.parse
import hashlib
import json
import time
import logging
import sys
from config import BASE_DIR, RENDER_DOMAIN, HASH_SALT, HASH_EXPIRE_DAYS
from filename_utils import clean_for_url, clean_for_filesystem, get_url_safe_name  # NUEVO IMPORT

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self):
        self.file_mappings = {}
        self.metadata_file = "file_metadata.json"
        self.users_file = "users.json"
        self.hashes_file = "file_hashes.json"
        self.HASH_EXPIRE_DAYS = HASH_EXPIRE_DAYS
        
        self.load_metadata()
        self.load_users()
        self.load_hashes()
        
        logger.info(f"✅ FileService iniciado con HASH_EXPIRE_DAYS={self.HASH_EXPIRE_DAYS}")
    
    def load_metadata(self):
        """Carga la metadata de archivos desde JSON"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
        except Exception as e:
            logger.error(f"Error cargando metadata: {e}")
            self.metadata = {}
    
    def save_metadata(self):
        """Guarda la metadata de archivos en JSON"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
    
    # ===== SISTEMA DE USUARIOS =====
    def load_users(self):
        """Cargar usuarios desde JSON (como primer bot)"""
        try:
            if os.path.exists(self.users_file):
                with open(self.users_file, 'r', encoding='utf-8') as f:
                    self.users = json.load(f)
            else:
                self.users = {}
        except Exception as e:
            logger.error(f"Error cargando usuarios: {e}")
            self.users = {}
    
    def save_users(self):
        """Guardar usuarios en JSON"""
        try:
            with open(self.users_file, 'w', encoding='utf-8') as f:
                json.dump(self.users, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando usuarios: {e}")
    
    def total_users_count(self):
        """Contar usuarios totales (como primer bot)"""
        return len(self.users)
    
    def is_user_exist(self, user_id):
        """Verificar si usuario existe"""
        return str(user_id) in self.users
    
    def add_user(self, user_id, user_first_name=""):
        """Agregar nuevo usuario"""
        if not self.is_user_exist(user_id):
            self.users[str(user_id)] = {
                'id': user_id,
                'first_name': user_first_name,
                'first_seen': time.time(),
                'last_seen': time.time(),
                'files_count': 0,
                'total_size': 0
            }
            self.save_users()
            logger.info(f"👤 Nuevo usuario registrado: {user_id} - {user_first_name}")
            return True
        else:
            # Actualizar último acceso
            self.users[str(user_id)]['last_seen'] = time.time()
            if user_first_name:
                self.users[str(user_id)]['first_name'] = user_first_name
            self.save_users()
            return False
    
    def get_all_users(self):
        """Obtener todos los usuarios (para broadcast)"""
        return list(self.users.values())
    
    def delete_user(self, user_id):
        """Eliminar usuario (como primer bot)"""
        if str(user_id) in self.users:
            del self.users[str(user_id)]
            self.save_users()
            return True
        return False
    
    # ===== SISTEMA DE HASHES DE SEGURIDAD =====
    def load_hashes(self):
        """Cargar hashes de seguridad"""
        try:
            if os.path.exists(self.hashes_file):
                with open(self.hashes_file, 'r', encoding='utf-8') as f:
                    self.file_hashes = json.load(f)
            else:
                self.file_hashes = {}
        except Exception as e:
            logger.error(f"Error cargando hashes: {e}")
            self.file_hashes = {}
    
    def save_hashes(self):
        """Guardar hashes de seguridad"""
        try:
            with open(self.hashes_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_hashes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando hashes: {e}")
    
    def create_file_hash(self, user_id, filename, file_type="downloads"):
        """Crear hash único de seguridad (como primer bot)"""
        # Crear hash único basado en múltiples factores
        timestamp = int(time.time())
        random_part = os.urandom(8).hex()
        
        hash_data = f"{user_id}_{filename}_{file_type}_{timestamp}_{HASH_SALT}_{random_part}"
        file_hash = hashlib.md5(hash_data.encode()).hexdigest()[:12]
        
        # Guardar hash con metadata
        hash_key = f"{user_id}_{filename}_{file_type}"
        self.file_hashes[file_hash] = {
            'user_id': user_id,
            'filename': filename,
            'file_type': file_type,
            'created_at': timestamp,
            'expires_at': timestamp + (self.HASH_EXPIRE_DAYS * 24 * 3600)
        }
        
        self.save_hashes()
        logger.info(f"🔐 Hash creado para {filename}: {file_hash} (expira en {self.HASH_EXPIRE_DAYS} días)")
        return file_hash
    
    def verify_hash(self, file_hash):
        """Verificar validez del hash (como primer bot)"""
        if file_hash not in self.file_hashes:
            return False, "Hash no encontrado"
        
        hash_data = self.file_hashes[file_hash]
        
        # Verificar expiración
        if time.time() > hash_data['expires_at']:
            del self.file_hashes[file_hash]
            self.save_hashes()
            return False, "Hash expirado"
        
        return True, hash_data
    
    def get_next_file_number(self, user_id, file_type="downloads"):
        """Obtiene el siguiente número de archivo para el usuario (PERSISTENTE)"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        next_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1
        self.save_metadata()
        return next_num
    
    def sanitize_filename(self, filename):
        """Limpia el nombre de archivo para que sea URL-safe - USANDO filename_utils"""
        return clean_for_url(filename)

    def format_bytes(self, size):
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def create_download_url(self, user_id, filename):
        """Crea una URL de descarga segura CON HASH - CORREGIDO"""
        # Usar clean_for_url en lugar de sanitize_filename para consistencia
        safe_filename = clean_for_url(filename)
        file_hash = self.create_file_hash(user_id, safe_filename, "downloads")
        
        # Codificar nombre para URL
        encoded_filename = get_url_safe_name(safe_filename)
        
        # Asegurar que RENDER_DOMAIN no termine con /
        base_url = RENDER_DOMAIN.rstrip('/')
        return f"{base_url}/download/{file_hash}?file={encoded_filename}"

    def create_packed_url(self, user_id, filename):
        """Crea una URL para archivos empaquetados CON HASH - CORREGIDO"""
        safe_filename = clean_for_url(filename)
        file_hash = self.create_file_hash(user_id, safe_filename, "packed")
        
        encoded_filename = get_url_safe_name(safe_filename)
        
        # Asegurar que RENDER_DOMAIN no termine con /
        base_url = RENDER_DOMAIN.rstrip('/')
        return f"{base_url}/packed/{file_hash}?file={encoded_filename}"

    def get_user_directory(self, user_id, file_type="downloads"):
        """Obtiene el directorio del usuario"""
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

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

    def list_user_files(self, user_id, file_type="downloads"):
        """Lista archivos del usuario con numeración PERSISTENTE"""
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
                    
                    # Generar URL con hash
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

    def register_file(self, user_id, original_name, stored_name, file_type="downloads"):
        """Registra un archivo en la metadata con número PERSISTENTE"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        file_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1
        
        self.metadata[user_key]["files"][str(file_num)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time()
        }
        self.save_metadata()
        
        # Actualizar estadísticas de usuario
        if str(user_id) in self.users:
            self.users[str(user_id)]['files_count'] = self.users[str(user_id)].get('files_count', 0) + 1
            self.save_users()
        
        logger.info(f"✅ Archivo registrado: #{file_num} - {original_name} para usuario {user_id}")
        return file_num

    def get_file_by_number(self, user_id, file_number, file_type="downloads"):
        """Obtiene información de archivo por número (PERSISTENTE)"""
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
            'file_type': file_type
        }

    def get_original_filename(self, user_id, stored_filename, file_type="downloads"):
        """Obtiene el nombre original del archivo basado en el nombre almacenado"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return stored_filename
        
        for file_data in self.metadata[user_key]["files"].values():
            if file_data["stored_name"] == stored_filename:
                return file_data["original_name"]
        
        return stored_filename

    def get_file_by_hash(self, file_hash):
        """Obtener archivo por hash (para servidor web)"""
        valid, hash_data = self.verify_hash(file_hash)
        if not valid:
            return None
        
        user_id = hash_data['user_id']
        filename = hash_data['filename']
        file_type = hash_data['file_type']
        
        user_dir = self.get_user_directory(user_id, file_type)
        file_path = os.path.join(user_dir, filename)
        
        if not os.path.exists(file_path):
            return None
        
        original_name = self.get_original_filename(user_id, filename, file_type)
        
        return {
            'path': file_path,
            'filename': filename,
            'original_name': original_name,
            'user_id': user_id,
            'file_type': file_type
        }

    def rename_file(self, user_id, file_number, new_name, file_type="downloads"):
        """Renombra un archivo"""
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
            
            # Usar clean_for_filesystem para el nombre en disco
            new_name_clean = clean_for_filesystem(new_name)
            
            user_dir = self.get_user_directory(user_id, file_type)
            old_path = os.path.join(user_dir, file_data["stored_name"])
            
            if not os.path.exists(old_path):
                return False, "Archivo físico no encontrado"
            
            _, ext = os.path.splitext(file_data["stored_name"])
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
            
            file_data["original_name"] = new_name
            file_data["stored_name"] = new_stored_name
            self.save_metadata()
            
            if file_type == "downloads":
                new_url = self.create_download_url(user_id, new_stored_name)
            else:
                new_url = self.create_packed_url(user_id, new_stored_name)
            
            return True, f"Archivo renombrado a: {new_name}", new_url
            
        except Exception as e:
            logger.error(f"Error renombrando archivo: {e}")
            return False, f"Error al renombrar: {str(e)}", None

    def delete_file_by_number(self, user_id, file_number, file_type="downloads"):
        """Elimina un archivo por número y REASIGNA números"""
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
            self.save_metadata()
            
            return True, f"Archivo #{file_number} '{file_data['original_name']}' eliminado y números reasignados"
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False, f"Error al eliminar archivo: {str(e)}"

    def delete_all_files(self, user_id, file_type="downloads"):
        """Elimina todos los archivos del usuario de un tipo específico"""
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
                self.save_metadata()
            
            return True, f"Se eliminaron {deleted_count} archivos {file_type} y se resetearon los números"
            
        except Exception as e:
            logger.error(f"Error eliminando todos los archivos: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

    def cleanup_expired_hashes(self):
        """Limpiar hashes expirados"""
        try:
            current_time = time.time()
            expired_hashes = []
            
            for file_hash, hash_data in self.file_hashes.items():
                if current_time > hash_data['expires_at']:
                    expired_hashes.append(file_hash)
            
            for file_hash in expired_hashes:
                del self.file_hashes[file_hash]
            
            if expired_hashes:
                self.save_hashes()
                logger.info(f"🧹 Hashes expirados limpiados: {len(expired_hashes)}")
            
            return len(expired_hashes)
        except Exception as e:
            logger.error(f"Error limpiando hashes: {e}")
            return 0

    def get_statistics(self):
        """Obtener estadísticas del sistema"""
        try:
            total_users = self.total_users_count()
            total_files_downloads = 0
            total_files_packed = 0
            total_size = 0
            
            for user_id in self.users:
                user_id_int = int(user_id)
                downloads = len(self.list_user_files(user_id_int, "downloads"))
                packed = len(self.list_user_files(user_id_int, "packed"))
                user_size = self.get_user_storage_usage(user_id_int)
                
                total_files_downloads += downloads
                total_files_packed += packed
                total_size += user_size
            
            return {
                'total_users': total_users,
                'total_files': total_files_downloads + total_files_packed,
                'total_files_downloads': total_files_downloads,
                'total_files_packed': total_files_packed,
                'total_size_bytes': total_size,
                'total_size_mb': total_size / (1024 * 1024),
                'active_hashes': len(self.file_hashes),
                'hash_expire_days': self.HASH_EXPIRE_DAYS
            }
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {}

file_service = FileService()