import os

# ===== CONFIGURACIÓN BÁSICA =====
API_ID = int(os.getenv("API_ID", "12345678"))
API_HASH = os.getenv("API_HASH", "tu_api_hash")
BOT_TOKEN = os.getenv("BOT_TOKEN", "tu_bot_token")
RENDER_DOMAIN = os.getenv("RENDER_DOMAIN", "https://file2link-test.onrender.com")
PORT = int(os.getenv("PORT", 8080))

BOT_USERNAME = os.getenv("BOT_USERNAME", "@test_nelsonfile2linkbot")

# ===== LÍMITES =====
MAX_FILE_SIZE_MB = 2000
MAX_FILE_SIZE = MAX_FILE_SIZE_MB * 1024 * 1024
MAX_CONCURRENT_PROCESSES = 1

# ===== URLs =====
TELEGRAM_API_URL = "https://api.telegram.org"