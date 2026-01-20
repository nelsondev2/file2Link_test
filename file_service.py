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
    
    def load_users(self):
        """Cargar usuarios desde JSON"""
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
    
    def load_hashes(self):
        """Cargar hashes de seguridad - CORREGIDO"""
        try:
            if os.path.exists(self.hashes_file):
                with open(self.hashes_file, 'r', encoding='utf-8') as f:
                    self.file_hashes = json.load(f)
                    logger.info(f"📂 Hashes cargados: {len(self.file_hashes)} hashes en memoria")
            else:
                self.file_hashes = {}
                logger.info("📂 No hay archivo de hashes, creando nuevo")
        except Exception as e:
            logger.error(f"Error cargando hashes: {e}")
            self.file_hashes = {}
    
    def save_hashes(self):
        """Guardar hashes de seguridad"""
        try:
            with open(self.hashes_file, 'w', encoding='utf-8') as f:
                json.dump(self.file_hashes, f, ensure_ascii=False, indent=2)
            logger.debug(f"💾 Hashes guardados: {len(self.file_hashes)} hashes")
        except Exception as e:
            logger.error(f"Error guardando hashes: {e}")
    
    def create_file_hash(self, user_id, filename, file_type="downloads"):
        """Crear hash único de seguridad - CORREGIDO Y MEJORADO"""
        try:
            timestamp = int(time.time())
            random_part = os.urandom(8).hex()
            
            # Crear hash más robusto
            hash_data = f"{user_id}_{filename}_{file_type}_{timestamp}_{HASH_SALT}_{random_part}"
            file_hash = hashlib.sha256(hash_data.encode()).hexdigest()[:12]
            
            # Asegurar que el filename esté limpio
            safe_filename = clean_for_url(filename)
            
            # Guardar hash con metadata completa
            self.file_hashes[file_hash] = {
                'user_id': int(user_id),  # Asegurar que sea int
                'filename': safe_filename,  # Nombre limpio
                'original_filename': filename,  # Nombre original
                'file_type': file_type,
                'created_at': timestamp,
                'expires_at': timestamp + (self.HASH_EXPIRE_DAYS * 24 * 3600)
            }
            
            self.save_hashes()
            logger.info(f"🔐 Hash creado para {filename}: {file_hash} (expira en {self.HASH_EXPIRE_DAYS} días)")
            logger.debug(f"📝 Detalles hash: usuario={user_id}, tipo={file_type}, filename={safe_filename}")
            
            return file_hash
            
        except Exception as e:
            logger.error(f"Error creando hash: {e}")
            # Fallback: hash simple
            fallback_hash = hashlib.md5(f"{user_id}_{filename}_{int(time.time())}".encode()).hexdigest()[:12]
            return fallback_hash
    
    def verify_hash(self, file_hash):
        """Verificar validez del hash - CORREGIDO Y MEJORADO"""
        try:
            logger.info(f"🔍 Verificando hash: {file_hash}")
            logger.debug(f"📂 Hashes en memoria: {len(self.file_hashes)}")
            
            if file_hash not in self.file_hashes:
                logger.warning(f"❌ Hash no encontrado: {file_hash}")
                logger.debug(f"Hashes disponibles: {list(self.file_hashes.keys())[:5]}...")
                return False, "Hash no encontrado"
            
            hash_data = self.file_hashes[file_hash]
            current_time = time.time()
            
            # Verificar expiración
            if 'expires_at' not in hash_data:
                logger.warning(f"⚠️ Hash sin expiración: {file_hash}, eliminando")
                del self.file_hashes[file_hash]
                self.save_hashes()
                return False, "Hash sin expiración"
            
            if current_time > hash_data['expires_at']:
                logger.info(f"⌛ Hash expirado: {file_hash}")
                del self.file_hashes[file_hash]
                self.save_hashes()
                return False, "Hash expirado"
            
            # Verificar estructura de datos
            required_fields = ['user_id', 'filename', 'file_type']
            for field in required_fields:
                if field not in hash_data:
                    logger.warning(f"⚠️ Hash corrupto, falta campo {field}: {file_hash}")
                    del self.file_hashes[file_hash]
                    self.save_hashes()
                    return False, f"Hash corrupto, falta {field}"
            
            logger.info(f"✅ Hash válido: {file_hash} para usuario {hash_data['user_id']}")
            return True, hash_data
            
        except Exception as e:
            logger.error(f"❌ Error verificando hash {file_hash}: {e}", exc_info=True)
            return False, f"Error interno: {str(e)}"
    
    def get_file_by_hash(self, file_hash):
        """Obtener archivo por hash (para servidor web) - CORREGIDO"""
        try:
            logger.info(f"🔍 Buscando archivo por hash: {file_hash}")
            
            valid, hash_data = self.verify_hash(file_hash)
            if not valid:
                logger.warning(f"❌ Hash inválido: {file_hash}")
                return None
            
            user_id = hash_data['user_id']
            filename = hash_data['filename']
            file_type = hash_data['file_type']
            
            logger.debug(f"📝 Datos hash: usuario={user_id}, archivo={filename}, tipo={file_type}")
            
            user_dir = self.get_user_directory(user_id, file_type)
            file_path = os.path.join(user_dir, filename)
            
            if not os.path.exists(file_path):
                logger.warning(f"❌ Archivo no encontrado en disco: {file_path}")
                
                # Buscar por nombre original si no encuentra
                original_name = hash_data.get('original_filename', filename)
                alt_path = os.path.join(user_dir, original_name)
                if os.path.exists(alt_path):
                    logger.info(f"✅ Encontrado por nombre original: {original_name}")
                    file_path = alt_path
                    filename = original_name
                else:
                    logger.error(f"❌ Archivo no existe en ninguna variante: {filename} o {original_name}")
                    return None
            
            # Obtener nombre original del archivo
            original_name = self.get_original_filename(user_id, filename, file_type)
            if not original_name or original_name == filename:
                original_name = hash_data.get('original_filename', filename)
            
            logger.info(f"✅ Archivo encontrado: {original_name} en {file_path}")
            
            return {
                'path': file_path,
                'filename': filename,
                'original_name': original_name,
                'user_id': user_id,
                'file_type': file_type,
                'hash_data': hash_data
            }
            
        except Exception as e:
            logger.error(f"❌ Error en get_file_by_hash: {e}", exc_info=True)
            return None
    
    def get_user_directory(self, user_id, file_type="downloads"):
        """Obtiene el directorio del usuario - CORREGIDO"""
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir
    
    def create_download_url(self, user_id, filename):
        """Crea una URL de descarga segura CON HASH - CORREGIDO"""
        try:
            # Usar clean_for_url para consistencia
            safe_filename = clean_for_url(filename)
            file_hash = self.create_file_hash(user_id, safe_filename, "downloads")
            
            if not file_hash:
                logger.error(f"❌ No se pudo crear hash para {filename}")
                return None
            
            # Codificar nombre para URL
            encoded_filename = get_url_safe_name(safe_filename)
            
            # Asegurar que RENDER_DOMAIN no termine con /
            base_url = RENDER_DOMAIN.rstrip('/')
            url = f"{base_url}/download/{file_hash}?file={encoded_filename}"
            
            logger.info(f"🔗 URL creada: {url[:50]}...")
            return url
            
        except Exception as e:
            logger.error(f"❌ Error creando URL: {e}")
            return None
    
    def create_packed_url(self, user_id, filename):
        """Crea una URL para archivos empaquetados CON HASH - CORREGIDO"""
        try:
            safe_filename = clean_for_url(filename)
            file_hash = self.create_file_hash(user_id, safe_filename, "packed")
            
            if not file_hash:
                logger.error(f"❌ No se pudo crear hash para {filename}")
                return None
            
            encoded_filename = get_url_safe_name(safe_filename)
            
            base_url = RENDER_DOMAIN.rstrip('/')
            url = f"{base_url}/packed/{file_hash}?file={encoded_filename}"
            
            logger.info(f"📦 URL packed creada: {url[:50]}...")
            return url
            
        except Exception as e:
            logger.error(f"❌ Error creando URL packed: {e}")
            return None
    
    def list_user_files(self, user_id, file_type="downloads"):
        """Lista archivos del usuario con numeración PERSISTENTE - CORREGIDO"""
        try:
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
                        
                        # Generar URL con hash - CON VALIDACIÓN
                        if file_type == "downloads":
                            download_url = self.create_download_url(user_id, file_data["stored_name"])
                        else:
                            download_url = self.create_packed_url(user_id, file_data["stored_name"])
                        
                        if download_url:
                            files.append({
                                'number': file_number,
                                'name': file_data["original_name"],
                                'stored_name': file_data["stored_name"],
                                'size': size,
                                'size_mb': size / (1024 * 1024),
                                'url': download_url,
                                'file_type': file_type
                            })
                        else:
                            logger.warning(f"⚠️ No se pudo generar URL para {file_data['stored_name']}")
            
            return files
            
        except Exception as e:
            logger.error(f"Error listando archivos: {e}")
            return []
    
    def register_file(self, user_id, original_name, stored_name, file_type="downloads"):
        """Registra un archivo en la metadata con número PERSISTENTE - CORREGIDO"""
        try:
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
            
        except Exception as e:
            logger.error(f"Error registrando archivo: {e}")
            return 1  # Fallback
    
    def cleanup_expired_hashes(self):
        """Limpiar hashes expirados - CORREGIDO"""
        try:
            current_time = time.time()
            expired_hashes = []
            
            for file_hash, hash_data in self.file_hashes.items():
                if 'expires_at' in hash_data and current_time > hash_data['expires_at']:
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

file_service = FileService()