import os

# ===== CONFIGURACIÓN BÁSICA =====
API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN")
PORT = int(os.getenv("PORT", 8080))

# ===== GRUPOS DE TELEGRAM =====
DB_CHANNEL_ID = os.getenv("DB_CHANNEL_ID")  # Grupo para metadatos
STORAGE_CHANNEL_ID = os.getenv("STORAGE_CHANNEL_ID")  # Grupo para archivos
BOT_USERNAME = os.getenv("BOT_USERNAME", "tu_bot_username")  # @username del bot

# ===== LÍMITES =====
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_CONCURRENT_PROCESSES = 1

# ===== URLs =====
TELEGRAM_API_URL = "https://api.telegram.org"