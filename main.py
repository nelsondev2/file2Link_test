import os
import logging
import threading
import time
import sys
import gc
from waitress import serve

from config import BASE_DIR, PORT, CLEANUP_INTERVAL, MAX_CACHED_USERS, MAX_FILES_PER_USER
from telegram_bot import TelegramBot
from flask_app import app
from file_service import file_service

# ===== LOGGING =====
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ===== LIMPIEZA PERIÓDICA =====
def periodic_cleanup():
    """Limpieza periódica para liberar RAM"""
    logger.info("🧹 Iniciando sistema de limpieza periódica...")
    
    while True:
        try:
            time.sleep(CLEANUP_INTERVAL)  # Intervalo configurable
            
            logger.info("🧹 Ejecutando limpieza periódica...")
            
            # 1. Limpiar hashes expirados
            expired_hashes = file_service.cleanup_expired_hashes()
            
            # 2. Limpiar datos antiguos
            file_service.cleanup_old_data(force=True)
            
            # 3. Forzar garbage collection
            collected = gc.collect()
            
            # 4. Log de memoria (estimado)
            import psutil
            try:
                memory = psutil.virtual_memory()
                logger.info(f"🧹 Cleanup completado: {expired_hashes} hashes, {collected} objetos GC, RAM: {memory.percent}%")
            except:
                logger.info(f"🧹 Cleanup completado: {expired_hashes} hashes, {collected} objetos GC")
            
        except Exception as e:
            logger.error(f"Error en cleanup periódico: {e}")
            time.sleep(60)

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info("🤖 Iniciando bot de Telegram optimizado...")
    bot = TelegramBot()
    bot.run_bot()

def start_web_server():
    """Inicia el servidor web Flask"""
    logger.info(f"🌐 Iniciando servidor web en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

if __name__ == '__main__':
    os.makedirs(BASE_DIR, exist_ok=True)
    
    logger.info(f"📁 Directorios creados/verificados: {BASE_DIR}")
    logger.info(f"⚡ Sistema optimizado para 512MB RAM")
    logger.info(f"📊 Límites: {MAX_CACHED_USERS} usuarios, {MAX_FILES_PER_USER} archivos/usuario")
    
    # Iniciar limpieza periódica
    cleanup_thread = threading.Thread(target=periodic_cleanup, daemon=True)
    cleanup_thread.start()
    logger.info(f"🧹 Limpieza periódica configurada cada {CLEANUP_INTERVAL//60} minutos")

    # Iniciar bot de Telegram
    bot_thread = threading.Thread(target=start_telegram_bot, daemon=True)
    bot_thread.start()
    logger.info("🤖 Hilo del bot iniciado")

    time.sleep(10)  # Esperar a que el bot se inicialice

    logger.info("🌐 Iniciando servidor web principal...")
    logger.info("✅ Sistema completamente operativo y optimizado")

    start_web_server()