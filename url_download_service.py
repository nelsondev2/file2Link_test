import os
import aiohttp
import aiofiles
import asyncio
import logging
import time
import re
import unicodedata
from urllib.parse import urlparse, unquote, quote
from typing import Optional, Tuple
from config import MAX_FILE_SIZE, DOWNLOAD_TIMEOUT, CHUNK_SIZE, MAX_RETRIES, DOWNLOAD_BUFFER_SIZE

logger = logging.getLogger(__name__)

class URLDownloadService:
    def __init__(self):
        self.active_downloads = {}
        self.session = None
        self.semaphore = asyncio.Semaphore(3)  # Máximo 3 descargas concurrentes
        self.dns_cache = {}
        
    async def get_session(self) -> aiohttp.ClientSession:
        """Obtiene o crea una sesión aiohttp optimizada"""
        if self.session is None or self.session.closed:
            timeout = aiohttp.ClientTimeout(
                total=DOWNLOAD_TIMEOUT,
                connect=30,
                sock_read=60,
                sock_connect=30
            )
            
            # Configurar conexiones optimizadas
            connector = aiohttp.TCPConnector(
                limit=10,                    # Máximo 10 conexiones totales
                limit_per_host=3,             # Máximo 3 por host
                ttl_dns_cache=300,             # Cache DNS por 5 minutos
                enable_cleanup_closed=True,
                force_close=False,
                ssl=False                      # Deshabilitar SSL para mayor velocidad (si es posible)
            )
            
            self.session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': '*/*',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive'
                }
            )
        return self.session
    
    def extract_filename_from_url(self, url: str) -> Optional[str]:
        """Extrae el nombre del archivo de la URL de manera inteligente"""
        try:
            parsed = urlparse(url)
            path = unquote(parsed.path)
            query = parsed.query
            
            # Primero buscar en parámetros de query
            if query:
                params = query.split('&')
                for param in params:
                    if '=' in param:
                        key, value = param.split('=', 1)
                        if key.lower() in ['name', 'file', 'filename', 'title', 'f']:
                            filename = unquote(value)
                            if filename:
                                # Limpiar el nombre
                                filename = filename.replace('+', ' ')
                                return self.sanitize_filename(filename)
            
            # Si no hay en query, usar el path
            filename = os.path.basename(path)
            if filename and filename != '/':
                filename = unquote(filename)
                # Limpiar parámetros después de ?
                if '?' in filename:
                    filename = filename.split('?')[0]
                return self.sanitize_filename(filename)
            
            # Si no se encontró nada, generar nombre basado en dominio
            domain = parsed.netloc.replace('www.', '').split('.')[0]
            return f"{domain}_{int(time.time())}.mp4"
            
        except Exception as e:
            logger.warning(f"Error extrayendo nombre de URL: {e}")
            return f"download_{int(time.time())}.mp4"
    
    async def get_filename_from_response(self, url: str, response: aiohttp.ClientResponse) -> str:
        """Obtiene el nombre del archivo de los headers o URL"""
        # Intentar obtener del header Content-Disposition
        content_disposition = response.headers.get('Content-Disposition')
        if content_disposition:
            # Buscar filename* (UTF-8) primero
            filename_star = re.search(r"filename\*=UTF-8''([^;]+)", content_disposition)
            if filename_star:
                try:
                    filename = unquote(filename_star.group(1))
                    return self.sanitize_filename(filename)
                except:
                    pass
            
            # Buscar filename normal
            filename_match = re.search(r'filename="([^"]+)"', content_disposition)
            if not filename_match:
                filename_match = re.search(r"filename=([^;]+)", content_disposition)
            
            if filename_match:
                filename = filename_match.group(1).strip('"\'')
                return self.sanitize_filename(filename)
        
        # Si no hay header, usar el de la URL
        return self.sanitize_filename(self.extract_filename_from_url(url))
    
    def sanitize_filename(self, filename: str) -> str:
        """Limpia el nombre de archivo de caracteres conflictivos de forma más agresiva"""
        if not filename:
            return f"download_{int(time.time())}.mp4"
        
        # Reemplazar caracteres problemáticos en sistemas de archivos
        # Incluye corchetes, paréntesis y otros caracteres especiales
        filename = re.sub(r'[<>:"/\\|?*\[\](){}!@#$%^&+=,]', '_', filename)
        
        # Eliminar caracteres de control
        filename = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', filename)
        
        # Reemplazar espacios y guiones bajos múltiples por uno solo
        filename = re.sub(r'[\s_]+', '_', filename)
        
        # Eliminar acentos y caracteres especiales
        filename = unicodedata.normalize('NFKD', filename)
        filename = filename.encode('ASCII', 'ignore').decode('ASCII')
        
        # Eliminar puntos, espacios y guiones al inicio/final
        filename = filename.strip('. _-')
        
        # Asegurar que el nombre no esté vacío
        if not filename:
            filename = f"download_{int(time.time())}"
        
        # Asegurar que tenga extensión
        if '.' not in filename:
            # Detectar por Content-Type o extensión común
            if any(ext in filename.lower() for ext in ['.mp4', '.mkv', '.avi', '.mov']):
                pass  # Ya tiene extensión
            else:
                # Intentar detectar por tipo común de video
                if 'video' in filename.lower() or 'episode' in filename.lower():
                    filename += '.mp4'
                else:
                    filename += '.bin'
        
        # Limitar longitud
        if len(filename) > 200:
            name, ext = os.path.splitext(filename)
            filename = name[:195] + ext
        
        return filename
    
    async def check_file_size(self, url: str) -> Tuple[bool, int]:
        """Verifica el tamaño del archivo antes de descargar"""
        try:
            session = await self.get_session()
            
            # HEAD request con timeout reducido
            async with session.head(url, allow_redirects=True, timeout=15) as response:
                if response.status in (200, 301, 302, 303, 307, 308):
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        size = int(content_length)
                        if size > MAX_FILE_SIZE:
                            return False, size
                        return True, size
                    
                    # Intentar con GET y range=0-0
                    async with session.get(url, headers={'Range': 'bytes=0-0'}, timeout=15) as range_resp:
                        if range_resp.status in (206, 200):
                            content_range = range_resp.headers.get('Content-Range')
                            if content_range:
                                total = int(content_range.split('/')[-1])
                                if total > MAX_FILE_SIZE:
                                    return False, total
                                return True, total
                
                return True, 0  # No se pudo determinar, continuar
                
        except Exception as e:
            logger.warning(f"No se pudo verificar tamaño del archivo: {e}")
            return True, 0
    
    async def download_from_url(
        self, 
        url: str, 
        file_path: str, 
        progress_callback=None, 
        user_id=None
    ) -> Tuple[bool, int, str]:
        """Descarga un archivo desde una URL directa con máxima velocidad"""
        
        async with self.semaphore:  # Limitar concurrencia
            temp_file_path = None
            try:
                if user_id:
                    self.active_downloads[user_id] = True
                
                # Verificar tamaño
                can_download, file_size = await self.check_file_size(url)
                if not can_download:
                    size_mb = file_size / (1024 * 1024)
                    max_mb = MAX_FILE_SIZE / (1024 * 1024)
                    return False, 0, f"Archivo demasiado grande: {size_mb:.1f}MB (límite: {max_mb:.0f}MB)"
                
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                session = await self.get_session()
                downloaded = 0
                start_time = time.time()
                last_callback_time = start_time
                filename = None
                
                # Headers para descarga optimizada
                headers = {
                    'Accept-Encoding': 'identity',  # Evitar compresión para archivos binarios
                    'Cache-Control': 'no-cache'
                }
                
                async with session.get(url, headers=headers, allow_redirects=True) as response:
                    if response.status != 200:
                        if response.status == 403:
                            # Intentar sin headers personalizados
                            async with session.get(url, allow_redirects=True) as retry_response:
                                if retry_response.status != 200:
                                    return False, 0, f"Error HTTP: {retry_response.status}"
                                response = retry_response
                        else:
                            return False, 0, f"Error HTTP: {response.status}"
                    
                    # Obtener nombre del archivo
                    filename = await self.get_filename_from_response(url, response)
                    
                    # Crear nombre de archivo temporal
                    temp_filename = f"temp_{int(time.time())}_{os.urandom(4).hex()}"
                    dir_path = os.path.dirname(file_path)
                    temp_file_path = os.path.join(dir_path, temp_filename)
                    
                    # Determinar el nombre final del archivo
                    final_filename = filename
                    final_file_path = os.path.join(dir_path, final_filename)
                    
                    # Si el archivo ya existe, agregar número
                    counter = 1
                    base_name, ext = os.path.splitext(final_filename)
                    while os.path.exists(final_file_path):
                        final_filename = f"{base_name}_{counter}{ext}"
                        final_file_path = os.path.join(dir_path, final_filename)
                        counter += 1
                    
                    # Obtener tamaño si no se pudo antes
                    if file_size == 0:
                        content_length = response.headers.get('Content-Length')
                        if content_length:
                            file_size = int(content_length)
                            if file_size > MAX_FILE_SIZE:
                                return False, 0, f"Archivo demasiado grande (límite: {MAX_FILE_SIZE/(1024*1024)}MB)"
                    
                    # Configurar buffer optimizado
                    buffer_size = DOWNLOAD_BUFFER_SIZE  # 128KB
                    
                    # Usar escritura asíncrona con buffer grande
                    async with aiofiles.open(temp_file_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(buffer_size):
                            if not chunk:
                                continue
                            
                            # Verificar cancelación
                            if user_id and user_id not in self.active_downloads:
                                await f.close()
                                if os.path.exists(temp_file_path):
                                    os.remove(temp_file_path)
                                return False, 0, "Descarga cancelada por el usuario"
                            
                            await f.write(chunk)
                            downloaded += len(chunk)
                            
                            # Callback de progreso
                            current_time = time.time()
                            if current_time - last_callback_time >= 0.5 and progress_callback:
                                await progress_callback(downloaded, file_size or downloaded)
                                last_callback_time = current_time
                    
                    # Callback final
                    if progress_callback and downloaded > 0:
                        await progress_callback(downloaded, file_size or downloaded)
                    
                    # Renombrar archivo temporal al nombre final
                    # Verificar que el archivo temporal existe
                    if not os.path.exists(temp_file_path):
                        return False, 0, "Error: Archivo temporal no encontrado"
                    
                    # Intentar renombrar
                    try:
                        os.rename(temp_file_path, final_file_path)
                    except Exception as rename_error:
                        logger.error(f"Error renombrando archivo: {rename_error}")
                        # Si falla el rename, intentar copiar y luego eliminar
                        import shutil
                        shutil.copy2(temp_file_path, final_file_path)
                        os.remove(temp_file_path)
                
                elapsed = time.time() - start_time
                speed = downloaded / elapsed if elapsed > 0 else 0
                
                logger.info(f"✅ URL descargada: {filename} en {elapsed:.1f}s ({speed/1024/1024:.1f} MB/s)")
                
                return True, downloaded, final_filename
                
            except asyncio.CancelledError:
                logger.warning(f"Descarga cancelada: {url}")
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                return False, 0, "Descarga cancelada"
                
            except asyncio.TimeoutError:
                logger.error(f"Timeout descargando {url}")
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                return False, 0, "Timeout: La descarga tomó demasiado tiempo"
                
            except Exception as e:
                logger.error(f"Error descargando desde URL: {e}", exc_info=True)
                if temp_file_path and os.path.exists(temp_file_path):
                    try:
                        os.remove(temp_file_path)
                    except:
                        pass
                return False, 0, str(e)
                
            finally:
                if user_id and user_id in self.active_downloads:
                    del self.active_downloads[user_id]
    
    async def download_with_retry(
        self,
        url: str,
        file_path: str,
        progress_callback=None,
        user_id=None,
        max_retries: int = MAX_RETRIES
    ) -> Tuple[bool, int, str]:
        """Descarga con reintentos automáticos"""
        for attempt in range(max_retries + 1):
            try:
                success, downloaded, filename = await self.download_from_url(
                    url=url,
                    file_path=file_path,
                    progress_callback=progress_callback,
                    user_id=user_id
                )
                
                if success:
                    return True, downloaded, filename
                
                if attempt < max_retries:
                    wait_time = 2 ** attempt  # Exponential backoff
                    logger.info(f"Reintentando descarga en {wait_time}s (intento {attempt + 1}/{max_retries})")
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                if attempt < max_retries:
                    await asyncio.sleep(2 ** attempt)
        
        return False, 0, "Máximo de reintentos alcanzado"
    
    async def get_file_info(self, url: str) -> Tuple[Optional[str], Optional[int]]:
        """Obtiene información del archivo sin descargarlo"""
        try:
            session = await self.get_session()
            async with session.head(url, allow_redirects=True, timeout=15) as response:
                if response.status in (200, 301, 302, 303, 307, 308):
                    # Obtener nombre
                    filename = await self.get_filename_from_response(url, response)
                    
                    # Obtener tamaño
                    size = None
                    content_length = response.headers.get('Content-Length')
                    if content_length:
                        size = int(content_length)
                    
                    return filename, size
            return None, None
        except Exception as e:
            logger.warning(f"Error obteniendo info del archivo: {e}")
            return None, None
    
    async def close(self):
        """Cierra la sesión aiohttp"""
        if self.session and not self.session.closed:
            await self.session.close()
            self.session = None

# Instancia global del servicio
url_download_service = URLDownloadService()