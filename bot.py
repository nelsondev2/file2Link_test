"""
Configuración e inicio del cliente de Telegram.
"""
import asyncio
import logging

from pyrogram import Client
from pyrogram.errors import ApiIdInvalid, AuthKeyUnregistered

from config import API_HASH, API_ID, BOT_TOKEN
import handlers

logger = logging.getLogger(__name__)


class Bot:
    def __init__(self) -> None:
        self._client = Client(
            "file2link_session",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
        )

    def run(self) -> None:
        """Bloquea el hilo actual ejecutando el bot."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start())
        except (ApiIdInvalid, AuthKeyUnregistered) as exc:
            logger.critical("Credenciales de Telegram inválidas: %s", exc)
            raise
        except Exception as exc:
            logger.error("Error en el bot: %s", exc, exc_info=True)

    async def _start(self) -> None:
        handlers.register(self._client)

        await self._client.start()
        me = await self._client.get_me()
        logger.info("Bot iniciado: @%s", me.username)

        # Mantener el bot corriendo indefinidamente
        await asyncio.Event().wait()
