import os
from datetime import timedelta

# Configuración principal
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "")
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://file2link-test.onrender.com")
BASE_DIR = "storage"
PORT = int(os.getenv("PORT", 8080))
SECRET_KEY = os.getenv("SECRET_KEY", os.urandom(24).hex())

# Límites
MAX_USER_STORAGE_MB = 5000
MAX_FILES_PER_USER = 100
DOWNLOAD_LINK_EXPIRY_HOURS = 24

# Configuración optimizada
MAX_PART_SIZE_MB = 100
MAX_CONCURRENT_PROCESSES = 2
CPU_USAGE_LIMIT = 75

# Tamaños de archivo
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024

# Configuración de descarga
DOWNLOAD_BUFFER_SIZE = 65536
DOWNLOAD_TIMEOUT = 3600
MAX_RETRIES = 3
CHUNK_SIZE = 32768