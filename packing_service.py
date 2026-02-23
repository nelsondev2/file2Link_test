import os
import math
import logging
import time
import zipfile
from config import BASE_DIR, MAX_PART_SIZE_MB
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)

class AdvancedPackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
        self.buffer_size = 64 * 1024  # 64KB buffer optimizado
    
    def pack_folder(self, user_id, split_size_mb=None):
        """Empaqueta archivos en ZIP o divide el ZIP en partes válidas"""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                user_dir = file_service.get_user_directory(user_id, "downloads")
                if not os.path.exists(user_dir):
                    return None, "No tienes archivos para empaquetar"
                
                files = [f for f in os.listdir(user_dir) 
                        if os.path.isfile(os.path.join(user_dir, f))]
                
                if not files:
                    return None, "No tienes archivos para empaquetar"
                
                packed_dir = file_service.get_user_directory(user_id, "packed")
                os.makedirs(packed_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                if split_size_mb:
                    # Crear ZIP y luego dividirlo en partes válidas
                    result = self._create_and_split_zip(user_id, user_dir, packed_dir, 
                                                       base_filename, split_size_mb, files)
                else:
                    # Crear un único archivo ZIP
                    result = self._pack_single_zip(user_id, user_dir, packed_dir, 
                                                  base_filename, files)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado avanzado: {e}")
            return None, f"Error al empaquetar: {str(e)}"
    
    def _pack_single_zip(self, user_id, user_dir, packed_dir, base_filename, files):
        """Crea un único archivo ZIP sin compresión"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            logger.info(f"Creando ZIP con {len(files)} archivos...")
            
            with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename in files:
                    file_path = os.path.join(user_dir, filename)
                    try:
                        zipf.write(file_path, filename)
                        logger.debug(f"Agregado: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename}: {e}")
                        continue
            
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            
            # Registrar archivo
            file_num = file_service.register_file(user_id, f"{base_filename}.zip", 
                                                f"{base_filename}.zip", "packed")
            
            download_url = file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb,
                'total_files': len(files)
            }], f"Empaquetado completado: {len(files)} archivos, {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"Error en ZIP simple: {e}")
            raise e
    
    def _create_and_split_zip(self, user_id, user_dir, packed_dir, base_filename, 
                             split_size_mb, files):
        """Crea un ZIP válido y lo divide en partes que se pueden unir y extraer"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            # PASO 1: Crear el archivo ZIP temporal (VÁLIDO)
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            
            logger.info(f"Creando ZIP temporal con {len(files)} archivos...")
            
            with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename in files:
                    file_path = os.path.join(user_dir, filename)
                    try:
                        zipf.write(file_path, filename)
                        logger.debug(f"Agregado al ZIP: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            zip_size = os.path.getsize(temp_zip_path)
            logger.info(f"ZIP creado: {temp_zip_path} ({zip_size/(1024*1024):.2f}MB)")
            
            # PASO 2: Dividir el archivo ZIP en partes (MÉTODO SEGURO)
            part_files_result = []
            parts_info = []
            part_num = 1
            
            with open(temp_zip_path, 'rb') as zip_file:
                while True:
                    # Crear nombre de parte (.001, .002, etc.)
                    part_filename = f"{base_filename}.zip.{part_num:03d}"
                    part_path = os.path.join(packed_dir, part_filename)
                    
                    # Leer exactamente split_size_bytes o lo que quede
                    chunk = zip_file.read(split_size_bytes)
                    if not chunk:
                        break
                    
                    # Escribir la parte
                    with open(part_path, 'wb') as part_file:
                        part_file.write(chunk)
                    
                    part_size = len(chunk)
                    part_size_mb = part_size / (1024 * 1024)
                    
                    # Registrar la parte
                    file_num = file_service.register_file(user_id, part_filename, part_filename, "packed")
                    download_url = file_service.create_packed_url(user_id, part_filename)
                    
                    parts_info.append((part_filename, part_size, download_url))
                    
                    part_files_result.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'size_mb': part_size_mb,
                        'total_files': len(files) if part_num == 1 else 0
                    })
                    
                    logger.info(f"Parte {part_num} creada: {part_filename} ({part_size_mb:.2f}MB)")
                    part_num += 1
            
            # PASO 3: Eliminar el archivo ZIP temporal
            os.remove(temp_zip_path)
            logger.info(f"Archivo temporal eliminado: {temp_zip_path}")
            
            # PASO 4: Crear archivo .txt con lista de enlaces
            self._create_parts_list_file(user_id, packed_dir, base_filename, parts_info, len(files))
            
            # PASO 5: Verificar que el primer archivo sea un ZIP válido
            # (opcional pero recomendado para debugging)
            if part_files_result:
                first_part = os.path.join(packed_dir, part_files_result[0]['filename'])
                if os.path.exists(first_part):
                    try:
                        # Intentar leer el primer archivo como ZIP
                        with zipfile.ZipFile(first_part, 'r') as test_zip:
                            # Solo verificar que se pueda abrir
                            test_files = test_zip.namelist()
                            logger.info(f"Primera parte es ZIP válido: {len(test_files)} archivos listados")
                    except zipfile.BadZipFile:
                        logger.warning("La primera parte NO es un ZIP válido. Puede necesitar unión completa.")
                    except Exception as e:
                        logger.warning(f"No se pudo verificar ZIP: {e}")
            
            total_size_mb = sum(part['size_mb'] for part in part_files_result)
            
            return part_files_result, (f"✅ Empaquetado completado: {len(part_files_result)} partes, "
                                     f"{len(files)} archivos, {total_size_mb:.1f}MB total")
            
        except Exception as e:
            logger.error(f"Error en creación y división de ZIP: {e}", exc_info=True)
            # Limpiar archivos en caso de error
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            if os.path.exists(temp_zip_path):
                try:
                    os.remove(temp_zip_path)
                except:
                    pass
            
            # Limpiar partes parciales
            for part_num in range(1, 100):
                part_filename = f"{base_filename}.zip.{part_num:03d}"
                part_path = os.path.join(packed_dir, part_filename)
                if os.path.exists(part_path):
                    try:
                        os.remove(part_path)
                    except:
                        pass
            
            raise e
    
    def _create_parts_list_file(self, user_id, packed_dir, base_filename, parts_info, total_files):
        """Crea archivo .txt con lista de enlaces"""
        list_filename = f"{base_filename}.txt"
        list_path = os.path.join(packed_dir, list_filename)
        
        try:
            with open(list_path, 'w', encoding='utf-8') as f:
                # Encabezado simple
                f.write(f"Lista de partes para: {base_filename}\n")
                f.write(f"Total archivos originales: {total_files}\n")
                f.write(f"Partes generadas: {len(parts_info)}\n")
                f.write("=" * 50 + "\n\n")
                
                # Listar cada parte con su enlace
                for i, (part_filename, part_size, part_url) in enumerate(parts_info, 1):
                    part_size_mb = part_size / (1024 * 1024)
                    f.write(f"Parte {i:03d}: {part_filename}\n")
                    f.write(f"Tamaño: {part_size_mb:.2f} MB\n")
                    f.write(f"Enlace: {part_url}\n\n")
            
            # Registrar archivo de lista en el sistema
            file_service.register_file(user_id, list_filename, list_filename, "packed")
            
            logger.info(f"Archivo de lista creado: {list_filename} ({len(parts_info)} enlaces)")
            return list_filename
            
        except Exception as e:
            logger.error(f"Error creando archivo de lista: {e}")
            return None
    
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


packing_service = AdvancedPackingService()
