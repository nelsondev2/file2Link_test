import os
import logging
import threading
import time
import sys
from waitress import serve

from config import BASE_DIR, PORT, SYSTEM_LOG_FILE
from telegram_bot import TelegramBot
from flask_app import app
from cleanupservice import cleanupservice
from logservice import systemlogger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = system_logger

def starttelegrambot():
    logger.info("Iniciando bot de Telegram...")
    bot = TelegramBot()
    bot.run_bot()

def startwebserver():
    logger.info(f"Iniciando servidor web en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if name == 'main':
    os.makedirs(BASEDIR, existok=True)
    
    logger.info(f"Directorios creados/verificados: {BASE_DIR}")

    cleanup_service.start()

    botthread = threading.Thread(target=starttelegram_bot, daemon=True)
    bot_thread.start()

    logger.info("Hilo del bot iniciado")

    time.sleep(10)

    logger.info("Iniciando servidor web principal...")

    startwebserver()