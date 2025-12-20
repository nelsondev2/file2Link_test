import asyncio
import logging
from pyrogram import Client

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import setup_handlers

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.client = None
        self.is_running = False

    async def start_bot(self):
        """Inicia el bot de Telegram de forma asíncrona pura"""
        try:
            self.client = Client(
                "file_to_link_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                workers=100,
                sleep_threshold=60,
            )

            setup_handlers(self.client)
            
            logger.info("Iniciando cliente de Telegram...")
            await self.client.start()

            bot_info = await self.client.get_me()
            logger.info(f"✅ Bot iniciado: @{bot_info.username}")
            logger.info("📩 Listo para recibir comandos y archivos")

            self.is_running = True
            
            # Mantener el bot corriendo
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"❌ Error crítico: {e}")
            self.is_running = False

    def run(self):
        """Punto de entrada para compatibilidad"""
        asyncio.run(self.start_bot())