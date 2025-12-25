#!/usr/bin/env python3
"""
Punto de entrada principal del sistema Nelson File2Link
Versión profesional con gestión de errores y logging avanzado
"""

import os
import logging
import threading
import time
import sys
import signal
from pathlib import Path

from waitress import serve
from colorama import init, Fore, Style

from config import BASE_DIR, PORT
from telegram_bot import TelegramBot
from flask_app import app

# Inicializar colorama para logs con colores
init(autoreset=True)

# ===== LOGGING PROFESIONAL =====
class ColoredFormatter(logging.Formatter):
    """Formateador de logs con colores"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    def format(self, record):
        color = self.COLORS.get(record.levelname, Fore.WHITE)
        record.levelname = f"{color}{record.levelname}{Style.RESET_ALL}"
        record.name = f"{Fore.MAGENTA}{record.name}{Style.RESET_ALL}"
        return super().format(record)

def setup_logging():
    """Configura logging profesional"""
    # Crear directorio de logs
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Configurar formato
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'
    
    # Formateador para consola con colores
    console_formatter = ColoredFormatter(log_format, date_format)
    
    # Formateador para archivo
    file_formatter = logging.Formatter(log_format, date_format)
    
    # Handler para consola
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    console_handler.setLevel(logging.INFO)
    
    # Handler para archivo
    file_handler = logging.FileHandler(
        log_dir / f"nelson_{time.strftime('%Y%m%d')}.log",
        encoding='utf-8'
    )
    file_handler.setFormatter(file_formatter)
    file_handler.setLevel(logging.DEBUG)
    
    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Reducir verbosidad de librerías externas
    logging.getLogger('waitress').setLevel(logging.WARNING)
    logging.getLogger('pyrogram').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    
    return root_logger

# ===== MANEJO DE SEÑALES =====
class SignalHandler:
    """Maneja señales del sistema para apagado controlado"""
    
    def __init__(self):
        self.shutdown_requested = False
        signal.signal(signal.SIGINT, self.handle_signal)
        signal.signal(signal.SIGTERM, self.handle_signal)
    
    def handle_signal(self, signum, frame):
        """Manejador de señales"""
        if not self.shutdown_requested:
            logger.info(f"Recibida señal {signum}, iniciando apagado controlado...")
            self.shutdown_requested = True

# ===== INICIALIZACIÓN =====
def start_telegram_bot():
    """Inicia el bot de Telegram en un hilo separado"""
    logger.info(Fore.CYAN + "🤖 Iniciando bot de Telegram..." + Style.RESET_ALL)
    
    try:
        bot = TelegramBot()
        bot.run_bot()
    except Exception as e:
        logger.critical(f"❌ Error crítico en bot de Telegram: {e}", exc_info=True)
        sys.exit(1)

def start_web_server():
    """Inicia el servidor web Flask optimizado para producción"""
    logger.info(Fore.CYAN + f"🌐 Iniciando servidor web en puerto {PORT}..." + Style.RESET_ALL)
    
    try:
        # Configuración optimizada para Waitress
        serve(
            app,
            host='0.0.0.0',
            port=PORT,
            threads=4,  # Optimizado para Render
            connection_limit=100,
            channel_timeout=60,
            cleanup_interval=30,
            asyncore_use_poll=True
        )
    except Exception as e:
        logger.critical(f"❌ Error crítico en servidor web: {e}", exc_info=True)
        sys.exit(1)

def check_environment():
    """Verifica el entorno y configuración"""
    logger.info(Fore.YELLOW + "🔍 Verificando entorno..." + Style.RESET_ALL)
    
    # Verificar variables críticas
    required_vars = ['API_ID', 'API_HASH', 'BOT_TOKEN']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.critical(f"❌ Variables de entorno faltantes: {', '.join(missing_vars)}")
        logger.critical("Configúralas en Render.com → Environment Variables")
        sys.exit(1)
    
    # Verificar directorios
    os.makedirs(BASE_DIR, exist_ok=True)
    
    # Verificar permisos de escritura
    try:
        test_file = os.path.join(BASE_DIR, '.write_test')
        with open(test_file, 'w') as f:
            f.write('test')
        os.remove(test_file)
        logger.info(Fore.GREEN + "✅ Permisos de escritura OK" + Style.RESET_ALL)
    except PermissionError:
        logger.critical(f"❌ Sin permisos de escritura en {BASE_DIR}")
        sys.exit(1)
    
    logger.info(Fore.GREEN + "✅ Entorno verificado correctamente" + Style.RESET_ALL)

def print_banner():
    """Muestra banner de inicio"""
    banner = f"""
{Fore.CYAN}{'='*60}
╔══════════════════════════════════════════════════════╗
║{Fore.YELLOW}      🤖 NELSON FILE2LINK - VERSIÓN PROFESIONAL      {Fore.CYAN}║
║{Fore.WHITE}          Sistema de Gestión de Archivos            {Fore.CYAN}║
╚══════════════════════════════════════════════════════╝
{Fore.CYAN}{'='*60}
{Fore.WHITE}📁 Directorio base: {Fore.GREEN}{BASE_DIR}
{Fore.WHITE}🌐 Puerto web: {Fore.GREEN}{PORT}
{Fore.WHITE}⚡ Optimizado para: {Fore.GREEN}Render.com
{Fore.WHITE}📏 Tamaño máximo: {Fore.GREEN}2000 MB
{Fore.CYAN}{'='*60}{Style.RESET_ALL}
    """
    print(banner)

if __name__ == '__main__':
    # Configurar logging
    logger = setup_logging()
    
    # Mostrar banner
    print_banner()
    
    # Verificar entorno
    check_environment()
    
    # Inicializar manejador de señales
    signal_handler = SignalHandler()
    
    # Iniciar bot de Telegram en hilo separado
    logger.info("🚀 Iniciando servicios...")
    
    bot_thread = threading.Thread(
        target=start_telegram_bot,
        daemon=True,
        name="TelegramBotThread"
    )
    bot_thread.start()
    
    logger.info("✅ Hilo del bot iniciado")
    
    # Esperar a que el bot se inicialice
    logger.info("⏳ Esperando inicialización del bot (10 segundos)...")
    time.sleep(10)
    
    # Iniciar servidor web en el hilo principal
    logger.info("🌐 Iniciando servidor web principal...")
    
    try:
        start_web_server()
    except KeyboardInterrupt:
        logger.info("\n👋 Apagado solicitado por usuario")
    except Exception as e:
        logger.critical(f"❌ Error fatal: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("✅ Sistema apagado correctamente")