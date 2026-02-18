"""
Configuración central de File2Link.
Todos los parámetros se leen desde variables de entorno.
"""
import os

# ── Credenciales de Telegram ──────────────────────────────────────────────────
API_ID       = int(os.getenv("API_ID", "0"))
API_HASH     = os.getenv("API_HASH", "")
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")

# ── Dominio público del servidor ──────────────────────────────────────────────
PUBLIC_DOMAIN = os.getenv("RENDER_DOMAIN", "https://tu-dominio.onrender.com")

# ── Almacenamiento ────────────────────────────────────────────────────────────
STORAGE_DIR   = os.getenv("STORAGE_DIR", "storage")
METADATA_FILE = os.path.join(STORAGE_DIR, "metadata.json")

# ── Servidor web ──────────────────────────────────────────────────────────────
PORT = int(os.getenv("PORT", 8080))

# ── Límites de archivos ───────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 2000))
MAX_FILE_SIZE    = MAX_FILE_SIZE_MB * 1024 * 1024

MAX_PART_SIZE_MB = int(os.getenv("MAX_PART_SIZE_MB", 500))

# ── Descargas ─────────────────────────────────────────────────────────────────
DOWNLOAD_TIMEOUT     = int(os.getenv("DOWNLOAD_TIMEOUT", 3600))
DOWNLOAD_BUFFER_SIZE = int(os.getenv("DOWNLOAD_BUFFER_SIZE", 131072))
MAX_RETRIES          = int(os.getenv("MAX_RETRIES", 3))

# ── Recursos del servidor ─────────────────────────────────────────────────────
MAX_CONCURRENT_PACKS = int(os.getenv("MAX_CONCURRENT_PACKS", 1))
CPU_LIMIT_PERCENT    = int(os.getenv("CPU_LIMIT_PERCENT", 80))
