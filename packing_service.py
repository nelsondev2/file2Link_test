import os
import asyncio
import time
import logging
import zipfile
from typing import List, Tuple, Optional, Dict

from config import BASE_DIR, MAX_PART_SIZE_MB
from load_manager import load_manager
from file_service import async_file_service

logger = logging.getLogger(__name__)

class AsyncPackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB
    
    async def pack_folder(self, user_id: int, split_size_mb: Optional[int] = None) -> Tuple[Optional[List[Dict]], str]:
        """Empaqueta carpeta del usuario de forma asíncrona"""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message
            
            try:
                user_dir = await async_file_service.get_user_directory(user_id, "downloads")
                
                loop = asyncio.get_event_loop()
                if not await loop.run_in_executor(None, os.path.exists, user_dir):
                    return None, "No tienes archivos para empaquetar"
                
                files = await loop.run_in_executor(None, os.listdir, user_dir)
                if not files:
                    return None, "No tienes archivos para empaquetar"
                
                packed_dir = await async_file_service.get_user_directory(user_id, "packed")
                await loop.run_in_executor(None, os.makedirs, packed_dir, exist_ok=True)
                
                timestamp = int(time.time())
                base_filename = f"packed_files_{timestamp}"
                
                if split_size_mb:
                    result = await self._pack_and_split_raw(user_id, user_dir, packed_dir, base_filename, split_size_mb)
                else:
                    result = await self._pack_single_simple(user_id, user_dir, packed_dir, base_filename)
                
                return result
                
            finally:
                load_manager.finish_process()
                
        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado: {e}")
            return None, f"Error al empaquetar: {str(e)}"
    
    async def _pack_single_simple(self, user_id: int, user_dir: str, packed_dir: str, base_filename: str) -> Tuple[List[Dict], str]:
        """Empaqueta en un solo archivo ZIP SIN compresión"""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")
        
        try:
            loop = asyncio.get_event_loop()
            
            all_files = []
            total_files = 0
            
            files = await loop.run_in_executor(None, os.listdir, user_dir)
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                if await loop.run_in_executor(None, os.path.isfile, file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            logger.info(f"Empaquetando {total_files} archivos en {output_file}")
            
            def create_zip():
                with zipfile.ZipFile(output_file, 'w', compression=zipfile.ZIP_STORED) as zipf:
                    for filename, file_path in all_files:
                        try:
                            zipf.write(file_path, filename)
                            logger.info(f"Agregado al ZIP: {filename}")
                        except Exception as e:
                            logger.error(f"Error agregando {filename} al ZIP: {e}")
                            continue
                return os.path.getsize(output_file)
            
            file_size = await loop.run_in_executor(None, create_zip)
            size_mb = file_size / (1024 * 1024)
            
            file_num = await async_file_service.register_file(user_id, f"{base_filename}.zip", f"{base_filename}.zip", "packed")
            
            await async_file_service.update_file_size(user_id, file_num, file_size, "packed")
            
            download_url = await async_file_service.create_packed_url(user_id, f"{base_filename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'size_mb': size_mb,
                'total_files': total_files
            }], f"Empaquetado completado: {total_files} archivos, {size_mb:.1f}MB"
            
        except Exception as e:
            if os.path.exists(output_file):
                await asyncio.get_event_loop().run_in_executor(None, os.remove, output_file)
            logger.error(f"Error en _pack_single_simple: {e}")
            raise e
    
    async def _pack_and_split_raw(self, user_id: int, user_dir: str, packed_dir: str, base_filename: str, split_size_mb: int) -> Tuple[List[Dict], str]:
        """Crea ZIP y lo divide en partes"""
        split_size_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        
        try:
            loop = asyncio.get_event_loop()
            
            all_files = []
            total_files = 0
            
            files = await loop.run_in_executor(None, os.listdir, user_dir)
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                if await loop.run_in_executor(None, os.path.isfile, file_path):
                    all_files.append((filename, file_path))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar"
            
            logger.info(f"Creando archivo ZIP y dividiendo en partes de {split_size_mb}MB")
            
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            
            def create_temp_zip():
                with zipfile.ZipFile(temp_zip_path, 'w', compression=zipfile.ZIP_STORED) as zipf:
                    for filename, file_path in all_files:
                        try:
                            zipf.write(file_path, filename)
                        except Exception as e:
                            logger.error(f"Error agregando {filename} al ZIP: {e}")
                            continue
                return os.path.getsize(temp_zip_path)
            
            zip_size = await loop.run_in_executor(None, create_temp_zip)
            logger.info(f"ZIP creado: {temp_zip_path} ({zip_size/(1024*1024):.2f}MB)")
            
            part_files = []
            
            def split_zip_file():
                nonlocal part_files
                parts = []
                part_num = 1
                with open(temp_zip_path, 'rb') as zip_file:
                    while True:
                        chunk = zip_file.read(split_size_bytes)
                        if not chunk:
                            break
                        
                        part_filename = f"{base_filename}.zip.{part_num:03d}"
                        part_path = os.path.join(packed_dir, part_filename)
                        
                        with open(part_path, 'wb') as part_file:
                            part_file.write(chunk)
                        
                        parts.append({
                            'filename': part_filename,
                            'size': len(chunk),
                            'part_num': part_num
                        })
                        part_num += 1
                
                os.remove(temp_zip_path)
                return parts
            
            parts = await loop.run_in_executor(None, split_zip_file)
            
            for part_info in parts:
                file_num = await async_file_service.register_file(
                    user_id, 
                    part_info['filename'], 
                    part_info['filename'], 
                    "packed"
                )
                
                await async_file_service.update_file_size(user_id, file_num, part_info['size'], "packed")
                
                download_url = await async_file_service.create_packed_url(user_id, part_info['filename'])
                
                part_files.append({
                    'number': file_num,
                    'filename': part_info['filename'],
                    'url': download_url,
                    'size_mb': part_info['size'] / (1024 * 1024),
                    'total_files': total_files if part_info['part_num'] == 1 else 0
                })
                
                logger.info(f"Parte {part_info['part_num']} creada: {part_info['filename']}")
            
            if not part_files:
                return None, "No se crearon partes. Error en la división del archivo."
            
            total_size_mb = sum(part['size_mb'] for part in part_files)
            
            return part_files, f"✅ Empaquetado completado: {len(part_files)} partes, {total_files} archivos, {total_size_mb:.1f}MB total"
            
        except Exception as e:
            logger.error(f"Error en _pack_and_split_raw: {e}", exc_info=True)
            temp_zip_path = os.path.join(packed_dir, f"temp_{base_filename}.zip")
            if os.path.exists(temp_zip_path):
                await asyncio.get_event_loop().run_in_executor(None, os.remove, temp_zip_path)
            raise e

# Instancia global
async_packing_service = AsyncPackingService()