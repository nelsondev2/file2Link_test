"""
Sistema de almacenamiento 100% en GRUPOS de Telegram - NO canales
"""
import logging
import time
import json
import tempfile
import os
from datetime import datetime
from pyrogram.types import Message
from pyrogram import Client

from config import DB_GROUP_ID, STORAGE_GROUP_ID, BOT_USERNAME, BOT_TOKEN, RENDER_DOMAIN

logger = logging.getLogger(__name__)

class TelegramGroupStorage:
    def __init__(self, client: Client):
        self.client = client
        self.db_group_id = self._parse_group_id(DB_GROUP_ID)
        self.storage_group_id = self._parse_group_id(STORAGE_GROUP_ID)
        self.bot_username = BOT_USERNAME
        
    def _parse_group_id(self, group_id_str):
        """Convierte ID de grupo de string a int, manejando diferentes formatos"""
        try:
            # Los grupos pueden tener IDs como: "-1234567890" o "1234567890"
            group_id = int(group_id_str)
            
            # Si es negativo, es un supergrupo (correcto)
            # Si es positivo, podría ser un grupo normal
            return group_id
            
        except Exception as e:
            logger.error(f"Error parseando group ID {group_id_str}: {e}")
            return None
    
    async def initialize(self):
        """Inicializa el almacenamiento verificando acceso a los grupos"""
        try:
            logger.info("🔍 Verificando acceso a grupos...")
            
            # Verificar DB Group
            if self.db_group_id:
                try:
                    db_group = await self.client.get_chat(self.db_group_id)
                    logger.info(f"✅ DB Group: {db_group.title} (ID: {self.db_group_id})")
                    
                    # Verificar si el bot es admin
                    me = await self.client.get_me()
                    member = await self.client.get_chat_member(self.db_group_id, me.id)
                    
                    if member.status in ["administrator", "creator"]:
                        logger.info("   👑 Bot es administrador del DB Group")
                        self.db_group_available = True
                    else:
                        logger.warning("   ⚠️ Bot NO es administrador del DB Group")
                        self.db_group_available = False
                        
                except Exception as e:
                    logger.error(f"❌ Error accediendo al DB Group: {e}")
                    self.db_group_available = False
            else:
                logger.warning("⚠️ DB_GROUP_ID no configurado")
                self.db_group_available = False
            
            # Verificar Storage Group
            if self.storage_group_id:
                try:
                    storage_group = await self.client.get_chat(self.storage_group_id)
                    logger.info(f"✅ Storage Group: {storage_group.title} (ID: {self.storage_group_id})")
                    
                    # Verificar si el bot es admin
                    me = await self.client.get_me()
                    member = await self.client.get_chat_member(self.storage_group_id, me.id)
                    
                    if member.status in ["administrator", "creator"]:
                        logger.info("   👑 Bot es administrador del Storage Group")
                        self.storage_group_available = True
                    else:
                        logger.warning("   ⚠️ Bot NO es administrador del Storage Group")
                        self.storage_group_available = False
                        
                except Exception as e:
                    logger.error(f"❌ Error accediendo al Storage Group: {e}")
                    self.storage_group_available = False
            else:
                logger.warning("⚠️ STORAGE_GROUP_ID no configurado")
                self.storage_group_available = False
            
            # Resumen
            if self.db_group_available and self.storage_group_available:
                logger.info("✅ Almacenamiento en grupos inicializado correctamente")
                return True
            else:
                logger.warning("⚠️ Almacenamiento parcialmente disponible")
                logger.warning("   Los datos pueden no persistir después de reinicios")
                return True  # Continuamos igual pero con advertencias
                
        except Exception as e:
            logger.error(f"❌ Error inicializando almacenamiento: {e}")
            # Modo fallback: seguir sin persistencia
            self.db_group_available = False
            self.storage_group_available = False
            return True  # IMPORTANTE: Retornar True para continuar
    
    async def save_metadata(self, user_id, data_type, data):
        """Guarda metadatos en el grupo de base de datos"""
        try:
            if not self.db_group_available:
                logger.warning("⚠️ DB Group no disponible, metadata no persistirá")
                return None
            
            key = f"user_{user_id}_{data_type}"
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            # Formato para metadata
            metadata_text = f"""📁 METADATA | {key} | {timestamp}
Usuario: {user_id}
Tipo: {data_type}
Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
            
            # Guardar como mensaje de texto en el grupo
            message = await self.client.send_message(
                chat_id=self.db_group_id,
                text=metadata_text
            )
            
            # Guardar datos como JSON en un archivo temporal
            data_json = json.dumps(data, ensure_ascii=False, indent=2)
            
            # Crear archivo temporal
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False, encoding='utf-8') as f:
                f.write(data_json)
                temp_file = f.name
            
            try:
                # Enviar como documento adjunto
                await self.client.send_document(
                    chat_id=self.db_group_id,
                    document=temp_file,
                    file_name=f"{key}_{timestamp}.json",
                    caption=f"📁 DATA | {key}",
                    reply_to_message_id=message.id
                )
            finally:
                # Limpiar archivo temporal
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
            
            logger.info(f"💾 Metadata guardada en grupo: {key} (msg {message.id})")
            return message.id
            
        except Exception as e:
            logger.error(f"Error guardando metadata en grupo: {e}")
            return None
    
    async def load_metadata(self, user_id, data_type):
        """Carga metadatos desde el grupo"""
        try:
            if not self.db_group_available:
                logger.warning("⚠️ DB Group no disponible, no se puede cargar metadata")
                return None
            
            key = f"user_{user_id}_{data_type}"
            
            # Buscar mensaje principal en el grupo
            async for message in self.client.search_messages(
                chat_id=self.db_group_id,
                query=f"📁 METADATA | {key}",
                limit=10
            ):
                if message.text and f"📁 METADATA | {key}" in message.text:
                    # Buscar mensaje con datos adjuntos
                    async for reply in self.client.get_chat_history(
                        chat_id=self.db_group_id,
                        limit=10,
                        offset_id=message.id - 1
                    ):
                        if reply.document and reply.caption and f"📁 DATA | {key}" in reply.caption:
                            # Descargar el documento JSON
                            temp_file = f"temp_{key}.json"
                            await self.client.download_media(reply, file_name=temp_file)
                            
                            try:
                                with open(temp_file, 'r', encoding='utf-8') as f:
                                    data = json.load(f)
                                return data
                            finally:
                                if os.path.exists(temp_file):
                                    os.unlink(temp_file)
            
            logger.info(f"📭 No hay metadata para {key} en el grupo")
            return None
            
        except Exception as e:
            logger.error(f"Error cargando metadata desde grupo: {e}")
            return None
    
    async def save_file_reference(self, message: Message, user_id, file_type="downloads"):
        """Guarda referencia a archivo en el grupo de storage (NO descarga el contenido)"""
        try:
            if not self.storage_group_available:
                logger.warning("⚠️ Storage Group no disponible, referencia no persistirá")
                return None
            
            # Obtener información del archivo
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
            
            # Guardar referencia en el grupo de storage
            storage_text = f"""📦 FILE_REF | {user_id} | {file_type}
