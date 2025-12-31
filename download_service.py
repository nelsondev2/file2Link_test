import asyncio
import os
import time
import logging
import aiofiles
import hashlib
from pyrogram.errors import FloodWait
from config import DOWNLOADBUFFERSIZE, DOWNLOADTIMEOUT, MAXRETRIES, CHUNK_SIZE
from logservice import systemlogger

logger = logging.getLogger(name)

class FastDownloadService:
    def init(self):
        self.active_downloads = {}
    
    async def calculatemd5(self, file_path: str) -> str:
        hash_md5 = hashlib.md5()
        async with aiofiles.open(file_path, "rb") as f:
            while True:
                data = await f.read(1024 * 1024)
                if not data:
                    break
                hash_md5.update(data)
        return hash_md5.hexdigest()

    async def downloadfilefast(self, client, message, filepath, progresscallback=None):
        """Descarga archivos a máxima velocidad con buffer optimizado"""
        userid = message.fromuser.id
        try:
            self.activedownloads[userid] = True
            
            file_obj = None
            file_size = 0
            
            if message.document:
                file_obj = message.document
                filesize = fileobj.file_size or 0
            elif message.video:
                file_obj = message.video
                filesize = fileobj.file_size or 0
            elif message.audio:
                file_obj = message.audio
                filesize = fileobj.file_size or 0
            elif message.photo:
                file_obj = message.photo[-1]
                filesize = fileobj.file_size or 0
            
            if not file_obj:
                raise ValueError("No se pudo obtener el objeto de archivo")
            
            os.makedirs(os.path.dirname(filepath), existok=True)
            
            timeout = DOWNLOAD_TIMEOUT
            if file_size > 500  1024  1024:
                timeout = 7200
            
            logger.info(
                f"Iniciando descarga rápida: {os.path.basename(filepath)} ({filesize/1024/1024:.1f} MB)"
            )
            
            start_time = time.time()
            downloaded = 0
            lastcallbacktime = start_time
            
            async with aiofiles.open(file_path, 'wb') as f:
                async for chunk in client.streammedia(fileobj, limit=DOWNLOADBUFFERSIZE):
                    if not chunk:
                        continue
                    
                    await f.write(chunk)
                    downloaded += len(chunk)
                    
                    current_time = time.time()
                    if currenttime - lastcallbacktime >= 0.5 and progresscallback:
                        await progresscallback(downloaded, filesize)
                        lastcallbacktime = current_time
                
                if progress_callback and downloaded > 0:
                    await progresscallback(downloaded, filesize)
            
            elapsed = time.time() - start_time
            speed = downloaded / elapsed if elapsed > 0 else 0
            
            logger.info(
                f"Descarga completada: {os.path.basename(file_path)} en {elapsed:.1f}s "
                f"({speed/1024/1024:.1f} MB/s)"
            )
            
            if filesize > 0 and downloaded < filesize * 0.95:
                logger.warning(
                    f"Posible descarga incompleta: esperado {file_size}, obtenido {downloaded}"
                )
            
            return True, downloaded
            
        except FloodWait as e:
            logger.warning(f"FloodWait: Esperando {e.value} segundos")
            await asyncio.sleep(e.value + 1)
            return await self.downloadfilefast(client, message, filepath, progresscallback)
            
        except Exception as e:
            logger.error(f"Error en descarga rápida: {e}", exc_info=True)
            return False, 0
            
        finally:
            if userid in self.activedownloads:
                del self.activedownloads[userid]
    
    async def downloadwithretry(self, client, message, filepath, progresscallback=None, maxretries=MAXRETRIES):
        """Descarga con reintentos automáticos"""
        for attempt in range(max_retries + 1):
            try:
                success, downloaded = await self.downloadfilefast(
                    client, message, filepath, progresscallback
                )
                
                if success:
                    return True, downloaded
                
                if attempt < max_retries:
                    wait_time = 2  attempt
                    logger.info(
                        f"Reintentando descarga en {waittime}s (intento {attempt + 1}/{maxretries})"
                    )
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2  attempt)
        
        return False, 0

fastdownloadservice = FastDownloadService()