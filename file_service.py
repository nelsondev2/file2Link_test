"""
Servicio de archivos simplificado - funciona SIN grupos
"""
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class SimpleFileService:
    def __init__(self, telegram_storage=None):
        self.storage = telegram_storage
        self.user_files = {}  # Almacenamiento en memoria
        self.file_counters = {}  # Contadores por usuario
        
    async def register_file(self, message, user_id, file_type="downloads"):
        """Registra un archivo - versión simplificada"""
        try:
            user_key = str(user_id)
            
            # Inicializar contador para el usuario
            if user_key not in self.file_counters:
                self.file_counters[user_key] = 1
            if user_key not in self.user_files:
                self.user_files[user_key] = {}
            
            # Obtener número de archivo
            file_num = self.file_counters[user_key]
            self.file_counters[user_key] += 1
            
            # Guardar referencia usando storage
            if self.storage:
                file_record = await self.storage.save_file_reference(message, user_id, file_type)
            else:
                # Fallback si no hay storage
                file_record = {
                    'user_id': user_id,
                    'file_type': file_type,
                    'timestamp': time.time(),
                    'original_name': 'archivo',
                    'file_info': {'file_id': 'unknown', 'file_size': 0}
                }
            
            if not file_record:
                return None
            
            # Guardar en memoria
            if file_type not in self.user_files[user_key]:
                self.user_files[user_key][file_type] = {}
            
            self.user_files[user_key][file_type][str(file_num)] = file_record
            
            # Generar URLs
            if self.storage:
                urls = await self.storage.get_file_urls(file_record)
            else:
                urls = {'download_url': '#', 'deep_link': '#'}
            
            logger.info(f"✅ Archivo registrado (#{file_num}) para usuario {user_id}")
            
            return {
                'number': file_num,
                'record': file_record,
                'file_type': file_type,
                'urls': urls,
                'name': file_record.get('original_name', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"❌ Error registrando archivo: {e}")
            return None
    
    async def get_file_urls(self, user_id, file_number, file_type="downloads"):
        """Obtiene URLs para un archivo"""
        try:
            user_key = str(user_id)
            
            # Verificar que el archivo existe
            if (user_key not in self.user_files or 
                file_type not in self.user_files[user_key] or
                str(file_number) not in self.user_files[user_key][file_type]):
                return None
            
            file_record = self.user_files[user_key][file_type][str(file_number)]
            
            # Generar URLs
            if self.storage:
                urls = await self.storage.get_file_urls(file_record)
            else:
                urls = {
                    'download_url': f"/download/{file_record.get('file_info', {}).get('file_id', 'unknown')}",
                    'deep_link': '#',
                    'file_id': file_record.get('file_info', {}).get('file_id', 'unknown')
                }
            
            return {
                'number': file_number,
                'name': file_record.get('original_name', 'unknown'),
                'size': file_record.get('file_info', {}).get('file_size', 0),
                'type': file_record.get('file_info', {}).get('type', 'unknown'),
                'urls': urls,
                'file_type': file_type,
                'timestamp': file_record.get('timestamp', time.time())
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo URLs: {e}")
            return None
    
    async def list_user_files(self, user_id, file_type="downloads"):
        """Lista archivos del usuario"""
        try:
            user_key = str(user_id)
            
            if user_key not in self.user_files or file_type not in self.user_files[user_key]:
                return []
            
            files = []
            
            for file_num_str, file_record in self.user_files[user_key][file_type].items():
                file_number = int(file_num_str)
                
                # Generar URLs
                if self.storage:
                    urls = await self.storage.get_file_urls(file_record)
                else:
                    urls = {
                        'download_url': '#',
                        'deep_link': '#',
                        'file_id': file_record.get('file_info', {}).get('file_id', 'unknown')
                    }
                
                files.append({
                    'number': file_number,
                    'name': file_record.get('original_name', 'unknown'),
                    'size': file_record.get('file_info', {}).get('file_size', 0),
                    'type': file_record.get('file_info', {}).get('type', 'unknown'),
                    'urls': urls,
                    'file_type': file_type,
                    'timestamp': file_record.get('timestamp', time.time()),
                    'date': datetime.fromtimestamp(file_record.get('timestamp', time.time())).strftime('%Y-%m-%d %H:%M')
                })
            
            # Ordenar por número (más reciente primero)
            files.sort(key=lambda x: x['number'], reverse=True)
            return files
            
        except Exception as e:
            logger.error(f"Error listando archivos: {e}")
            return []
    
    async def delete_file(self, user_id, file_number, file_type="downloads"):
        """Elimina un archivo"""
        try:
            user_key = str(user_id)
            
            # Verificar que existe
            if (user_key not in self.user_files or 
                file_type not in self.user_files[user_key] or
                str(file_number) not in self.user_files[user_key][file_type]):
                return False, "Archivo no encontrado"
            
            # Eliminar
            del self.user_files[user_key][file_type][str(file_number)]
            
            return True, f"✅ Archivo #{file_number} eliminado"
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False, f"❌ Error: {str(e)}"

# Instancia global - ¡IMPORTANTE!
file_service = SimpleFileService()

async def initialize_file_service(storage=None):
    """Inicializa el servicio de archivos - VERSIÓN SIMPLIFICADA"""
    global file_service
    
    # Si ya existe una instancia, actualizarla con storage
    if storage and hasattr(file_service, 'storage'):
        file_service.storage = storage
    
    logger.info("✅ Servicio de archivos inicializado (modo simplificado)")
    return file_service