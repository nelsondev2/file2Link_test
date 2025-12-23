import asyncio
import logging
import sys
from pyrogram import Client, filters

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import setup_handlers

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.client = None
        self.is_running = False

    async def setup_handlers(self):
        """Configura todos los handlers del bot (sin callbacks)"""
        setup_handlers(self.client)

    async def start_bot(self):
        """Inicia el bot de Telegram"""
        try:
            self.client = Client(
                "file_to_link_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN
            )

            await self.setup_handlers()
            
            logger.info("Iniciando cliente de Telegram...")
            await self.client.start()

            bot_info = await self.client.get_me()
            logger.info(f"Bot iniciado: @{bot_info.username}")
            
            logger.info("El bot está listo y respondiendo a comandos")

            self.is_running = True
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"Error crítico en el bot: {e}")
            self.is_running = False

    def run_bot(self):
        """Ejecuta el bot en un loop asyncio"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start_bot())
        except Exception as e:
            logger.error(f"Error en el loop del bot: {e}")
