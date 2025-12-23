import os
import zipfile
import time
import logging
from config import BASE_DIR, MAX_PART_SIZE_MB
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)

class SimplePackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
    
    def pack_folder(self, user_id, split_size_mb=None):
        """Empaqueta la carpeta del usuario y divide en partes ZIP multi-volumen"""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                user_dir = file_service.get_user_directory(user_id, "downloads")
                if not os.path.exists(user_dir):
                    return None, "No tienes archivos para empaquetar"
                
                files = os.listdir(user_dir)
                if not files:
                    return None, "No tienes archivos para empaquetar"
                
                packed_dir = file_service.get_user_directory(user_id, "packed")
                os.makedirs(packed_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                if split_size_mb:
                    result = self._create_multi_volume_zip(user_id, user_dir, packed_dir, base_filename, split_size_mb)
                else:
                    result = self._create_single_zip(user_id, user_dir, packed_dir, base_filename)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado: {e}")
            return None, f"Error al empaquetar: {str(e)}"
    
    def _create_single_zip(self, user_id, user_dir, packed_dir, base_filename):
        """Crea un solo archivo ZIP sin compresión"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            logger.info(f"Creando ZIP único con {total_files} archivos")
            
            # Crear ZIP sin compresión para minimizar CPU/RAM
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, file_path in all_files:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename}: {e}")
                        continue
            
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            
            # Registrar archivo
            file_num = file_service.register_file(user_id, f"{base_filename}.zip", f"{base_filename}.zip", "packed")
            download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb,
                'total_files': total_files
            }], f"Empaquetado completado: {total_files} archivos, {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"Error creando ZIP único: {e}")
            raise e
    
    def _create_multi_volume_zip(self, user_id, user_dir, packed_dir, base_filename, split_size_mb):
        """Crea un archivo ZIP multi-volumen (partes .zip.001, .zip.002, etc.)"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            # Obtener lista de archivos
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            logger.info(f"Creando ZIP multi-volumen de {split_size_mb}MB con {total_files} archivos")
            
            # Crear archivo ZIP temporal sin compresión
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            
            with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, file_path in all_files:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado al ZIP: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename}: {e}")
                        continue
            
            zip_size = os.path.getsize(temp_zip_path)
            logger.info(f"ZIP temporal creado: {zip_size/(1024*1024):.2f}MB")
            
            # Dividir el archivo ZIP en partes binarias
            part_files = []
            part_num = 1
            
            with open(temp_zip_path, 'rb') as zip_file:
                while True:
                    # Leer chunk del tamaño especificado
                    chunk = zip_file.read(split_size_bytes)
                    if not chunk:
                        break
                    
                    # Crear nombre de parte con formato estándar .zip.001
                    part_filename = f"{base_filename}.zip.{part_num:03d}"
                    part_path = os.path.join(packed_dir, part_filename)
                    
                    # Escribir la parte cruda
                    with open(part_path, 'wb') as part_file:
                        part_file.write(chunk)
                    
                    part_size = len(chunk)
                    part_size_mb = part_size / (1024 * 1024)
                    
                    # Registrar la parte
                    file_num = file_service.register_file(user_id, part_filename, part_filename, "packed")
                    download_url = file_service.create_packed_url(user_id, part_filename)
                    
                    part_files.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'size_mb': part_size_mb,
                        'total_files': total_files if part_num == 1 else 0
                    })
                    
                    logger.info(f"Parte {part_num} creada: {part_filename} ({part_size_mb:.2f}MB)")
                    part_num += 1
            
            # Eliminar el archivo ZIP temporal
            os.remove(temp_zip_path)
            
            # Verificar que se crearon partes
            if not part_files:
                return None, "No se crearon partes. Error en la división."
            
            # También crear un archivo .ZIP normal con solo la primera parte
            # Esto permite que algunos descompresores lo reconozcan directamente
            first_part_path = os.path.join(packed_dir, part_files[0]['filename'])
            zip_copy_path = os.path.join(packed_dir, f"{base_filename}.zip")
            
            # Copiar la primera parte como archivo .zip normal
            with open(first_part_path, 'rb') as src, open(zip_copy_path, 'wb') as dst:
                dst.write(src.read())
            
            # Registrar el archivo .zip normal también
            zip_file_num = file_service.register_file(user_id, f"{base_filename}.zip", f"{base_filename}.zip", "packed")
            zip_download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            zip_size_mb = os.path.getsize(zip_copy_path) / (1024 * 1024)
            
            # Agregar el archivo .zip normal a la lista
            part_files.insert(0, {
                'number': zip_file_num,
                'filename': f"{base_filename}.zip",
                'url': zip_download_url,
                'size_mb': zip_size_mb,
                'total_files': total_files
            })
            
            total_size_mb = sum(part['size_mb'] for part in part_files)
            
            return part_files, f"✅ ZIP multi-volumen creado: {len(part_files)-1} partes, {total_files} archivos, {total_size_mb:.1f}MB total"
            
        except Exception as e:
            logger.error(f"Error creando ZIP multi-volumen: {e}", exc_info=True)
            # Limpiar archivos temporales
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            if os.path.exists(temp_zip_path):
                os.remove(temp_zip_path)
            raise e
    
    def clear_packed_folder(self, user_id):
        """Elimina todos los archivos empaquetados del usuario"""
        try:
            packed_dir = file_service.get_user_directory(user_id, "packed")
            
            if not os.path.exists(packed_dir):
                return False, "No tienes archivos empaquetados para eliminar"
            
            files = os.listdir(packed_dir)
            if not files:
                return False, "No tienes archivos empaquetados para eliminar"
            
            deleted_count = 0
            for filename in files:
                file_path = os.path.join(packed_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            return True, f"Se eliminaron {deleted_count} archivos empaquetados"
            
        except Exception as e:
            logger.error(f"Error limpiando carpeta empaquetada: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

packing_service = SimplePackingService()