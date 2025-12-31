import os

# ===== CONFIGURACIÓN OPTIMIZADA =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
BASE_DIR = "storage"
PORT = int(os.getenv("PORT", 8080))

# Configuración optimizada para CPU limitada
MAX_PART_SIZE_MB = 100
COMPRESSION_TIMEOUT = 600
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 80

# ✅ Tamaño máximo de archivos configurable
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# ⬇️ Configuración para descarga rápida
DOWNLOAD_BUFFER_SIZE = 131072
DOWNLOAD_THREADS = 2
DOWNLOAD_TIMEOUT = 3600
MAX_RETRIES = 3
CHUNK_SIZE = 65536
