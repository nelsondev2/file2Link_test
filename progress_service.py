import asyncio
import logging
import sys
from pyrogram import Client, filters

from config import APIID, APIHASH, BOT_TOKEN
from telegramhandlers import setuphandlers
from notifyservice import notifyservice

logger = logging.getLogger(name)

class TelegramBot:
    def init(self):
        self.client = None
        self.is_running = False

    async def setup_handlers(self):
        setup_handlers(self.client)

    async def start_bot(self):
        try:
            self.client = Client(
                "filetolink_bot",
                apiid=APIID,
                apihash=APIHASH,
                bottoken=BOTTOKEN
            )

            notifyservice.setclient(self.client)
            await self.setup_handlers()
            
            logger.info("Iniciando cliente de Telegram...")
            await self.client.start()

            botinfo = await self.client.getme()
            logger.info(f"Bot iniciado: @{bot_info.username}")
            
            logger.info("El bot está listo y respondiendo a comandos")

            self.is_running = True
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"Error crítico en el bot: {e}")
            self.is_running = False

    def run_bot(self):
        try:
            loop = asyncio.neweventloop()
            asyncio.seteventloop(loop)
            loop.rununtilcomplete(self.start_bot())
        except Exception as e:
            logger.error(f"Error en el loop del bot: {e}")