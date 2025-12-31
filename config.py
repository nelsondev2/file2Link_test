import os

# ===== CONFIGURACIÓN GENERAL =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
BASE_DIR = "storage"
PORT = int(os.getenv("PORT", 8080))

# ===== LIMITES DE RECURSOS =====
# Tamaño máximo de archivo individual (MB)
MAX_FILE_SIZE_MB = 2000  # 2 GB
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# Cuota máxima por usuario (MB)
MAX_USER_QUOTA_MB = 3000  # 3 GB
MAX_USER_QUOTA = MAX_USER_QUOTA_MB * 1024 * 1024
USER_QUOTA_WARNING_PERCENT = 80  # Avisar al 80%

# Configuración optimizada para CPU limitada
MAX_PART_SIZE_MB = 100
COMPRESSION_TIMEOUT = 600
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 80

# Descarga rápida
DOWNLOAD_BUFFER_SIZE = 131072
DOWNLOAD_THREADS = 2
DOWNLOAD_TIMEOUT = 3600
MAX_RETRIES = 3
CHUNK_SIZE = 65536

# ===== MODO MANTENIMIENTO =====
MAINTENANCE_MODE = bool(int(os.getenv("MAINTENANCE_MODE", "0")))
MAINTENANCE_MESSAGE = (
    "⚠️ El sistema se encuentra actualmente en modo mantenimiento.\n\n"
    "Por favor, inténtalo nuevamente en unos minutos."
)

# ===== LOGS =====
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
SYSTEM_LOG_FILE = os.path.join(LOG_DIR, "system.log")
USER_LOG_PREFIX = os.path.join(LOG_DIR, "user_")  # user_<id>.log