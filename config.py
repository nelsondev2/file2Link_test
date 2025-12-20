import os
from datetime import timedelta

# ==================== CONFIGURACIÓN PRINCIPAL ====================
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
BASE_DIR = "storage"
PORT = int(os.getenv("PORT", 8080))
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())

# ==================== SEGURIDAD POR USERNAME (SOLO PARA WEB) ====================
# Solo estos usernames de Telegram pueden acceder a la URL base (/ y /health)
# El bot de Telegram (@watch_bot) puede monitorear
ALLOWED_WEB_USERNAMES = [
    "watch_bot",  # Tu bot de monitoreo
    "nelson_file2link_bot",  # El bot principal si quieres que también pueda monitorear
]

# ==================== LÍMITES DE SEGURIDAD ====================
MAX_USER_STORAGE_MB = 5000
MAX_FILES_PER_USER = 100
SESSION_TIMEOUT = timedelta(hours=24)

# ==================== RATE LIMITING ====================
MAX_REQUESTS_PER_MINUTE = 30
DOWNLOAD_LINK_EXPIRY_HOURS = 24

# ==================== CONFIGURACIÓN OPTIMIZADA ====================
MAX_PART_SIZE_MB = 100
MAX_CONCURRENT_PROCESSES = 2
CPU_USAGE_LIMIT = 75

# ==================== TAMAÑOS DE ARCHIVO ====================
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# ==================== CONFIGURACIÓN DE DESCARGA ====================
DOWNLOAD_BUFFER_SIZE = 65536
DOWNLOAD_TIMEOUT = 3600
MAX_RETRIES = 3
CHUNK_SIZE = 32768

# ==================== URLs SEGURAS ====================
ALLOWED_REFERERS = ["t.me", "telegram.org"]