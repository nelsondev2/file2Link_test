import asyncio
import os
import time
import logging
import aiofiles
from pyrogram.errors import FloodWait
from config import DOWNLOAD_BUFFER_SIZE, DOWNLOAD_TIMEOUT, MAX_RETRIES, CHUNK_SIZE

logger = logging.getLogger(__name__)

class FastDownloadService:
    def __init__(self):
        self.active_downloads = {}
    
    async def download_file_fast(self, client, message, file_path, progress_callback=None):
        """Descarga archivos a máxima velocidad con buffer optimizado"""
        try:
            user_id = message.from_user.id
            self.active_downloads[user_id] = True
            
            file_obj = None
            file_size = 0
            
            if message.document:
                file_obj = message.document
                file_size = file_obj.file_size or 0
            elif message.video:
                file_obj = message.video
                file_size = file_obj.file_size or 0
            elif message.audio:
                file_obj = message.audio
                file_size = file_obj.file_size or 0
            elif message.photo:
                file_obj = message.photo[-1]
                file_size = file_obj.file_size or 0
            
            if not file_obj:
                raise ValueError("No se pudo obtener el objeto de archivo")
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            timeout = DOWNLOAD_TIMEOUT
            if file_size > 500 * 1024 * 1024:
                timeout = 7200
            
            logger.info(f"Iniciando descarga rápida: {os.path.basename(file_path)} ({file_size/1024/1024:.1f} MB)")
            
            start_time = time.time()
            downloaded = 0
            last_callback_time = start_time
            
            async with aiofiles.open(file_path, 'wb') as f:
                async for chunk in client.stream_media(file_obj, limit=DOWNLOAD_BUFFER_SIZE):
                    if not chunk:
                        continue
                    
                    await f.write(chunk)
                    downloaded += len(chunk)
                    
                    current_time = time.time()
                    if current_time - last_callback_time >= 0.5 and progress_callback:
                        await progress_callback(downloaded, file_size)
                        last_callback_time = current_time
                
                if progress_callback and downloaded > 0:
                    await progress_callback(downloaded, file_size)
            
            elapsed = time.time() - start_time
            speed = downloaded / elapsed if elapsed > 0 else 0
            
            logger.info(f"Descarga completada: {os.path.basename(file_path)} en {elapsed:.1f}s ({speed/1024/1024:.1f} MB/s)")
            
            return True, downloaded
            
        except FloodWait as e:
            logger.warning(f"FloodWait: Esperando {e.value} segundos")
            await asyncio.sleep(e.value + 1)
            return await self.download_file_fast(client, message, file_path, progress_callback)
            
        except Exception as e:
            logger.error(f"Error en descarga rápida: {e}", exc_info=True)
            return False, 0
            
        finally:
            if user_id in self.active_downloads:
                del self.active_downloads[user_id]
    
    async def download_with_retry(self, client, message, file_path, progress_callback=None, max_retries=MAX_RETRIES):
        """Descarga con reintentos automáticos"""
        for attempt in range(max_retries + 1):
            try:
                success, downloaded = await self.download_file_fast(
                    client, message, file_path, progress_callback
                )
                
                if success:
                    return True, downloaded
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt
                    logger.info(f"Reintentando descarga en {wait_time}s (intento {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
        
        return False, 0

fast_download_service = FastDownloadService()
