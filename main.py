import os
import logging
import threading
import sys
from waitress import serve
from config import BASE_DIR, PORT
from telegram_bot import TelegramBot
from flask_app import app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def start_bot():
    logger.info("Iniciando bot de Telegram...")
    bot = TelegramBot()
    bot.run()


def start_web():
    logger.info(f"Servidor web en puerto {PORT}")
    serve(app, host="0.0.0.0", port=PORT)


if __name__ == "__main__":
    os.makedirs(BASE_DIR, exist_ok=True)

    bot_thread = threading.Thread(target=start_bot, daemon=True)
    bot_thread.start()
    logger.info("Bot iniciado en hilo secundario")

    # Esperar brevemente a que el bot se conecte
    import time
    time.sleep(3)

    logger.info("Iniciando servidor web...")
    start_web()
