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

    async def start(self):
        try:
            self.client = Client(
                "file2link_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                max_concurrent_transmissions=6,
                ipv6=False,
            )

            setup_handlers(self.client)

            logger.info("Iniciando cliente de Telegram...")
            await self.client.start()

            info = await self.client.get_me()
            logger.info(f"Bot activo: @{info.username}")
            self.is_running = True

            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"Error critico: {e}")
            self.is_running = False

    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start())
        except Exception as e:
            logger.error(f"Error en loop: {e}")
