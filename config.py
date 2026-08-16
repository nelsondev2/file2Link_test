import os

# ===== CONFIGURACION =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://file2link.onrender.com")
BASE_DIR = "storage"
PORT = int(os.getenv("PORT", 8080))

# Optimizacion para CPU limitada
MAX_PART_SIZE_MB = 500
COMPRESSION_TIMEOUT = 600
MAX_CONCURRENT_PROCESSES = 1
CPU_USAGE_LIMIT = 80

# Tamaño maximo de archivos
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# Descarga
DOWNLOAD_BUFFER_SIZE = 131072
DOWNLOAD_THREADS = 2
DOWNLOAD_TIMEOUT = 3600
MAX_RETRIES = 3
CHUNK_SIZE = 65536

# Cola
MAX_QUEUE_PER_USER = 20
QUEUE_PROCESSING_DELAY = 0.3
