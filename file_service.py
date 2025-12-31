import os
import urllib.parse
import hashlib
import json
import time
import logging
import sys
from config import BASE_DIR, RENDER_DOMAIN

logger = logging.getLogger(__name__)

class FileService:
    def __init__(self):
        self.file_mappings = {}
        self.metadata_file = "file_metadata.json"
        self.load_metadata()
    
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
        """Limpia el nombre de archivo para que sea URL-safe"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100-len(ext)] + ext
        return filename

    def format_bytes(self, size):
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def create_download_url(self, user_id, filename):
        """Crea una URL de descarga válida"""
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        return f"{RENDER_DOMAIN}/storage/{user_id}/downloads/{encoded_filename}"  # ⬅️ CAMBIADO: static → storage

    def create_packed_url(self, user_id, filename):
        """Crea una URL para archivos empaquetados"""
        safe_filename = self.sanitize_filename(filename)
        encoded_filename = urllib.parse.quote(safe_filename)
        return f"{RENDER_DOMAIN}/storage/{user_id}/packed/{encoded_filename}"  # ⬅️ CAMBIADO: static → storage

    def get_user_directory(self, user_id, file_type="downloads"):
        """Obtiene el directorio del usuario"""
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)  # ⬅️ BASE_DIR ahora es "storage"
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

    def create_file_hash(self, user_id, filename):
        """Crea un hash único para el archivo"""
        data = f"{user_id}_{filename}_{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def list_user_files(self, user_id, file_type="downloads"):
        """Lista archivos del usuario con numeración PERSISTENTE"""
        user_dir = self.get_user_directory(user_id, file_type)
        if not os.path.exists(user_dir):
            return []
        
        files = []
        user_key = f"{user_id}_{file_type}"
        
        if user_key in self.metadata:
            # Obtener archivos existentes y ordenar por número
            existing_files = []
            for file_num, file_data in self.metadata[user_key]["files"].items():
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.exists(file_path):
                    existing_files.append((int(file_num), file_data))
            
            # Ordenar por número (NO reasignar números)
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

    def register_file(self, user_id, original_name, stored_name, file_type="downloads"):
        """Registra un archivo en la metadata con número PERSISTENTE - CORREGIDO"""
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}
        
        # CORREGIDO: Usar el número actual SIN restar 1
        file_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1
        
        self.metadata[user_key]["files"][str(file_num)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time()
        }
        self.save_metadata()
        
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
            
            new_name = self.sanitize_filename(new_name)
            
            user_dir = self.get_user_directory(user_id, file_type)
            old_path = os.path.join(user_dir, file_data["stored_name"])
            
            if not os.path.exists(old_path):
                return False, "Archivo físico no encontrado"
            
            _, ext = os.path.splitext(file_data["stored_name"])
            new_stored_name = new_name + ext
            
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
            
            # ELIMINAR la entrada de metadata y REASIGNAR números
            del self.metadata[user_key]["files"][str(file_number)]
            
            # Reasignar números consecutivos
            remaining_files = sorted(
                [(int(num), data) for num, data in self.metadata[user_key]["files"].items()],
                key=lambda x: x[0]
            )
            
            # Resetear metadata
            self.metadata[user_key]["files"] = {}
            
            # Reasignar números comenzando desde 1
            new_number = 1
            for old_num, file_data in remaining_files:
                self.metadata[user_key]["files"][str(new_number)] = file_data
                new_number += 1
            
            # Actualizar next_number
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
            
            # Resetear metadata para este tipo de archivo
            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                self.metadata[user_key] = {"next_number": 1, "files": {}}
                self.save_metadata()
            
            return True, f"Se eliminaron {deleted_count} archivos {file_type} y se resetearon los números"
            
        except Exception as e:
            logger.error(f"Error eliminando todos los archivos: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

file_service = FileService()
