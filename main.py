"""
Punto de entrada de File2Link.

Arranca el bot de Telegram (hilo secundario) y el servidor web
Flask con Waitress (hilo principal).
"""
import logging
import os
import sys
import threading

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

def _start_keepalive() -> None:
    """
    Lanza un hilo que hace ping a /health cada 10 minutos.
    Evita que Render free tier duerma el servicio y corte la conexión
    de long-polling de Telegram.
    """
    import time
    import urllib.request

    from config import PUBLIC_DOMAIN

    def _ping() -> None:
        url = f"{PUBLIC_DOMAIN}/health"
        while True:
            time.sleep(600)  # 10 minutos
            try:
                urllib.request.urlopen(url, timeout=10)
                logger.debug("Keep-alive ping OK")
            except Exception as exc:
                logger.warning("Keep-alive ping falló: %s", exc)

    t = threading.Thread(target=_ping, daemon=True, name="keepalive")
    t.start()
    logger.info("Keep-alive activo (ping cada 10 min a %s/health)", PUBLIC_DOMAIN)


def main() -> None:
    _check_config()

    os.makedirs(STORAGE_DIR, exist_ok=True)
    logger.info("Directorio de almacenamiento: %s", STORAGE_DIR)

    # Bot en hilo secundario (daemon → muere si el proceso principal muere)
    from bot import Bot
    bot = Bot()
    bot_thread = threading.Thread(target=bot.run, daemon=True, name="telegram-bot")
    bot_thread.start()
    logger.info("Bot de Telegram iniciando en segundo plano…")

    # El servidor web arranca INMEDIATAMENTE para que Render no cancele el
    # despliegue por timeout en el health check.
    # Waitress empieza a escuchar en cuanto se llama a serve().
    from web_app import app

    # Keep-alive: ping al propio /health cada 10 min para que Render free tier
    # no duerma el servicio y el bot siga recibiendo mensajes de Telegram.
    _start_keepalive()

    logger.info("Servidor web escuchando en puerto %d", PORT)
    serve(app, host="0.0.0.0", port=PORT, threads=4)


if __name__ == "__main__":
    main()
