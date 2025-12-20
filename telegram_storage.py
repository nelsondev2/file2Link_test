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
                logger.error("❌ No se pudo extraer información del archivo")
                return None
            
            # Obtener el nombre real del archivo
            original_name = self._get_original_filename(message)
            
            # Crear registro básico
            file_record = {
                'user_id': user_id,
                'file_type': file_type,
                'file_info': file_info,
                'timestamp': time.time(),
                'original_name': original_name,
                'message_id': message.id,
                'chat_id': message.chat.id if message.chat else user_id,
                'date': message.date.timestamp() if message.date else time.time()
            }
            
            logger.info(f"✅ Referencia de archivo creada: {original_name} ({file_info.get('file_size', 0)/1024/1024:.1f}MB)")
            return file_record
            
        except Exception as e:
            logger.error(f"Error creando referencia: {e}", exc_info=True)
            return None
    
    def _get_original_filename(self, message: Message):
        """Obtiene el nombre original del archivo del mensaje"""
        try:
            if message.document and message.document.file_name:
                return message.document.file_name
            elif message.video and message.video.file_name:
                return message.video.file_name
            elif message.audio and message.audio.file_name:
                return message.audio.file_name
            elif message.photo:
                return f"photo_{message.id}.jpg"
            elif message.voice:
                return f"voice_{message.id}.ogg"
            elif message.sticker:
                return f"sticker_{message.id}.webp"
            else:
                # Intentar extraer del caption
                if message.caption:
                    return message.caption[:50]
                else:
                    return f"archivo_{message.id}"
        except Exception as e:
            logger.error(f"Error obteniendo nombre original: {e}")
            return f"archivo_{message.id}"
    
    async def get_file_urls(self, file_record):
        """Genera URLs REALES para el archivo"""
        try:
            file_id = file_record['file_info']['file_id']
            user_id = file_record['user_id']
            
            # Obtener file_path REAL de Telegram API
            try:
                api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
                import requests
                response = requests.get(api_url, timeout=5)
                
                if response.status_code == 200:
                    file_data = response.json()
                    if file_data.get('ok'):
                        file_path = file_data['result']['file_path']
                        # URL REAL de descarga directa
                        real_download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                        
                        logger.info(f"✅ URL real obtenida para file_id: {file_id}")
                        
                        # URL principal
                        deep_link = f"https://t.me/{self.bot_username}?start=file_{file_id}_{user_id}"
                        
                        # URL de nuestro proxy
                        proxy_url = f"{RENDER_DOMAIN}/download/{file_id}"
                        
                        return {
                            'deep_link': deep_link,
                            'download_url': proxy_url,
                            'real_download_url': real_download_url,
                            'file_id': file_id,
                            'telegram_url': f"tg://file?id={file_id}",
                            'has_real_url': True
                        }
            except Exception as api_error:
                logger.warning(f"⚠️ No se pudo obtener URL real: {api_error}")
            
            # Fallback si no se puede obtener URL real
            deep_link = f"https://t.me/{self.bot_username}?start=file_{file_id}_{user_id}"
            download_url = f"{RENDER_DOMAIN}/download/{file_id}"
            
            return {
                'deep_link': deep_link,
                'download_url': download_url,
                'file_id': file_id,
                'telegram_url': f"tg://file?id={file_id}",
                'has_real_url': False
            }
            
        except Exception as e:
            logger.error(f"Error generando URLs: {e}", exc_info=True)
            return None
    
    def _extract_file_info(self, message: Message):
        """Extrae información COMPLETA del archivo"""
        try:
            file_info = {}
            
            if message.document:
                file_info = {
                    'file_id': message.document.file_id,
                    'file_unique_id': message.document.file_unique_id,
                    'file_name': message.document.file_name or f"document_{message.id}",
                    'mime_type': message.document.mime_type or "application/octet-stream",
                    'file_size': message.document.file_size or 0,
                    'type': 'document'
                }
                logger.info(f"📄 Documento: {file_info['file_name']} ({file_info['file_size']} bytes)")
                
            elif message.video:
                file_info = {
                    'file_id': message.video.file_id,
                    'file_unique_id': message.video.file_unique_id,
                    'file_name': message.video.file_name or f"video_{message.id}.mp4",
                    'mime_type': message.video.mime_type or "video/mp4",
                    'file_size': message.video.file_size or 0,
                    'duration': message.video.duration,
                    'width': message.video.width,
                    'height': message.video.height,
                    'type': 'video'
                }
                logger.info(f"🎥 Video: {file_info['file_name']} ({file_info['file_size']/1024/1024:.1f}MB)")
                
            elif message.audio:
                file_info = {
                    'file_id': message.audio.file_id,
                    'file_unique_id': message.audio.file_unique_id,
                    'file_name': message.audio.file_name or f"audio_{message.id}.mp3",
                    'mime_type': message.audio.mime_type or "audio/mpeg",
                    'file_size': message.audio.file_size or 0,
                    'duration': message.audio.duration,
                    'performer': message.audio.performer,
                    'title': message.audio.title,
                    'type': 'audio'
                }
                logger.info(f"🎵 Audio: {file_info['file_name']} ({file_info['file_size']/1024/1024:.1f}MB)")
                
            elif message.photo:
                # Tomar la foto de mayor resolución (la última)
                photo = message.photo[-1]
                file_info = {
                    'file_id': photo.file_id,
                    'file_unique_id': photo.file_unique_id,
                    'file_name': f"photo_{message.id}.jpg",
                    'mime_type': "image/jpeg",
                    'file_size': photo.file_size or 0,
                    'width': photo.width,
                    'height': photo.height,
                    'type': 'photo'
                }
                logger.info(f"🖼️ Foto: {file_info['file_name']} ({file_info['file_size']/1024/1024:.1f}MB)")
                
            elif message.voice:
                file_info = {
                    'file_id': message.voice.file_id,
                    'file_unique_id': message.voice.file_unique_id,
                    'file_name': f"voice_{message.id}.ogg",
                    'mime_type': "audio/ogg",
                    'file_size': message.voice.file_size or 0,
                    'duration': message.voice.duration,
                    'type': 'voice'
                }
                logger.info(f"🎤 Voz: {file_info['file_name']} ({file_info['file_size']/1024/1024:.1f}MB)")
                
            elif message.sticker:
                file_info = {
                    'file_id': message.sticker.file_id,
                    'file_unique_id': message.sticker.file_unique_id,
                    'file_name': f"sticker_{message.id}.webp",
                    'emoji': message.sticker.emoji,
                    'set_name': message.sticker.set_name,
                    'is_animated': message.sticker.is_animated,
                    'is_video': message.sticker.is_video,
                    'type': 'sticker'
                }
                logger.info(f"🖼️ Sticker: {file_info['file_name']}")
            
            else:
                logger.warning(f"⚠️ Tipo de mensaje no manejado: {message.media}")
                return None
            
            return file_info
            
        except Exception as e:
            logger.error(f"❌ Error extrayendo info: {e}", exc_info=True)
            return None

# Instancia global
telegram_storage = None

async def initialize_telegram_storage(client):
    """Inicializa almacenamiento simplificado"""
    global telegram_storage
    telegram_storage = SimpleTelegramStorage(client)
    await telegram_storage.initialize()
    return telegram_storage