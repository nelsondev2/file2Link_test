"""
Archivo principal - Sistema optimizado para Render Free Tier
"""
import os
import logging
import threading
import time
import sys
import asyncio
from waitress import serve

from config import PORT
from telegram_bot import TelegramBot
from flask_app import app

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info("🚀 Iniciando bot de Telegram optimizado...")
    bot = TelegramBot()
    bot.run_bot()

def start_web_server():
    """Inicia el servidor web Flask (proxy ligero)"""
    logger.info(f"🌐 Iniciando servidor web en puerto {PORT}")
    logger.info(f"📡 Dominio: https://tu-dominio.onrender.com")
    logger.info("⚡ Sistema optimizado: 0% CPU, 0MB almacenamiento")
    serve(app, host='0.0.0.0', port=PORT)

def run_async_init():
    """Inicialización asíncrona (si es necesaria)"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # Aquí podríamos inicializar servicios async si fuera necesario
        loop.close()
    except Exception as e:
        logger.error(f"Error en inicialización async: {e}")

if __name__ == '__main__':
    # Mostrar banner de inicio
    print("\n" + "="*60)
    print("🚀 FILE2LINK - SISTEMA OPTIMIZADO PARA RENDER FREE")
    print("="*60)
    print("📊 CPU: 0.1 | Almacenamiento: 0MB | Todo en Telegram ☁️")
    print("🔗 URLs permanentes | Sobrevive a reinicios | Máxima velocidad")
    print("="*60 + "\n")
    
    logger.info("Iniciando sistema File2Link optimizado...")
    
    # Inicialización básica (si necesaria)
    init_thread = threading.Thread(target=run_async_init, daemon=True)
    init_thread.start()
    
    # Iniciar bot de Telegram
    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()
    
    logger.info("✅ Hilo del bot iniciado")
    
    # Pequeña pausa para que el bot se inicialice
    time.sleep(3)
    
    # Iniciar servidor web
    logger.info("🌍 Iniciando servidor web principal...")
    
    start_web_server()