"""
Almacenamiento simplificado que funciona con o sin grupos
"""
import logging
import time
import json
from datetime import datetime
from pyrogram.types import Message
from pyrogram import Client

from config import BOT_USERNAME, BOT_TOKEN, RENDER_DOMAIN

logger = logging.getLogger(__name__)

class SimpleTelegramStorage:
    def __init__(self, client: Client):
        self.client = client
        self.bot_username = BOT_USERNAME.replace('@', '') if BOT_USERNAME else "test_nelsonfile2linkbot"
        
    async def initialize(self):
        """Inicialización simplificada - siempre retorna True"""
        logger.info("✅ Almacenamiento simplificado inicializado")
        logger.info("📝 Nota: Los archivos se guardan en Telegram, metadatos en memoria")
        return True
    
    async def save_file_reference(self, message: Message, user_id, file_type="downloads"):
        """Guarda referencia a archivo usando solo Telegram (sin grupos externos)"""
        try:
            # Obtener información del archivo
            file_info = self._extract_file_info(message)
            if not file_info:
                return None
            
            # Crear registro básico
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
            
            logger.info(f"✅ Referencia de archivo creada: {file_info.get('file_name')}")
            return file_record
            
        except Exception as e:
            logger.error(f"Error creando referencia: {e}")
            return None
    
    async def get_file_urls(self, file_record):
        """Genera URLs para el archivo"""
        try:
            file_id = file_record['file_info']['file_id']
            user_id = file_record['user_id']
            
            # URL principal
            deep_link = f"https://t.me/{self.bot_username}?start=file_{file_id}_{user_id}"
            
            # URL de descarga
            download_url = f"{RENDER_DOMAIN}/download/{file_id}"
            
            return {
                'deep_link': deep_link,
                'download_url': download_url,
                'file_id': file_id,
                'telegram_url': f"tg://file?id={file_id}"
            }
            
        except Exception as e:
            logger.error(f"Error generando URLs: {e}")
            return None
    
    def _extract_file_info(self, message: Message):
        """Extrae información del archivo"""
        try:
            if message.document:
                return {
                    'file_id': message.document.file_id,
                    'file_unique_id': message.document.file_unique_id,
                    'file_name': message.document.file_name,
                    'mime_type': message.document.mime_type,
                    'file_size': message.document.file_size,
                    'type': 'document'
                }
            elif message.video:
                return {
                    'file_id': message.video.file_id,
                    'file_unique_id': message.video.file_unique_id,
                    'file_name': message.video.file_name or f"video_{message.id}.mp4",
                    'mime_type': message.video.mime_type or "video/mp4",
                    'file_size': message.video.file_size,
                    'type': 'video'
                }
            elif message.audio:
                return {
                    'file_id': message.audio.file_id,
                    'file_unique_id': message.audio.file_unique_id,
                    'file_name': message.audio.file_name or f"audio_{message.id}.mp3",
                    'mime_type': message.audio.mime_type or "audio/mpeg",
                    'file_size': message.audio.file_size,
                    'type': 'audio'
                }
            elif message.photo:
                photo = message.photo[-1]
                return {
                    'file_id': photo.file_id,
                    'file_unique_id': photo.file_unique_id,
                    'file_name': f"photo_{message.id}.jpg",
                    'mime_type': "image/jpeg",
                    'file_size': photo.file_size,
                    'type': 'photo'
                }
            elif message.voice:
                return {
                    'file_id': message.voice.file_id,
                    'file_unique_id': message.voice.file_unique_id,
                    'file_name': f"voice_{message.id}.ogg",
                    'mime_type': "audio/ogg",
                    'file_size': message.voice.file_size,
                    'type': 'voice'
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error extrayendo info: {e}")
            return None

# Instancia global
telegram_storage = None

async def initialize_telegram_storage(client):
    """Inicializa almacenamiento simplificado"""
    global telegram_storage
    telegram_storage = SimpleTelegramStorage(client)
    await telegram_storage.initialize()
    return telegram_storage