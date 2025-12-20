"""
Sistema de almacenamiento 100% en Telegram - CERO carga en Render
"""
import logging
import time
import json
from datetime import datetime
from pyrogram.types import Message
from pyrogram import Client

from config import DB_CHANNEL_ID, STORAGE_CHANNEL_ID, BOT_USERNAME, BOT_TOKEN, RENDER_DOMAIN

logger = logging.getLogger(__name__)

class TelegramStorage:
    def __init__(self, client: Client):
        self.client = client
        self.db_channel_id = int(DB_CHANNEL_ID)
        self.storage_channel_id = int(STORAGE_CHANNEL_ID)
        
    async def save_metadata(self, user_id, data_type, data):
        """Guarda metadatos en el canal de base de datos"""
        try:
            key = f"user_{user_id}_{data_type}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Formato simple para metadata
            metadata_text = f"""📁 METADATA | {key} | {timestamp}
User: {user_id}
Type: {data_type}
Created: {datetime.now().isoformat()}
"""
            
            # Guardar como mensaje de texto
            message = await self.client.send_message(
                chat_id=self.db_channel_id,
                text=metadata_text
            )
            
            # Guardar datos reales como documento JSON
            data_json = json.dumps(data, ensure_ascii=False, indent=2)
            
            # Crear archivo temporal con los datos
            import tempfile
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                f.write(data_json)
                temp_file = f.name
            
            try:
                # Enviar como documento
                await self.client.send_document(
                    chat_id=self.db_channel_id,
                    document=temp_file,
                    file_name=f"{key}_{timestamp}.json",
                    caption=f"📁 DATA | {key}",
                    reply_to_message_id=message.id
                )
            finally:
                # Limpiar archivo temporal
                import os
                os.unlink(temp_file)
            
            logger.info(f"💾 Metadata guardada: {key} (msg {message.id})")
            return message.id
            
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
            return None
    
    async def load_metadata(self, user_id, data_type):
        """Carga metadatos desde el canal"""
        try:
            key = f"user_{user_id}_{data_type}"
            
            # Buscar mensaje principal
            async for message in self.client.search_messages(
                chat_id=self.db_channel_id,
                query=f"📁 METADATA | {key}",
                limit=10
            ):
                if message.text and f"📁 METADATA | {key}" in message.text:
                    # Buscar mensaje de datos (reply o siguiente)
                    async for reply in self.client.get_chat_history(
                        chat_id=self.db_channel_id,
                        limit=10,
                        offset_id=message.id
                    ):
                        if reply.document and reply.caption and f"📁 DATA | {key}" in reply.caption:
                            # Descargar el documento JSON
                            import tempfile
                            import os
                            
                            temp_file = f"temp_{key}.json"
                            await self.client.download_media(reply, file_name=temp_file)
                            
                            try:
                                with open(temp_file, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                return data
                            finally:
                                if os.path.exists(temp_file):
                                    os.unlink(temp_file)
            
            return None
            
        except Exception as e:
            logger.error(f"Error cargando metadata: {e}")
            return None
    
    async def save_file_reference(self, message: Message, user_id, file_type="downloads"):
        """Guarda referencia a archivo en Telegram (NO descarga el contenido)"""
        try:
            # Obtener file_id y file_unique_id de Telegram
            file_info = self._extract_file_info(message)
            if not file_info:
                return None
            
            # Crear registro de archivo
            file_record = {
                'user_id': user_id,
                'file_type': file_type,
                'file_info': file_info,
                'timestamp': time.time(),
                'original_name': file_info.get('file_name', 'unknown'),
                'message_id': message.id,
                'chat_id': message.chat.id if message.chat else user_id,
                'date': message.date.timestamp() if message.date else time.time()
            }
            
            # Guardar referencia en canal de storage
            storage_text = f"""📦 FILE_REF | {user_id} | {file_type}
File: {file_info.get('file_name', 'unknown')}
Size: {file_info.get('file_size', 0)} bytes
Type: {file_info.get('mime_type', 'unknown')}
Time: {datetime.now().isoformat()}
FileID: {file_info.get('file_id')}
UniqueID: {file_info.get('file_unique_id')}
"""
            
            storage_msg = await self.client.send_message(
                chat_id=self.storage_channel_id,
                text=storage_text
            )
            
            file_record['storage_msg_id'] = storage_msg.id
            
            logger.info(f"✅ Archivo referenciado en Telegram: {file_info.get('file_name')}")
            return file_record
            
        except Exception as e:
            logger.error(f"Error guardando referencia de archivo: {e}")
            return None
    
    async def get_file_urls(self, file_record):
        """Genera URLs para acceder al archivo"""
        try:
            file_id = file_record['file_info']['file_id']
            user_id = file_record['user_id']
            
            # 1. Deep link de Telegram
            deep_link = f"https://t.me/{BOT_USERNAME}?start=file_{file_id}_{user_id}"
            
            # 2. URL de nuestro proxy
            proxy_url = f"{RENDER_DOMAIN}/file/{file_id}/{user_id}"
            
            # 3. URL directa a API de Telegram (requiere token)
            direct_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_id}"
            
            # 4. URL para descarga directa
            download_url = f"{RENDER_DOMAIN}/download/{file_id}"
            
            return {
                'deep_link': deep_link,
                'proxy_url': proxy_url,
                'direct_url': direct_url,
                'download_url': download_url,
                'file_id': file_id,
                'telegram_url': f"tg://file?id={file_id}"
            }
            
        except Exception as e:
            logger.error(f"Error generando URLs: {e}")
            return None
    
    def _extract_file_info(self, message: Message):
        """Extrae información del archivo de un mensaje de Telegram"""
        try:
            file_info = {}
            
            if message.document:
                file_info = {
                    'file_id': message.document.file_id,
                    'file_unique_id': message.document.file_unique_id,
                    'file_name': message.document.file_name,
                    'mime_type': message.document.mime_type,
                    'file_size': message.document.file_size,
                    'type': 'document'
                }
            elif message.video:
                file_info = {
                    'file_id': message.video.file_id,
                    'file_unique_id': message.video.file_unique_id,
                    'file_name': message.video.file_name or f"video_{message.id}.mp4",
                    'mime_type': message.video.mime_type or "video/mp4",
                    'file_size': message.video.file_size,
                    'duration': message.video.duration,
                    'width': message.video.width,
                    'height': message.video.height,
                    'type': 'video'
                }
            elif message.audio:
                file_info = {
                    'file_id': message.audio.file_id,
                    'file_unique_id': message.audio.file_unique_id,
                    'file_name': message.audio.file_name or f"audio_{message.id}.mp3",
                    'mime_type': message.audio.mime_type or "audio/mpeg",
                    'file_size': message.audio.file_size,
                    'duration': message.audio.duration,
                    'performer': message.audio.performer,
                    'title': message.audio.title,
                    'type': 'audio'
                }
            elif message.photo:
                # Tomar la foto de mayor resolución
                photo = message.photo[-1]
                file_info = {
                    'file_id': photo.file_id,
                    'file_unique_id': photo.file_unique_id,
                    'file_name': f"photo_{message.id}.jpg",
                    'mime_type': "image/jpeg",
                    'file_size': photo.file_size,
                    'width': photo.width,
                    'height': photo.height,
                    'type': 'photo'
                }
            elif message.voice:
                file_info = {
                    'file_id': message.voice.file_id,
                    'file_unique_id': message.voice.file_unique_id,
                    'file_name': f"voice_{message.id}.ogg",
                    'mime_type': "audio/ogg",
                    'file_size': message.voice.file_size,
                    'duration': message.voice.duration,
                    'type': 'voice'
                }
            elif message.sticker:
                file_info = {
                    'file_id': message.sticker.file_id,
                    'file_unique_id': message.sticker.file_unique_id,
                    'emoji': message.sticker.emoji,
                    'set_name': message.sticker.set_name,
                    'is_animated': message.sticker.is_animated,
                    'is_video': message.sticker.is_video,
                    'type': 'sticker'
                }
            
            return file_info if file_info else None
            
        except Exception as e:
            logger.error(f"Error extrayendo info de archivo: {e}")
            return None
    
    async def delete_file_reference(self, file_record):
        """Elimina referencia de archivo (opcional)"""
        try:
            if 'storage_msg_id' in file_record:
                await self.client.delete_messages(
                    chat_id=self.storage_channel_id,
                    message_ids=file_record['storage_msg_id']
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error eliminando referencia: {e}")
            return False
    
    async def cleanup_old_metadata(self, days_old=30):
        """Limpia metadatos antiguos"""
        try:
            deleted = 0
            cutoff_time = time.time() - (days_old * 24 * 3600)
            
            async for message in self.client.get_chat_history(self.db_channel_id, limit=100):
                if message.text and "📁 METADATA |" in message.text:
                    # Extraer timestamp del texto
                    import re
                    match = re.search(r'(\d{8}_\d{6})', message.text)
                    if match:
                        timestamp_str = match.group(1)
                        try:
                            msg_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                            if msg_date.timestamp() < cutoff_time:
                                # Eliminar mensaje y sus respuestas
                                await self.client.delete_messages(
                                    chat_id=self.db_channel_id,
                                    message_ids=message.id
                                )
                                deleted += 1
                        except:
                            pass
            
            logger.info(f"🧹 Metadata antigua limpiada: {deleted} registros")
            return deleted
            
        except Exception as e:
            logger.error(f"Error en limpieza: {e}")
            return 0

# Instancia global
telegram_storage = None

async def initialize_telegram_storage(client):
    """Inicializa el almacenamiento en Telegram"""
    global telegram_storage
    telegram_storage = TelegramStorage(client)
    
    # Verificar conexión a los canales
    try:
        db_chat = await client.get_chat(int(DB_CHANNEL_ID))
        storage_chat = await client.get_chat(int(STORAGE_CHANNEL_ID))
        
        logger.info(f"✅ Almacenamiento Telegram inicializado")
        logger.info(f"   📁 DB Channel: {db_chat.title}")
        logger.info(f"   📦 Storage Channel: {storage_chat.title}")
        
        return telegram_storage
    except Exception as e:
        logger.error(f"❌ Error conectando a canales: {e}")
        return None