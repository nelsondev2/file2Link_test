import os
import logging
import yt_dlp
import asyncio
import concurrent.futures
import time
import random
from config import BASE_DIR, YT_DLP_TIMEOUT, YT_DLP_MAX_FILE_SIZE_MB
from file_service import file_service
from load_manager import load_manager
from cookies_service import cookies_service

logger = logging.getLogger(__name__)

class YouTubeService:
    def __init__(self):
        # Configuración base (se actualizará dinámicamente con cookies)
        self.base_ydl_opts = {
            'format': 'best[height<=360]',
            'outtmpl': os.path.join(BASE_DIR, 'temp', '%(id)s_%(title).100s.%(ext)s'),
            'quiet': False,
            'no_warnings': False,
            'noplaylist': True,
            'max_filesize': YT_DLP_MAX_FILE_SIZE_MB * 1024 * 1024,
            
            # Estrategias anti-bot
            'retries': 20,
            'fragment_retries': 20,
            'skip_unavailable_fragments': True,
            'continuedl': True,
            'concurrent_fragment_downloads': 1,
            'throttled_rate': None,
            
            # Headers realistas
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            },
            
            # Extractores específicos
            'extractor_args': {
                'youtube': {
                    'skip': ['hls', 'dash'],
                }
            },
            
            # Procesadores post-descarga
            'postprocessors': [{
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
        }
        
        # Crear directorio temporal
        temp_dir = os.path.join(BASE_DIR, 'temp')
        os.makedirs(temp_dir, exist_ok=True)

    def _get_ydl_opts_with_cookies(self, final_path, attempt):
        """Obtiene opciones de yt-dlp incluyendo cookies GLOBALES si están disponibles"""
        opts = self.base_ydl_opts.copy()
        opts['outtmpl'] = final_path
        
        # Rotar User-Agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        opts['http_headers']['User-Agent'] = user_agents[attempt % len(user_agents)]
        
        # Estrategias diferentes por intento
        if attempt == 2:
            opts['format'] = 'worst[height>=240]'
            opts['extractor_args']['youtube']['skip'] = []
        
        # AGREGAR COOKIES GLOBALES SI ESTÁN DISPONIBLES
        cookies_path = cookies_service.get_global_cookies_path()
        if cookies_path:
            opts['cookiefile'] = cookies_path
            logger.info(f"🎯 Usando cookies GLOBALES: {cookies_path}")
        
        return opts

    async def download_youtube_video(self, url, user_id):
        """Descarga un video de YouTube con soporte para cookies GLOBALES"""
        MAX_RETRIES = 2
        RETRY_DELAY = 10
        
        # Verificar si hay cookies GLOBALES configuradas
        has_cookies = cookies_service.has_global_cookies()
        cookies_status = "🔐 **Con cookies**" if has_cookies else "🔓 **Sin cookies**"
        
        logger.info(f"🎬 Iniciando descarga YouTube para {user_id} - {cookies_status}")
        
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                logger.info(f"🎬 Intento {attempt}/{MAX_RETRIES} para: {url}")
                
                can_start, message = load_manager.can_start_process()
                if not can_start:
                    return False, message

                # Validación mejorada de URL
                if not await self._validate_youtube_url(url):
                    return False, "❌ URL de YouTube no válida"

                # Obtener información con estrategias anti-bot
                video_info = await self._get_video_info_robust(url)
                if not video_info:
                    if attempt < MAX_RETRIES:
                        logger.warning(f"⚠️ No se pudo obtener info, reintentando...")
                        await asyncio.sleep(RETRY_DELAY)
                        continue
                    return False, "❌ No se pudo obtener información del video"

                # Preparar descarga
                user_dir = file_service.get_user_directory(user_id, "downloads")
                original_filename = f"{self._sanitize_filename(video_info['title'])}.mp4"
                final_filename = await self._get_unique_filename(user_dir, original_filename)
                final_path = os.path.join(user_dir, final_filename)

                # Configurar opciones CON cookies GLOBALES
                download_opts = self._get_ydl_opts_with_cookies(final_path, attempt)
                
                # Descargar con manejo mejorado
                success, result = await self._download_with_retry(url, download_opts, video_info['title'], attempt)
                
                if success:
                    # Verificar archivo descargado
                    if not os.path.exists(final_path) or os.path.getsize(final_path) == 0:
                        raise Exception("Archivo descargado está vacío")

                    # Registrar en sistema
                    file_number = file_service.register_file(user_id, original_filename, final_filename, "downloads")
                    download_url = file_service.create_download_url(user_id, final_filename)
                    
                    file_size = os.path.getsize(final_path)
                    size_mb = file_size / (1024 * 1024)
                    
                    logger.info(f"✅ Descarga exitosa: {original_filename} ({size_mb:.2f} MB) - {cookies_status}")
                    
                    return True, {
                        'file_number': file_number,
                        'filename': original_filename,
                        'stored_filename': final_filename,
                        'url': download_url,
                        'size_mb': size_mb,
                        'duration': video_info.get('duration', 0),
                        'title': video_info['title'],
                        'cookies_used': has_cookies
                    }
                else:
                    if attempt < MAX_RETRIES:
                        wait_time = RETRY_DELAY * attempt
                        logger.warning(f"🔄 Reintentando en {wait_time} segundos...")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        return False, f"❌ Error en descarga: {result}"

            except Exception as e:
                logger.error(f"❌ Error en intento {attempt}: {str(e)}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(RETRY_DELAY * attempt)
                    continue
                else:
                    return False, f"❌ Error después de {MAX_RETRIES} intentos: {str(e)}"
            finally:
                load_manager.finish_process()

    async def _get_download_options(self, final_path, attempt):
        """Obtiene opciones de descarga con rotación de estrategias"""
        # Rotar User-Agents
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        ]
        
        opts = self.base_ydl_opts.copy()
        opts['outtmpl'] = final_path
        opts['http_headers']['User-Agent'] = user_agents[attempt % len(user_agents)]
        
        # Estrategias diferentes por intento
        if attempt == 2:
            # Segundo intento: formato más compatible
            opts['format'] = 'worst[height>=240]'
            opts['extractor_args']['youtube']['skip'] = []  # Intentar todos los formatos
        
        return opts

    async def _validate_youtube_url(self, url):
        """Valida URLs de YouTube de forma más flexible"""
        youtube_patterns = [
            'youtube.com/watch',
            'youtu.be/',
            'youtube.com/shorts/',
            'youtube.com/embed/'
        ]
        return any(pattern in url for pattern in youtube_patterns)

    async def _get_video_info_robust(self, url):
        """Obtiene información del video con múltiples estrategias"""
        strategies = [
            self._get_video_info_basic,
            self._get_video_info_with_headers,
            self._get_video_info_simple_format
        ]
        
        for strategy in strategies:
            try:
                info = await strategy(url)
                if info:
                    return info
                await asyncio.sleep(2)  # Pausa entre estrategias
            except Exception as e:
                logger.warning(f"Estrategia fallida: {e}")
                continue
        
        return None

    async def _get_video_info_basic(self, url):
        """Estrategia básica para obtener info"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
        }
        return await self._extract_info_with_opts(url, opts)

    async def _get_video_info_with_headers(self, url):
        """Estrategia con headers personalizados"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,
            'skip_download': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            },
        }
        return await self._extract_info_with_opts(url, opts)

    async def _get_video_info_simple_format(self, url):
        """Estrategia con formato simple"""
        opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,  # Solo metadata básica
            'skip_download': True,
        }
        return await self._extract_info_with_opts(url, opts)

    async def _extract_info_with_opts(self, url, opts):
        """Extrae información con opciones específicas"""
        try:
            loop = asyncio.get_event_loop()
            
            def extract():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url, download=False)
            
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, extract)
                info = await asyncio.wait_for(future, timeout=30)
                
                if not info:
                    return None
                    
                return {
                    'title': info.get('title', 'video_sin_titulo').strip(),
                    'duration': info.get('duration', 0),
                    'uploader': info.get('uploader', 'Desconocido'),
                    'view_count': info.get('view_count', 0),
                    'id': info.get('id', '')
                }
                
        except asyncio.TimeoutError:
            logger.warning("⏰ Timeout obteniendo información del video")
            return None
        except Exception as e:
            logger.warning(f"⚠️ Error en extract_info: {e}")
            return None

    async def _download_with_retry(self, url, opts, video_title, attempt):
        """Descarga con manejo robusto de errores"""
        try:
            loop = asyncio.get_event_loop()
            
            def download_task():
                try:
                    # Agregar hook de progreso simple
                    def progress_hook(d):
                        if d['status'] == 'downloading':
                            percent = d.get('_percent_str', '0%')
                            speed = d.get('_speed_str', 'N/A')
                            logger.info(f"📥 {video_title}: {percent} a {speed}")
                        elif d['status'] == 'finished':
                            logger.info(f"✅ Descarga completada: {video_title}")
                    
                    opts['progress_hooks'] = [progress_hook]
                    
                    with yt_dlp.YoutubeDL(opts) as ydl:
                        ydl.download([url])
                    return True, "Descarga completada"
                    
                except yt_dlp.DownloadError as e:
                    error_msg = str(e)
                    if "Sign in to confirm you're not a bot" in error_msg:
                        return False, "YouTube ha bloqueado la descarga. Intenta con otro video."
                    elif "Private video" in error_msg:
                        return False, "El video es privado o no está disponible."
                    elif "Video unavailable" in error_msg:
                        return False, "El video no está disponible."
                    else:
                        return False, f"Error de YouTube: {error_msg}"
                except Exception as e:
                    return False, f"Error en descarga: {str(e)}"

            # Ejecutar con timeout
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = loop.run_in_executor(executor, download_task)
                result = await asyncio.wait_for(future, timeout=YT_DLP_TIMEOUT)
                return result
                
        except asyncio.TimeoutError:
            logger.error("⏰ Timeout en descarga de YouTube")
            return False, "La descarga tardó demasiado tiempo"
        except Exception as e:
            logger.error(f"❌ Error en _download_with_retry: {e}")
            return False, f"Error en el proceso de descarga: {str(e)}"

    def _sanitize_filename(self, filename):
        """Limpia el nombre de archivo"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        # Limitar longitud y remover espacios extra
        filename = filename.strip()
        if len(filename) > 100:
            filename = filename[:100]
        return filename

    async def _get_unique_filename(self, directory, filename):
        """Genera nombre único"""
        base, ext = os.path.splitext(filename)
        counter = 1
        new_filename = filename
        
        while os.path.exists(os.path.join(directory, new_filename)):
            new_filename = f"{base}_{counter}{ext}"
            counter += 1
            
        return new_filename

    def cleanup_temp_files(self, max_age_hours=1):
        """Limpia archivos temporales más frecuentemente"""
        try:
            temp_dir = os.path.join(BASE_DIR, 'temp')
            if not os.path.exists(temp_dir):
                return
                
            current_time = time.time()
            for filename in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, filename)
                if os.path.isfile(file_path):
                    file_age = current_time - os.path.getctime(file_path)
                    if file_age > max_age_hours * 3600:
                        os.remove(file_path)
                        logger.info(f"🧹 Limpiado temporal: {filename}")
        except Exception as e:
            logger.error(f"Error limpiando temporales: {e}")

youtube_service = YouTubeService()
