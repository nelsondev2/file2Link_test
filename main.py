#!/usr/bin/env python3
# main.py — Entrada única, bot + web simplificada, descargas optimizadas con Pyrogram

import os
import sys
import time
import logging
import asyncio
import signal
from pathlib import Path
from threading import Thread, Semaphore

from flask import Flask, jsonify, render_template_string, send_from_directory
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from file_service import FileService
from packing_service import PackingService

# -------------------------
# Configuración básica
# -------------------------
BASE_DIR = os.getenv("BASE_DIR", "storage")
PORT = int(os.getenv("PORT", 8080))
API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
MAX_CONCURRENT = int(os.getenv("MAX_CONCURRENT_PROCESSES", "1"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "2000"))

# -------------------------
# Logging
# -------------------------
log_dir = Path("logs")
log_dir.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_dir / f"nelson_{time.strftime('%Y%m%d')}.log", encoding="utf-8")
    ]
)
logger = logging.getLogger("nelson")

# -------------------------
# Servicios
# -------------------------
file_service = FileService(base_dir=BASE_DIR)
packing_service = PackingService(file_service=file_service)

# Semaphore para limitar concurrencia
download_semaphore = Semaphore(MAX_CONCURRENT)

# -------------------------
# Flask web (simplificada)
# -------------------------
app = Flask(__name__)

@app.route("/")
def index():
    stats = {
        "base_dir": BASE_DIR,
        "total_users": len([d for d in os.listdir(BASE_DIR) if os.path.isdir(os.path.join(BASE_DIR, d))]) if os.path.exists(BASE_DIR) else 0,
        "total_size_gb": round(sum(
            os.path.getsize(os.path.join(root, f))
            for root, _, files in os.walk(BASE_DIR) for f in files
        ) / (1024**3), 2) if os.path.exists(BASE_DIR) else 0.0,
        "max_file_mb": MAX_FILE_MB
    }
    html = """
    <!doctype html>
    <html>
      <head><meta charset="utf-8"><title>Nelson File2Link - Status</title></head>
      <body style="font-family:Arial,Helvetica,sans-serif;padding:20px;">
        <h1>Nelson File2Link — Estado</h1>
        <ul>
          <li><strong>Directorio base:</strong> {{ base_dir }}</li>
          <li><strong>Usuarios:</strong> {{ total_users }}</li>
          <li><strong>Almacenamiento total (GB):</strong> {{ total_size_gb }}</li>
          <li><strong>Tamaño máximo por archivo (MB):</strong> {{ max_file_mb }}</li>
        </ul>
        <p><a href="/files">Explorar archivos</a></p>
      </body>
    </html>
    """
    return render_template_string(html, **stats)

@app.route("/files")
def files():
    # Lista simple de usuarios y archivos (no autenticada, para administración interna)
    users = []
    if os.path.exists(BASE_DIR):
        for user in sorted(os.listdir(BASE_DIR)):
            user_dir = os.path.join(BASE_DIR, user, "downloads")
            if os.path.isdir(user_dir):
                files = []
                for f in sorted(os.listdir(user_dir)):
                    path = os.path.join(user_dir, f)
                    if os.path.isfile(path):
                        files.append({"name": f, "size": os.path.getsize(path)})
                users.append({"user": user, "files": files})
    return jsonify(users)

@app.route("/storage/<user_id>/downloads/<path:filename>")
def serve_file(user_id, filename):
    user_dir = os.path.join(BASE_DIR, user_id, "downloads")
    return send_from_directory(user_dir, filename, as_attachment=True)

# -------------------------
# Pyrogram bot
# -------------------------
bot = Client(
    "nelson_file2link_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN,
    workdir="./session_data",
    workers=4
)

# Mensajes y botones compactos
MAIN_KEYBOARD = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("📁 Mis archivos", callback_data="show_files"),
         InlineKeyboardButton("📦 Empaquetar", callback_data="pack_all")],
        [InlineKeyboardButton("ℹ️ Estado", callback_data="status")]
    ]
)

def short_progress_bar(percent: float, length: int = 12) -> str:
    filled = int(round(percent * length / 100))
    return "█" * filled + "░" * (length - filled)

async def send_short_reply(message: Message, text: str, reply_markup=None):
    try:
        await message.reply_text(text, reply_markup=reply_markup, disable_web_page_preview=True)
    except Exception:
        logger.exception("Error sending reply")

