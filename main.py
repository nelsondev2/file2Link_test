import os
import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from waitress import serve

from config import BASE_DIR, PORT
from telegram_bot import TelegramBot
from flask_app import app

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def start_telegram_bot():
    """Inicia el bot de Telegram en el event loop principal"""
    logger.info("Iniciando bot de Telegram...")
    bot = TelegramBot()
    await bot.start_bot()

def start_web_server():
    """Inicia el servidor web en thread separado"""
    logger.info(f"Iniciando servidor web en puerto {PORT}")
    serve(app, host='0.0.0.0', port=PORT)

async def main():
    """Función principal asíncrona"""
    # Crear directorio base
    os.makedirs(BASE_DIR, exist_ok=True)
    logger.info(f"Directorio creado: {BASE_DIR}")
    
    # Crear executor para operaciones bloqueantes
    executor = ThreadPoolExecutor(max_workers=4)
    loop = asyncio.get_event_loop()
    loop.set_default_executor(executor)
    
    try:
        # Iniciar bot de Telegram
        bot_task = asyncio.create_task(start_telegram_bot())
        
        # Esperar a que el bot esté listo
        await asyncio.sleep(5)
        
        # Iniciar servidor web en thread separado
        import threading
        web_thread = threading.Thread(target=start_web_server, daemon=True)
        web_thread.start()
        
        logger.info("✅ Todos los servicios iniciados")
        logger.info(f"📡 Web server: http://0.0.0.0:{PORT}")
        logger.info("🤖 Telegram bot: Listo para recibir comandos")
        
        # Mantener el bot corriendo
        await bot_task
        
    except KeyboardInterrupt:
        logger.info("👋 Apagando servicios...")
    except Exception as e:
        logger.error(f"Error crítico: {e}")
    finally:
        executor.shutdown(wait=True)
        logger.info("✅ Servicios detenidos")

if __name__ == '__main__':
    asyncio.run(main())