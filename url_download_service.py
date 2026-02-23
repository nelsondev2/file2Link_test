import os
import aiohttp
import aiofiles
import asyncio
import logging
import time
from urllib.parse import urlparse, unquote
from config import MAX_FILE_SIZE, DOWNLOAD_TIMEOUT, CHUNK_SIZE, MAX_RETRIES

logger = logging.getLogger(__name__)

class URLDownloadService:
    def __init__(self):
        self.active_downloads = {}
        self.session = None
    
    async def get_session(self):
        """Obtiene o crea una sesión aiohttp"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(total=DOWNLOAD_TIMEOUT, connect=30)
            self.session = aiohttp.ClientSession(timeout=timeout)
        return self.session
    
    async def get_filename_from_url(self, url, response):
        """Extrae el nombre del archivo de la URL o de los headers"""
        # Intentar obtener del header Content-Disposition
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition and 'filename=' in content_disposition:
            filename = content_disposition.split('filename=')[1].strip('"\'')
            return filename
        
        # Extraer de la URL
        parsed_url = urlparse(url)
        filename = os.path.basename(unquote(parsed_url.path))
        
        if filename and '.' in filename:
            return filename
        
        # Si no se pudo determinar, usar timestamp
        return f"download_{int(time.time())}"
    
    async def check_file_size(self, url):
        """Verifica el tamaño del archivo antes de descargar"""
        try:
            session = await self.get_session()
            async with session.head(url, allow_redirects=True) as response:
                if response.status == 200:
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        size = int(content_length)
                        if size > MAX_FILE_SIZE:
                            return False, size
                        return True, size
                return True, 0  # No se pudo determinar tamaño, continuar
        except Exception as e:
            logger.warning(f"No se pudo verificar tamaño del archivo: {e}")
            return True, 0
    
    async def download_from_url(self, url, file_path, progress_callback=None, user_id=None):
        """Descarga un archivo desde una URL directa"""
        try:
            if user_id:
                self.active_downloads[user_id] = True
            
            # Verificar tamaño
            can_download, file_size = await self.check_file_size(url)
            if not can_download:
                return False, 0, f"Archivo demasiado grande (límite: {MAX_FILE_SIZE/(1024*1024)}MB)"
            
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            session = await self.get_session()
            downloaded = 0
            start_time = time.time()
            last_callback_time = start_time
            
            async with session.get(url, allow_redirects=True) as response:
                if response.status != 200:
                    return False, 0, f"Error HTTP: {response.status}"
                
                # Si no se pudo obtener tamaño antes, intentar ahora
                if file_size == 0:
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        file_size = int(content_length)
                        if file_size > MAX_FILE_SIZE:
                            return False, 0, f"Archivo demasiado grande (límite: {MAX_FILE_SIZE/(1024*1024)}MB)"
                
                # Obtener nombre del archivo
                filename = await self.get_filename_from_url(url, response)
                
                async with aiofiles.open(file_path, 'wb') as f:
                    async for chunk in response.content.iter_chunked(CHUNK_SIZE):
                        if not chunk:
                            continue
                        
                        await f.write(chunk)
                        downloaded += len(chunk)
                        
                        current_time = time.time()
                        if current_time - last_callback_time >= 0.5 and progress_callback:
                            await progress_callback(downloaded, file_size or downloaded)
                            last_callback_time = current_time
                    
                    if progress_callback and downloaded > 0:
                        await progress_callback(downloaded, file_size or downloaded)
            
            elapsed = time.time() - start_time
            speed = downloaded / elapsed if elapsed > 0 else 0
            
            logger.info(f"URL descargada: {filename} en {elapsed:.1f}s ({speed/1024/1024:.1f} MB/s)")
            
            return True, downloaded, filename
            
        except asyncio.TimeoutError:
            return False, 0, "Timeout: La descarga tomó demasiado tiempo"
        except Exception as e:
            logger.error(f"Error descargando desde URL: {e}", exc_info=True)
            return False, 0, str(e)
        finally:
            if user_id and user_id in self.active_downloads:
                del self.active_downloads[user_id]
    
    async def close(self):
        """Cierra la sesión aiohttp"""
        if self.session and not self.session.closed:
            await self.session.close()

url_download_service = URLDownloadService()