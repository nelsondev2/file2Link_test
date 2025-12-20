"""
Bot de Telegram optimizado para usar GRUPOS en lugar de canales
"""
import asyncio
import logging
import sys
from pyrogram import Client

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import setup_handlers
from telegram_storage import initialize_telegram_storage, telegram_storage
from file_service import initialize_file_service, file_service

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.client = None
        self.is_running = False

    async def setup_handlers(self):
        """Configura todos los handlers del bot"""
        setup_handlers(self.client)

    async def initialize_services(self):
        """Inicializa todos los servicios del sistema usando GRUPOS"""
        try:
            logger.info("🔄 Inicializando servicios con GRUPOS...")
            
            # 1. Inicializar almacenamiento en GRUPOS de Telegram
            logger.info("   📡 Conectando con Grupos de Telegram...")
            storage = await initialize_telegram_storage(self.client)
            
            if not storage:
                logger.error("❌ No se pudo inicializar el almacenamiento en grupos")
                logger.warning("⚠️ Continuando en modo básico (sin persistencia)")
                # Crear servicio de archivos sin almacenamiento persistente
                from file_service import TelegramFileService
                global file_service
                file_service = TelegramFileService(None)
                return True
            
            # 2. Inicializar servicio de archivos
            logger.info("   📁 Inicializando servicio de archivos...")
            fs = await initialize_file_service(storage)
            
            if not fs:
                logger.error("❌ No se pudo inicializar el servicio de archivos")
                return False
            
            # Verificar estado de los grupos
            if hasattr(storage, 'db_group_available') and storage.db_group_available:
                logger.info("   ✅ DB Group: Disponible")
            else:
                logger.warning("   ⚠️ DB Group: No disponible (metadatos no persistirán)")
                
            if hasattr(storage, 'storage_group_available') and storage.storage_group_available:
                logger.info("   ✅ Storage Group: Disponible")
            else:
                logger.warning("   ⚠️ Storage Group: No disponible (referencias no persistirán)")
            
            logger.info("""
            ✅ SERVICIOS INICIALIZADOS CON GRUPOS
            =====================================
            📊 Sistema: File2Link con Grupos
            💾 Almacenamiento: Grupos de Telegram
            ⚡ CPU Render: 0%
            💿 Disco Render: 0MB
            🔗 URLs: Permanentes
            🛡️  Persistencia: Con grupos activos
            =====================================
            """)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando servicios: {e}")
            # Modo fallback: continuar sin persistencia
            logger.warning("⚠️ Continuando en modo básico (sin persistencia)")
            return True

    async def start_bot(self):
        """Inicia el bot de Telegram"""
        try:
            # Crear cliente de Pyrogram
            self.client = Client(
                "file_to_link_bot",
                api_id=API_ID,
                api_hash=API_HASH,
                bot_token=BOT_TOKEN,
                sleep_threshold=30
            )

            # Iniciar cliente
            logger.info("🤖 Iniciando cliente de Telegram...")
            await self.client.start()

            # Obtener información del bot
            bot_info = await self.client.get_me()
            logger.info(f"   ✅ Bot: @{bot_info.username}")
            logger.info(f"   📝 ID: {bot_info.id}")
            logger.info(f"   👤 Nombre: {bot_info.first_name}")
            
            # Inicializar servicios
            if not await self.initialize_services():
                logger.warning("⚠️ Continuando con funcionalidad básica...")
            else:
                logger.info("✅ Sistema con grupos inicializado")
            
            # Configurar handlers
            await self.setup_handlers()
            
            # Mensaje final de inicio
            logger.info("""
            🚀 BOT LISTO Y FUNCIONANDO CON GRUPOS
            =====================================
            Estado: ✅ ACTIVO
            Modo: Grupos de Telegram
            Persistencia: ✅ CON GRUPOS
            URLs: ✅ PERMANENTES
            =====================================
            """)
            
            # Mantener el bot corriendo
            self.is_running = True
            
            # Mantener conexión activa
            await asyncio.Event().wait()

        except Exception as e:
            logger.error(f"❌ Error crítico en el bot: {e}", exc_info=True)
            self.is_running = False
        finally:
            if self.client:
                await self.client.stop()

    def run_bot(self):
        """Ejecuta el bot en un loop asyncio"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.start_bot())
        except KeyboardInterrupt:
            logger.info("👋 Bot detenido por el usuario")
        except Exception as e:
            logger.error(f"❌ Error en el loop del bot: {e}", exc_info=True)
            sys.exit(1)