# -------------------------
# Descarga optimizada con download_media
# -------------------------
async def download_with_progress(client: Client, message: Message, dest_path: str):
    """
    Usa pyrogram.download_media con callback para actualizar progreso.
    Mantiene un solo mensaje de progreso por descarga.
    """
    progress_msg = None
    last_update = 0

    def progress_cb(current, total):
        nonlocal progress_msg, last_update
        try:
            percent = (current / total * 100) if total else 0
            now = time.time()
            if now - last_update < 1 and percent < 99.5:
                return  # actualizar cada ~1s
            last_update = now
            bar = short_progress_bar(percent)
            text = f"⚡ Descargando `{os.path.basename(dest_path)}`\n{bar} {percent:.1f}%\n{current//1024} KB / {total//1024} KB"
            # editar mensaje de progreso (sin await en callback)
            asyncio.get_event_loop().create_task(
                (progress_msg.edit_text(text) if progress_msg else message.reply_text(text))
            )
        except Exception:
            logger.exception("Error en progress_cb")

    # Crear carpeta destino
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)

    # Reservar semáforo (bloqueante en hilo async)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, download_semaphore.acquire)

    try:
        # Enviar mensaje inicial
        progress_msg = await message.reply_text(f"⚡ Preparando descarga `{os.path.basename(dest_path)}`...")
        # Pyrogram download_media soporta progress callback
        await client.download_media(message, file_name=dest_path, progress=progress_cb)
        # Finalizar
        await progress_msg.edit_text(f"✅ Descarga completada: `{os.path.basename(dest_path)}`")
        return True
    except Exception as e:
        logger.exception("Error en download_with_progress")
        if progress_msg:
            try:
                await progress_msg.edit_text("❌ Error en la descarga. Intenta de nuevo más tarde.")
            except Exception:
                pass
        return False
    finally:
        download_semaphore.release()

# -------------------------
# Handlers
# -------------------------
@bot.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
async def handle_media(client: Client, message: Message):
    user = message.from_user
    user_id = str(user.id)
    # Validaciones
    file_size = getattr(message.document or message.video or message.audio or (message.photo and message.photo[-1]), "file_size", 0) or 0
    if file_size > MAX_FILE_MB * 1024 * 1024:
        await send_short_reply(message, f"❌ Archivo demasiado grande. Límite: {MAX_FILE_MB} MB")
        return

    # Preparar ruta
    user_dir = file_service.get_user_directory(user_id, "downloads")
    filename = file_service.sanitize_filename(getattr(message.document or message.video or message.audio or (message.photo and message.photo[-1]), "file_name", None) or f"file_{int(time.time())}")
    dest_path = os.path.join(user_dir, filename)

    # Iniciar descarga con semáforo y progreso
    await send_short_reply(message, "⏳ Encolando descarga...")

    success = await download_with_progress(client, message, dest_path)
    if not success:
        return

    # Registrar archivo
    file_num = file_service.register_file(user_id, filename, filename, "downloads")
    download_url = file_service.create_download_url(user_id, filename)
    reply = (
        f"✅ Archivo guardado como **#{file_num}**\n"
        f"🔗 Enlace: {download_url}"
    )
    await send_short_reply(message, reply, reply_markup=MAIN_KEYBOARD)

@bot.on_message(filters.command("start") & filters.private)
async def cmd_start(client: Client, message: Message):
    user = message.from_user
    text = (
        f"👋 Hola {user.first_name}!\n\n"
        "Envía un archivo y te daré un enlace de descarga rápido.\n"
        f"📏 Límite por archivo: {MAX_FILE_MB} MB\n\n"
        "Usa los botones para gestionar tus archivos."
    )
    await message.reply_text(text, reply_markup=MAIN_KEYBOARD)

@bot.on_message(filters.command("list") & filters.private)
async def cmd_list(client: Client, message: Message):
    user_id = str(message.from_user.id)
    files = file_service.list_user_files(user_id, "downloads")
    if not files:
        await send_short_reply(message, "📭 Carpeta vacía. Envía archivos para comenzar.")
        return
    lines = [f"📁 Archivos ({len(files)}):"]
    for f in files[:20]:
        lines.append(f"• #{f['number']:02d} {f['name']} — {file_service.format_bytes(f['size'])}")
    await send_short_reply(message, "\n".join(lines))

@bot.on_message(filters.command("pack") & filters.private)
async def cmd_pack(client: Client, message: Message):
    user_id = str(message.from_user.id)
    await send_short_reply(message, "📦 Preparando empaquetado (ZIP sin compresión). Esto puede tardar...")
    try:
        files, msg = packing_service.pack_folder(user_id, split_size_mb=None)
        if not files:
            await send_short_reply(message, f"❌ {msg}")
            return
        # Si hay un solo zip
        if len(files) == 1:
            f = files[0]
            await send_short_reply(message, f"✅ Empaquetado listo: `{f['filename']}`\n🔗 {f['url']}")
        else:
            await send_short_reply(message, f"✅ Empaquetado en {len(files)} partes. Usa /list para verlas.")
    except Exception as e:
        logger.exception("Error en cmd_pack")
        await send_short_reply(message, "❌ Error empaquetando. Intenta más tarde.")

# -------------------------
# Run: Flask en hilo + Bot en main loop
# -------------------------
def run_flask():
    logger.info(f"Starting Flask on port {PORT}")
    app.run(host="0.0.0.0", port=PORT, threaded=True)

def main():
    # Validaciones mínimas
    if not (API_ID and API_HASH and BOT_TOKEN):
        logger.critical("API_ID, API_HASH y BOT_TOKEN deben estar configurados en variables de entorno")
        sys.exit(1)

    Path(BASE_DIR).mkdir(parents=True, exist_ok=True)
    # Iniciar Flask en hilo
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()

    # Iniciar bot
    logger.info("Iniciando bot de Telegram...")
    bot.run()

if __name__ == "__main__":
    main()