"""
Servicio de archivos que solo maneja referencias a Telegram
CERO descargas, CERO almacenamiento en Render
"""
import os
import logging
import time
from datetime import datetime

logger = logging.getLogger(__name__)

class TelegramFileService:
    def __init__(self, telegram_storage):
        self.storage = telegram_storage
        self.user_metadata = {}  # Cache en memoria
        self.loaded_users = set()
        
    async def initialize_user(self, user_id):
        """Carga metadatos del usuario desde Telegram"""
        try:
            user_key = str(user_id)
            
            # Si ya está cargado, usar cache
            if user_key in self.loaded_users:
                return True
            
            # Cargar desde Telegram
            metadata = await self.storage.load_metadata(user_id, "files")
            
            if metadata:
                self.user_metadata[user_key] = metadata
                self.loaded_users.add(user_key)
                logger.info(f"✅ Metadata cargada desde Telegram para usuario {user_id}")
                return True
            else:
                # Inicializar nuevo usuario
                self.user_metadata[user_key] = {
                    'downloads': {
                        'next_number': 1,
                        'files': {},
                        'created': datetime.now().isoformat()
                    },
                    'packed': {
                        'next_number': 1,
                        'files': {},
                        'created': datetime.now().isoformat()
                    },
                    'user_info': {
                        'id': user_id,
                        'first_use': datetime.now().isoformat(),
                        'last_activity': datetime.now().isoformat()
                    }
                }
                self.loaded_users.add(user_key)
                logger.info(f"✅ Nuevo usuario inicializado: {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error inicializando usuario {user_id}: {e}")
            return False
    
    async def save_user_metadata(self, user_id):
        """Guarda metadatos del usuario en Telegram"""
        try:
            user_key = str(user_id)
            
            if user_key not in self.user_metadata:
                return False
            
            # Actualizar timestamp de actividad
            if 'user_info' in self.user_metadata[user_key]:
                self.user_metadata[user_key]['user_info']['last_activity'] = datetime.now().isoformat()
            
            await self.storage.save_metadata(user_id, "files", self.user_metadata[user_key])
            return True
            
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
            return False
    
    async def register_file(self, message, user_id, file_type="downloads"):
        """Registra un archivo (solo referencia, NO descarga)"""
        try:
            user_key = str(user_id)
            
            # Inicializar usuario si no está
            if user_key not in self.loaded_users:
                await self.initialize_user(user_id)
            
            # Verificar que el tipo de archivo existe
            if file_type not in self.user_metadata[user_key]:
                self.user_metadata[user_key][file_type] = {
                    'next_number': 1,
                    'files': {},
                    'created': datetime.now().isoformat()
                }
            
            # Obtener siguiente número
            file_num = self.user_metadata[user_key][file_type]['next_number']
            self.user_metadata[user_key][file_type]['next_number'] += 1
            
            # Guardar referencia en Telegram (CERO descarga)
            file_record = await self.storage.save_file_reference(message, user_id, file_type)
            
            if not file_record:
                return None
            
            # Guardar en metadata local
            self.user_metadata[user_key][file_type]['files'][str(file_num)] = file_record
            
            # Guardar metadata en Telegram
            await self.save_user_metadata(user_id)
            
            logger.info(f"✅ Archivo registrado (#{file_num}): {file_record.get('original_name')}")
            
            # Generar URLs inmediatamente
            urls = await self.storage.get_file_urls(file_record)
            
            return {
                'number': file_num,
                'record': file_record,
                'file_type': file_type,
                'urls': urls,
                'name': file_record.get('original_name', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error registrando archivo: {e}")
            return None
    
    async def get_file_urls(self, user_id, file_number, file_type="downloads"):
        """Obtiene URLs para un archivo"""
        try:
            user_key = str(user_id)
            
            # Asegurarse de que el usuario está cargado
            if user_key not in self.loaded_users:
                await self.initialize_user(user_id)
            
            # Verificar que el archivo existe
            if (user_key not in self.user_metadata or 
                file_type not in self.user_metadata[user_key] or
                str(file_number) not in self.user_metadata[user_key][file_type]['files']):
                return None
            
            file_record = self.user_metadata[user_key][file_type]['files'][str(file_number)]
            
            # Generar URLs
            urls = await self.storage.get_file_urls(file_record)
            
            if urls:
                return {
                    'number': file_number,
                    'name': file_record.get('original_name', 'unknown'),
                    'size': file_record.get('file_info', {}).get('file_size', 0),
                    'type': file_record.get('file_info', {}).get('type', 'unknown'),
                    'urls': urls,
                    'file_type': file_type,
                    'timestamp': file_record.get('timestamp', time.time())
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error obteniendo URLs: {e}")
            return None
    
    async def list_user_files(self, user_id, file_type="downloads"):
        """Lista archivos del usuario"""
        try:
            user_key = str(user_id)
            
            # Cargar usuario si no está
            if user_key not in self.loaded_users:
                await self.initialize_user(user_id)
            
            # Verificar que el tipo existe
            if file_type not in self.user_metadata[user_key]:
                return []
            
            files = []
            
            for file_num_str, file_record in self.user_metadata[user_key][file_type]['files'].items():
                file_number = int(file_num_str)
                
                # Generar URLs
                urls = await self.storage.get_file_urls(file_record)
                
                if urls:
                    files.append({
                        'number': file_number,
                        'name': file_record.get('original_name', 'unknown'),
                        'size': file_record.get('file_info', {}).get('file_size', 0),
                        'type': file_record.get('file_info', {}).get('type', 'unknown'),
                        'mime_type': file_record.get('file_info', {}).get('mime_type', 'unknown'),
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
        """Elimina referencia a archivo"""
        try:
            user_key = str(user_id)
            
            # Cargar usuario si no está
            if user_key not in self.loaded_users:
                await self.initialize_user(user_id)
            
            # Verificar que el archivo existe
            if (user_key not in self.user_metadata or 
                file_type not in self.user_metadata[user_key] or
                str(file_number) not in self.user_metadata[user_key][file_type]['files']):
                return False, "Archivo no encontrado"
            
            # Obtener registro del archivo
            file_record = self.user_metadata[user_key][file_type]['files'][str(file_number)]
            file_name = file_record.get('original_name', f"#{file_number}")
            
            # Opcional: Eliminar referencia del canal de storage
            await self.storage.delete_file_reference(file_record)
            
            # Eliminar de metadata local
            del self.user_metadata[user_key][file_type]['files'][str(file_number)]
            
            # Reorganizar números si es necesario (opcional)
            # ...
            
            # Guardar cambios
            await self.save_user_metadata(user_id)
            
            # NOTA: El archivo real sigue en Telegram, solo eliminamos la referencia
            
            return True, f"✅ Archivo eliminado: #{file_number} - {file_name}"
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False, f"❌ Error: {str(e)}"
    
    async def get_user_stats(self, user_id):
        """Obtiene estadísticas del usuario"""
        try:
            user_key = str(user_id)
            
            if user_key not in self.loaded_users:
                await self.initialize_user(user_id)
            
            if user_key not in self.user_metadata:
                return None
            
            downloads = await self.list_user_files(user_id, "downloads")
            packed = await self.list_user_files(user_id, "packed")
            
            total_files = len(downloads) + len(packed)
            total_size = sum(f['size'] for f in downloads + packed if f['size'])
            
            return {
                'user_id': user_id,
                'downloads_count': len(downloads),
                'packed_count': len(packed),
                'total_files': total_files,
                'total_size': total_size,
                'total_size_mb': total_size / (1024 * 1024) if total_size > 0 else 0,
                'first_use': self.user_metadata[user_key].get('user_info', {}).get('first_use', 'unknown'),
                'last_activity': self.user_metadata[user_key].get('user_info', {}).get('last_activity', 'unknown')
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo stats: {e}")
            return None
    
    async def cleanup_user_data(self, user_id):
        """Limpia todos los datos del usuario"""
        try:
            user_key = str(user_id)
            
            if user_key in self.user_metadata:
                # Opcional: Eliminar referencias de storage
                for file_type in ['downloads', 'packed']:
                    if file_type in self.user_metadata[user_key]:
                        for file_record in self.user_metadata[user_key][file_type]['files'].values():
                            await self.storage.delete_file_reference(file_record)
                
                # Eliminar metadata
                del self.user_metadata[user_key]
                if user_key in self.loaded_users:
                    self.loaded_users.remove(user_key)
                
                # También eliminar de Telegram (opcional)
                # Para esto necesitaríamos trackear el message_id de la metadata
                
                return True, "✅ Todos los datos del usuario limpiados"
            
            return False, "❌ Usuario no encontrado"
            
        except Exception as e:
            logger.error(f"Error limpiando datos: {e}")
            return False, f"❌ Error: {str(e)}"

# Instancia global
file_service = None

async def initialize_file_service(storage):
    """Inicializa el servicio de archivos"""
    global file_service
    
    if storage is None:
        logger.error("❌ No se pudo inicializar file_service: storage es None")
        return None
    
    file_service = TelegramFileService(storage)
    logger.info("✅ Servicio de archivos Telegram inicializado (0 CPU, 0 almacenamiento)")
    return file_service