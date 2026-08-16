import asyncio
import os
import time
import logging
import aiofiles
from pyrogram.errors import FloodWait
from config import DOWNLOAD_BUFFER_SIZE, DOWNLOAD_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)


class DownloadService:
    def __init__(self):
        self.active_downloads = {}

    def _get_file_obj(self, message):
        """Extrae el objeto de archivo y su tamaño del mensaje."""
        if message.document:
            return message.document, message.document.file_size or 0
        if message.video:
            return message.video, message.video.file_size or 0
        if message.audio:
            return message.audio, message.audio.file_size or 0
        if message.photo:
            return message.photo[-1], message.photo[-1].file_size or 0
        return None, 0

    async def download_file(self, client, message, file_path, progress_callback=None):
        """Descarga un archivo con buffer optimizado."""
        try:
            user_id = message.from_user.id
            self.active_downloads[user_id] = True

            file_obj, file_size = self._get_file_obj(message)
            if not file_obj:
                raise ValueError("No se pudo obtener el objeto de archivo")

            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            timeout = DOWNLOAD_TIMEOUT
            if file_size > 500 * 1024 * 1024:
                timeout = 7200

            logger.info(
                f"Descarga iniciada: {os.path.basename(file_path)} "
                f"({file_size / 1024 / 1024:.1f} MB)"
            )

            start_time = time.time()
            downloaded = 0
            last_cb = start_time

            async with aiofiles.open(file_path, "wb") as f:
                async for chunk in client.stream_media(file_obj, limit=DOWNLOAD_BUFFER_SIZE):
                    if not chunk:
                        continue

                    await f.write(chunk)
                    downloaded += len(chunk)

                    now = time.time()
                    if now - last_cb >= 0.5 and progress_callback:
                        await progress_callback(downloaded, file_size)
                        last_cb = now

                if progress_callback and downloaded > 0:
                    await progress_callback(downloaded, file_size)

            elapsed = time.time() - start_time
            speed = downloaded / elapsed if elapsed > 0 else 0
            logger.info(
                f"Descarga completada: {os.path.basename(file_path)} "
                f"en {elapsed:.1f}s ({speed / 1024 / 1024:.1f} MB/s)"
            )

            return True, downloaded

        except FloodWait as e:
            logger.warning(f"FloodWait: esperando {e.value}s")
            await asyncio.sleep(e.value + 1)
            return await self.download_file(client, message, file_path, progress_callback)

        except Exception as e:
            logger.error(f"Error en descarga: {e}", exc_info=True)
            return False, 0

        finally:
            self.active_downloads.pop(user_id, None)

    async def download_with_retry(self, client, message, file_path, progress_callback=None):
        """Descarga con reintentos automaticos."""
        for attempt in range(MAX_RETRIES + 1):
            try:
                success, downloaded = await self.download_file(
                    client, message, file_path, progress_callback
                )
                if success:
                    return True, downloaded

                if attempt < MAX_RETRIES:
                    wait = 2 ** attempt
                    logger.info(f"Reintentando en {wait}s (intento {attempt + 1}/{MAX_RETRIES})")
                    await asyncio.sleep(wait)

            except Exception as e:
                logger.error(f"Error en intento {attempt + 1}: {e}")
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2 ** attempt)

        return False, 0


download_service = DownloadService()
