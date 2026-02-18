"""
Servicio de descarga de archivos desde Telegram.

Descarga con streaming y reintentos automáticos en caso de fallo.
"""
import asyncio
import logging
import os
import time
from typing import Awaitable, Callable, Optional

import aiofiles
from pyrogram.errors import FloodWait

from config import DOWNLOAD_BUFFER_SIZE, DOWNLOAD_TIMEOUT, MAX_RETRIES

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[int, int], Awaitable[None]]


class Downloader:
    async def download(
        self,
        client,
        message,
        dest_path: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> bool:
        """
        Descarga un archivo de Telegram al disco.

        Devuelve True si la descarga fue exitosa, False en caso contrario.
        """
        file_obj = (
            message.document
            or message.video
            or message.audio
            or (message.photo and message.photo[-1])
        )
        if file_obj is None:
            return False

        file_size: int = getattr(file_obj, "file_size", 0) or 0
        timeout = DOWNLOAD_TIMEOUT
        if file_size > 500 * 1024 * 1024:
            timeout = 7200

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        start = time.monotonic()
        downloaded = 0
        last_cb = start

        try:
            async with aiofiles.open(dest_path, "wb") as fp:
                async for chunk in client.stream_media(file_obj, limit=DOWNLOAD_BUFFER_SIZE):
                    if not chunk:
                        continue
                    await fp.write(chunk)
                    downloaded += len(chunk)

                    now = time.monotonic()
                    if on_progress and now - last_cb >= 0.5:
                        speed = downloaded / max(now - start, 0.001)
                        await on_progress(downloaded, file_size)
                        last_cb = now

            if on_progress:
                await on_progress(downloaded, file_size)

            elapsed = time.monotonic() - start
            avg_speed = downloaded / max(elapsed, 0.001) / (1024 * 1024)
            logger.info(
                "Descarga completada: %s (%.1f MB/s)",
                os.path.basename(dest_path),
                avg_speed,
            )
            return True

        except FloodWait as exc:
            logger.warning("FloodWait: esperando %ds", exc.value)
            await asyncio.sleep(exc.value + 1)
            return await self.download(client, message, dest_path, on_progress)

        except Exception as exc:
            logger.error("Error descargando archivo: %s", exc, exc_info=True)
            # Eliminar archivo parcial
            if os.path.exists(dest_path):
                try:
                    os.remove(dest_path)
                except OSError:
                    pass
            return False

    async def download_with_retry(
        self,
        client,
        message,
        dest_path: str,
        on_progress: Optional[ProgressCallback] = None,
    ) -> bool:
        """Descarga con reintentos exponenciales."""
        for attempt in range(MAX_RETRIES + 1):
            if attempt > 0:
                wait = 2 ** attempt
                logger.info("Reintentando descarga en %ds (intento %d/%d)", wait, attempt, MAX_RETRIES)
                await asyncio.sleep(wait)

            if await self.download(client, message, dest_path, on_progress):
                return True

        return False


downloader = Downloader()
