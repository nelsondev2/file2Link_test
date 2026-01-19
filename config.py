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
DOWNLOAD_THREADS = 1
DOWNLOAD_TIMEOUT = 3600
MAX_RETRIES = 3
CHUNK_SIZE = 65536

# ===== NUEVAS CONFIGURACIONES =====
# Administración
OWNER_ID = os.getenv("OWNER_ID", "").split(",")
OWNER_ID = [int(x.strip()) for x in OWNER_ID if x.strip().isdigit()]

# Canal para logs (como primer bot)
BIN_CHANNEL = os.getenv("BIN_CHANNEL", None)

# Hash security
HASH_SALT = os.getenv("HASH_SALT", "nelson_file2link_secure_salt")
HASH_EXPIRE_DAYS = int(os.getenv("HASH_EXPIRE_DAYS", "30"))

# Queue limits
MAX_QUEUE_SIZE = 4
MAX_CONCURRENT_UPLOADS = 1  # Procesar UNO POR UNO
QUEUE_PROCESSING_TIMEOUT = 3600

# ===== TELEGRAM DATABASE CONFIGURATION =====
DB_CHANNEL_ID = os.getenv("DB_CHANNEL_ID", "")  # ID del canal privado para DB
# Ejemplo: -1001234567890 (con el -100 al inicio)

# ===== VALIDACIÓN Y CORRECCIÓN AUTOMÁTICA =====
# CORREGIR: Asegurar que RENDER_DOMAIN no termine con /
if RENDER_DOMAIN.endswith('/'):
    RENDER_DOMAIN = RENDER_DOMAIN.rstrip('/')
    print(f"⚠️ CORREGIDO: RENDER_DOMAIN ajustado a: {RENDER_DOMAIN}")

def validate_config():
    """Validar configuración crítica"""
    errors = []
    
    if not BOT_TOKEN or BOT_TOKEN == "tu_bot_token":
        errors.append("BOT_TOKEN no configurado")
    
    if not API_ID or API_ID == 12345678:
        errors.append("API_ID no configurado")
    
    if not API_HASH or API_HASH == "tu_api_hash":
        errors.append("API_HASH no configurado")
    
    if not RENDER_DOMAIN or "example.com" in RENDER_DOMAIN:
        errors.append("RENDER_DOMAIN no configurado correctamente")
    
    # Verificar que RENDER_DOMAIN no tenga doble barra
    if '//' in RENDER_DOMAIN.replace('https://', '').replace('http://', ''):
        errors.append("RENDER_DOMAIN contiene doble barra (//) interna")
    
    # Advertencia (no error) si no hay DB_CHANNEL_ID
    if not DB_CHANNEL_ID:
        print("⚠️ ADVERTENCIA: DB_CHANNEL_ID no configurado. Los datos NO serán persistentes en reinicios.")
    
    return errors

# Validar al importar
config_errors = validate_config()
if config_errors:
    print("⚠️ ADVERTENCIA: Errores en configuración:")
    for error in config_errors:
        print(f"  • {error}")
    print("\nConfigura las variables en Render.com → Environment Variables")
else:
    print(f"✅ Configuración validada: RENDER_DOMAIN={RENDER_DOMAIN}")