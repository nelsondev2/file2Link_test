import os
import logging
import json
import tempfile
from config import COOKIES_DIR, COOKIES_GLOBAL_FILE

logger = logging.getLogger(__name__)

class CookiesService:
    def __init__(self):
        os.makedirs(COOKIES_DIR, exist_ok=True)
    
    def save_global_cookies(self, cookies_content, file_extension=".txt"):
        """Guarda las cookies GLOBALES para todos los usuarios"""
        try:
            # Guardar archivo de cookies global
            cookies_file = COOKIES_GLOBAL_FILE
            
            with open(cookies_file, 'w', encoding='utf-8') as f:
                f.write(cookies_content)
            
            logger.info(f"Cookies GLOBALES guardadas: {cookies_file}")
            return True, "✅ **Cookies GLOBALES guardadas correctamente.**\n\nAhora TODAS las descargas de YouTube usarán estas cookies para acceder a contenido restringido."
            
        except Exception as e:
            logger.error(f"Error guardando cookies globales: {e}")
            return False, f"❌ **Error al guardar cookies:** {str(e)}"
    
    def get_global_cookies_path(self):
        """Obtiene la ruta del archivo de cookies GLOBALES"""
        if os.path.exists(COOKIES_GLOBAL_FILE):
            return COOKIES_GLOBAL_FILE
        
        # También buscar con extensión .json por compatibilidad
        json_cookies_file = COOKIES_GLOBAL_FILE.replace('.txt', '.json')
        if os.path.exists(json_cookies_file):
            return json_cookies_file
            
        return None
    
    def delete_global_cookies(self):
        """Elimina las cookies GLOBALES"""
        try:
            if not os.path.exists(COOKIES_GLOBAL_FILE):
                # También verificar archivo .json
                json_cookies_file = COOKIES_GLOBAL_FILE.replace('.txt', '.json')
                if not os.path.exists(json_cookies_file):
                    return False, "❌ **No hay cookies GLOBALES configuradas.**"
                else:
                    os.remove(json_cookies_file)
                    logger.info("Cookies GLOBALES eliminadas (JSON)")
                    return True, "✅ **Cookies GLOBALES eliminadas correctamente.**"
            
            os.remove(COOKIES_GLOBAL_FILE)
            logger.info("Cookies GLOBALES eliminadas")
            return True, "✅ **Cookies GLOBALES eliminadas correctamente.**"
            
        except Exception as e:
            logger.error(f"Error eliminando cookies globales: {e}")
            return False, f"❌ **Error al eliminar cookies:** {str(e)}"
    
    def has_global_cookies(self):
        """Verifica si hay cookies GLOBALES configuradas"""
        return self.get_global_cookies_path() is not None
    
    def get_global_cookies_info(self):
        """Obtiene información sobre las cookies GLOBALES"""
        cookies_path = self.get_global_cookies_path()
        
        if not cookies_path:
            return None
        
        try:
            file_size = os.path.getsize(cookies_path)
            file_extension = os.path.splitext(cookies_path)[1]
            
            return {
                'path': cookies_path,
                'size': file_size,
                'size_mb': file_size / (1024 * 1024),
                'extension': file_extension,
                'exists': True
            }
        except Exception as e:
            logger.error(f"Error obteniendo info de cookies globales: {e}")
            return None

cookies_service = CookiesService()
