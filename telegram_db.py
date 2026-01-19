import json
import time
import logging
import asyncio
from pyrogram import Client
from config import DB_CHANNEL_ID

logger = logging.getLogger(__name__)

class TelegramDB:
    def __init__(self, client):
        self.client = client
        self.db_channel_id = None
        
        if DB_CHANNEL_ID:
            try:
                self.db_channel_id = int(DB_CHANNEL_ID)
                logger.info(f"✅ Telegram DB configurada en canal: {self.db_channel_id}")
            except ValueError:
                logger.warning(f"⚠️ DB_CHANNEL_ID inválido: {DB_CHANNEL_ID}")
        else:
            logger.warning("⚠️ DB_CHANNEL_ID no configurado. Usando almacenamiento local.")
    
    async def is_available(self):
        """Verificar si Telegram DB está disponible"""
        if not self.db_channel_id or not self.client:
            return False
        
        try:
            # Intentar acceder al canal
            chat = await self.client.get_chat(self.db_channel_id)
            return chat is not None
        except Exception as e:
            logger.error(f"❌ Error accediendo a canal DB: {e}")
            return False
    
    async def save_data(self, data_type, data_id, data):
        """Guardar datos en Telegram"""
        if not await self.is_available():
            return False
        
        try:
            # Crear mensaje estructurado
            message_text = self._create_db_message(data_type, data_id, data)
            
            # Enviar al canal
            message = await self.client.send_message(
                chat_id=self.db_channel_id,
                text=message_text,
                disable_notification=True,
                disable_web_page_preview=True
            )
            
            logger.debug(f"📝 Datos guardados en Telegram DB: {data_type}/{data_id} (msg_id: {message.id})")
            return message.id
            
        except Exception as e:
            logger.error(f"Error guardando en Telegram DB: {e}")
            return False
    
    async def load_data(self, data_type, data_id=None):
        """Cargar datos desde Telegram"""
        if not await self.is_available():
            return None
        
        try:
            # Buscar en los mensajes del canal
            messages = []
            async for message in self.client.search_messages(
                chat_id=self.db_channel_id,
                query=f"#DB {data_type}"
            ):
                if data_id:
                    # Buscar por ID específico
                    if f"ID: {data_id}" in message.text:
                        return self._parse_db_message(message.text)
                else:
                    # Cargar todos de este tipo
                    parsed = self._parse_db_message(message.text)
                    if parsed:
                        messages.append(parsed)
            
            if data_id:
                return None  # No encontrado
            else:
                return messages
                
        except Exception as e:
            logger.error(f"Error cargando desde Telegram DB: {e}")
            return None if data_id else []
    
    async def update_data(self, data_type, data_id, new_data):
        """Actualizar datos en Telegram"""
        if not await self.is_available():
            return False
        
        try:
            # Primero buscar el mensaje existente
            message_id = await self._find_message_id(data_type, data_id)
            
            if not message_id:
                return await self.save_data(data_type, data_id, new_data)
            
            # Actualizar el mensaje
            message_text = self._create_db_message(data_type, data_id, new_data)
            
            await self.client.edit_message_text(
                chat_id=self.db_channel_id,
                message_id=message_id,
                text=message_text,
                disable_web_page_preview=True
            )
            
            logger.debug(f"✏️ Datos actualizados en Telegram DB: {data_type}/{data_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error actualizando en Telegram DB: {e}")
            return False
    
    async def delete_data(self, data_type, data_id):
        """Eliminar datos de Telegram"""
        if not await self.is_available():
            return False
        
        try:
            message_id = await self._find_message_id(data_type, data_id)
            
            if message_id:
                await self.client.delete_messages(
                    chat_id=self.db_channel_id,
                    message_ids=message_id
                )
                logger.debug(f"🗑️ Datos eliminados de Telegram DB: {data_type}/{data_id}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error eliminando de Telegram DB: {e}")
            return False
    
    async def _find_message_id(self, data_type, data_id):
        """Encontrar ID de mensaje por tipo e ID de datos"""
        try:
            async for message in self.client.search_messages(
                chat_id=self.db_channel_id,
                query=f"#DB {data_type} ID: {data_id}"
            ):
                if f"ID: {data_id}" in message.text:
                    return message.id
        except Exception as e:
            logger.error(f"Error buscando mensaje: {e}")
        
        return None
    
    def _create_db_message(self, data_type, data_id, data):
        """Crear texto de mensaje estructurado para DB"""
        timestamp = int(time.time())
        
        message = f"""#DB {data_type}
ID: {data_id}
Timestamp: {timestamp}
---
{json.dumps(data, ensure_ascii=False, indent=2)}
---
#END"""
        
        # Telegram limita a 4096 caracteres por mensaje
        if len(message) > 4000:
            # Si es muy grande, comprimir JSON
            data_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
            message = f"""#DB {data_type}
ID: {data_id}
Timestamp: {timestamp}
---
{data_str}
---
#END"""
        
        return message
    
    def _parse_db_message(self, message_text):
        """Parsear mensaje de DB"""
        try:
            lines = message_text.split('\n')
            
            if len(lines) < 5 or not lines[0].startswith('#DB'):
                return None
            
            data_type = lines[0].replace('#DB', '').strip()
            data_id = lines[1].replace('ID:', '').strip()
            
            # Encontrar el JSON
            json_start = message_text.find('---\n') + 4
            json_end = message_text.rfind('\n---')
            
            if json_start > 0 and json_end > json_start:
                json_str = message_text[json_start:json_end]
                data = json.loads(json_str)
                
                return {
                    'type': data_type,
                    'id': data_id,
                    'data': data,
                    'timestamp': lines[2].replace('Timestamp:', '').strip()
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error parseando mensaje DB: {e}")
            return None
    
    async def get_all_users(self):
        """Obtener todos los usuarios"""
        return await self.load_data("USER")
    
    async def get_all_files(self, user_id=None):
        """Obtener todos los archivos"""
        files = await self.load_data("FILE")
        
        if user_id and files:
            user_files = []
            for f in files:
                if 'data' in f and f['data'].get('user_id') == user_id:
                    user_files.append(f)
            return user_files
        
        return files
    
    async def get_all_hashes(self):
        """Obtener todos los hashes"""
        return await self.load_data("HASH")
    
    async def cleanup_old_hashes(self):
        """Limpiar hashes expirados"""
        hashes = await self.get_all_hashes()
        current_time = time.time()
        
        deleted = 0
        if hashes:
            for hash_data in hashes:
                if 'data' in hash_data:
                    expires_at = hash_data['data'].get('expires_at', 0)
                    if expires_at and expires_at < current_time:
                        success = await self.delete_data("HASH", hash_data['id'])
                        if success:
                            deleted += 1
        
        return deleted

# Instancia global (se inicializará después)
telegram_db = None

async def init_telegram_db(client):
    """Inicializar Telegram DB"""
    global telegram_db
    telegram_db = TelegramDB(client)
    
    if await telegram_db.is_available():
        logger.info("✅ Telegram DB inicializada y lista")
        return True
    else:
        logger.warning("⚠️ Telegram DB no disponible")
        return False