Archivo: {file_info.get('file_name', 'unknown')}
Tamaño: {file_info.get('file_size', 0)} bytes
Tipo: {file_info.get('mime_type', 'unknown')}
Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
FileID: {file_info.get('file_id')}
UniqueID: {file_info.get('file_unique_id')}
"""
            
            storage_msg = await self.client.send_message(
                chat_id=self.storage_group_id,
                text=storage_text
            )
            
            file_record['storage_msg_id'] = storage_msg.id
            
            logger.info(f"✅ Archivo referenciado en grupo: {file_info.get('file_name')}")
            return file_record
            
        except Exception as e:
            logger.error(f"Error guardando referencia en grupo: {e}")
            return None
    
    async def get_file_urls(self, file_record):
        """Genera URLs para acceder al archivo"""
        try:
            file_id = file_record['file_info']['file_id']
            user_id = file_record['user_id']
            
            # 1. Deep link de Telegram
            deep_link = f"https://t.me/{self.bot_username.replace('@', '')}?start=file_{file_id}_{user_id}"
            
            # 2. URL de nuestro proxy
            proxy_url = f"{RENDER_DOMAIN}/file/{file_id}/{user_id}"
            
            # 3. URL directa a API de Telegram
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
        """Elimina referencia de archivo del grupo"""
        try:
            if not self.storage_group_available:
                return False
                
            if 'storage_msg_id' in file_record:
                await self.client.delete_messages(
                    chat_id=self.storage_group_id,
                    message_ids=file_record['storage_msg_id']
                )
                return True
            return False
        except Exception as e:
            logger.error(f"Error eliminando referencia: {e}")
            return False

# Instancia global
telegram_storage = None

async def initialize_telegram_storage(client):
    """Inicializa el almacenamiento en grupos de Telegram"""
    global telegram_storage
    telegram_storage = TelegramGroupStorage(client)
    
    # Inicializar y verificar acceso
    await telegram_storage.initialize()
    
    return telegram_storage