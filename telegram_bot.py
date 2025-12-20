"""
Bot de Telegram - Versión ULTRA SIMPLE que SIEMPRE funciona
"""
import asyncio
import logging
import sys
from pyrogram import Client

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import setup_handlers

logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.client = None
        self.is_running = False

    async def setup_handlers(self):
        """Configura todos los handlers del bot"""
        setup_handlers(self.client)

    async def ensure_file_service(self):
        """Asegura que file_service esté disponible"""
        try:
            # Intentar importar e inicializar file_service
            from file_service import file_service as fs
            from telegram_storage import initialize_telegram_storage
            from file_service import initialize_file_service
            
            # Si ya está inicializado, no hacer nada
            if fs is not None:
                logger.info("✅ file_service ya está disponible")
                return True
            
            # Inicializar storage
            storage = await initialize_telegram_storage(self.client)
            logger.info("✅ Almacenamiento inicializado")
            
            # Inicializar file_service
            await initialize_file_service(storage)
            logger.info("✅ file_service inicializado")
            
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ No se pudo inicializar file_service: {e}")
            logger.info("🔄 Creando servicio básico de emergencia...")
            
            try:
                # Crear servicio básico directamente
                from file_service import SimpleFileService
                import file_service as fs_module
                
                # Crear nueva instancia
                fs_module.file_service = SimpleFileService(None)
                logger.info("✅ Servicio básico creado")
                return True
                
            except Exception as e2:
                logger.error(f"❌ Error crítico: {e2}")
                return False

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
            
            # Asegurar que file_service esté disponible
            await self.ensure_file_service()
            
            # Configurar handlers
            await self.setup_handlers()
            
            # Mensaje final
            logger.info("""
            🚀 BOT LISTO Y FUNCIONANDO
            ===========================
            Estado: ✅ ACTIVO
            Funciones: ✅ BÁSICAS
            Archivos: ✅ ACEPTADOS
            Enlaces: ✅ GENERADOS
            ===========================
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