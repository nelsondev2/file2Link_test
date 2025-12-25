import os
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
import logging

logger = logging.getLogger(__name__)

@dataclass
class AppConfig:
    """Configuración centralizada y validada"""
    
    # ===== TELEGRAM API =====
    API_ID: int = field(default_factory=lambda: int(os.getenv("API_ID", 0)))
    API_HASH: str = field(default_factory=lambda: os.getenv("API_HASH", ""))
    BOT_TOKEN: str = field(default_factory=lambda: os.getenv("BOT_TOKEN", ""))
    
    # ===== SERVIDOR WEB =====
    PORT: int = field(default_factory=lambda: int(os.getenv("PORT", 8080)))
    RENDER_DOMAIN: str = field(
        default_factory=lambda: os.getenv(
            "RENDER_DOMAIN", 
            "https://nelson-file2link.onrender.com"
        )
    )
    
    # ===== DIRECTORIOS =====
    BASE_DIR: str = "storage"
    SESSION_DIR: str = "sessions"
    LOGS_DIR: str = "logs"
    TEMP_DIR: str = "temp"
    
    # ===== LÍMITES DE SISTEMA =====
    MAX_FILE_SIZE_MB: int = 2000
    MAX_CONCURRENT_PROCESSES: int = 1
    CPU_USAGE_LIMIT: int = 80
    MEMORY_USAGE_LIMIT: int = 90
    
    # ===== CONFIGURACIÓN DE DESCARGA =====
    MAX_PART_SIZE_MB: int = 100
    COMPRESSION_TIMEOUT: int = 600
    DOWNLOAD_BUFFER_SIZE: int = 131072  # 128KB
    DOWNLOAD_THREADS: int = 2
    DOWNLOAD_TIMEOUT: int = 3600
    MAX_RETRIES: int = 3
    CHUNK_SIZE: int = 65536
    
    # ===== VALORES CALCULADOS =====
    @property
    def MAX_FILE_SIZE(self) -> int:
        """Tamaño máximo en bytes"""
        return self.MAX_FILE_SIZE_MB * 1024 * 1024
    
    @property
    def MAX_PART_SIZE(self) -> int:
        """Tamaño máximo de partes en bytes"""
        return self.MAX_PART_SIZE_MB * 1024 * 1024
    
    # ===== MÉTODOS DE VALIDACIÓN =====
    def validate(self) -> bool:
        """Valida que toda la configuración sea correcta"""
        errors = []
        
        if not self.BOT_TOKEN or self.BOT_TOKEN == "tu_bot_token":
            errors.append("BOT_TOKEN no configurado o es el valor por defecto")
        
        if not self.API_ID or self.API_ID == 12345678:
            errors.append("API_ID no configurado o es el valor por defecto")
        
        if not self.API_HASH or self.API_HASH == "tu_api_hash":
            errors.append("API_HASH no configurado o es el valor por defecto")
        
        if self.MAX_FILE_SIZE_MB > 4000:
            errors.append("MAX_FILE_SIZE_MB no puede ser mayor a 4000MB (límite de Telegram)")
        
        if self.MAX_CONCURRENT_PROCESSES < 1:
            errors.append("MAX_CONCURRENT_PROCESSES debe ser al menos 1")
        
        if errors:
            error_msg = "\n".join([f"  • {error}" for error in errors])
            logger.error(f"Errores de configuración:\n{error_msg}")
            return False
        
        return True
    
    def ensure_directories(self):
        """Crea todos los directorios necesarios"""
        directories = [
            self.BASE_DIR,
            self.SESSION_DIR,
            self.LOGS_DIR,
            self.TEMP_DIR
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
            logger.debug(f"Directorio creado/verificado: {directory}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte la configuración a diccionario"""
        return {
            key: value for key, value in self.__dict__.items() 
            if not key.startswith('_')
        }
    
    def __post_init__(self):
        """Validación automática al crear instancia"""
        self.ensure_directories()
        if not self.validate():
            raise ValueError("Configuración inválida. Verifica las variables de entorno.")


# Instancia global de configuración
config = AppConfig()

# Exportar variables individuales (para compatibilidad)
API_ID = config.API_ID
API_HASH = config.API_HASH
BOT_TOKEN = config.BOT_TOKEN
RENDER_DOMAIN = config.RENDER_DOMAIN
BASE_DIR = config.BASE_DIR
PORT = config.PORT
MAX_PART_SIZE_MB = config.MAX_PART_SIZE_MB
COMPRESSION_TIMEOUT = config.COMPRESSION_TIMEOUT
MAX_CONCURRENT_PROCESSES = config.MAX_CONCURRENT_PROCESSES
CPU_USAGE_LIMIT = config.CPU_USAGE_LIMIT
MAX_FILE_SIZE_MB = config.MAX_FILE_SIZE_MB
MAX_FILE_SIZE = config.MAX_FILE_SIZE
DOWNLOAD_BUFFER_SIZE = config.DOWNLOAD_BUFFER_SIZE
DOWNLOAD_THREADS = config.DOWNLOAD_THREADS
DOWNLOAD_TIMEOUT = config.DOWNLOAD_TIMEOUT
MAX_RETRIES = config.MAX_RETRIES
CHUNK_SIZE = config.CHUNK_SIZE