"""
Punto de entrada de File2Link.

Arranca el bot de Telegram (hilo secundario) y el servidor web
Flask con Waitress (hilo principal).
"""
import logging
import os
import sys
import threading
import time

from waitress import serve

from config import PORT, STORAGE_DIR, API_ID, API_HASH, BOT_TOKEN

# ── Logging ────────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Silenciar loggers muy verbosos de librerías externas
logging.getLogger("pyrogram").setLevel(logging.WARNING)
logging.getLogger("waitress").setLevel(logging.WARNING)


# ── Validación de configuración ────────────────────────────────────────────────

def _check_config() -> None:
    missing = []
    if not API_ID:          missing.append("API_ID")
    if not API_HASH:        missing.append("API_HASH")
    if not BOT_TOKEN:       missing.append("BOT_TOKEN")
    if missing:
        logger.critical(
            "Faltan variables de entorno requeridas: %s\n"
            "Configúralas antes de arrancar la aplicación.",
            ", ".join(missing),
        )
        sys.exit(1)


# ── Inicio ─────────────────────────────────────────────────────────────────────

def main() -> None:
    _check_config()

    os.makedirs(STORAGE_DIR, exist_ok=True)
    logger.info("Directorio de almacenamiento: %s", STORAGE_DIR)

    # Bot en hilo separado
    from bot import Bot
    bot = Bot()
    bot_thread = threading.Thread(target=bot.run, daemon=True, name="telegram-bot")
    bot_thread.start()
    logger.info("Bot de Telegram iniciado")

    # Pequeña pausa para que el bot se conecte antes de servir tráfico web
    time.sleep(5)

    # Servidor web en hilo principal
    from web_app import app
    logger.info("Servidor web escuchando en puerto %d", PORT)
    serve(app, host="0.0.0.0", port=PORT, threads=4)


if __name__ == "__main__":
    main()
