import os
import logging
import threading
import time
import sys
from waitress import serve

from config import BASE_DIR, PORT
from telegram_bot import TelegramBot
from flask_app import app

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info("Iniciando bot de Telegram...")
    bot = TelegramBot()
    bot.run_bot()

def start_web_server():
    """Inicia el servidor web Flask"""
    logger.info(f"Iniciando servidor web en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    
    logger.info(f"Directorios creados/verificados: {BASE_DIR}")

    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()

    logger.info("Hilo del bot iniciado")

    time.sleep(10)

    logger.info("Iniciando servidor web principal...")

    start_web_server()
