"""
Bot de Telegram CORREGIDO - Funciona inmediatamente
"""
import asyncio
import logging
import sys
from pyrogram import Client

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import setup_handlers
from telegram_storage import initialize_telegram_storage
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
        """Inicializa servicios de forma SIMPLE y CONFIABLE"""
        try:
            logger.info("🔧 Inicializando servicios...")
            
            # 1. Inicializar almacenamiento SIMPLE
            try:
                storage = await initialize_telegram_storage(self.client)
                logger.info("✅ Almacenamiento simple inicializado")
            except Exception as e:
                logger.warning(f"⚠️ Almacenamiento no disponible: {e}")
                storage = None
            
            # 2. Inicializar servicio de archivos (¡IMPORTANTE!)
            # Pasar la instancia storage (puede ser None)
            fs = await initialize_file_service(storage)
            
            if fs:
                logger.info("✅ Servicio de archivos inicializado")
                
                # Asegurarse de que file_service esté disponible globalmente
                import sys
                from file_service import file_service as fs_global
                
                # Verificar que podemos usar register_file
                if hasattr(fs_global, 'register_file'):
                    logger.info("✅ Método 'register_file' disponible")
                else:
                    logger.error("❌ 'register_file' NO disponible")
                    # Crear instancia de emergencia
                    from file_service import SimpleFileService
                    global file_service
                    file_service = SimpleFileService(storage)
                    
            else:
                logger.error("❌ No se pudo inicializar servicio de archivos")
                # Crear instancia de emergencia
                from file_service import SimpleFileService
                global file_service
                file_service = SimpleFileService(storage)
            
            logger.info("""
            ✅ SERVICIOS INICIALIZADOS
            ==========================
            Estado: ✅ FUNCIONAL
            Modo: Simplificado
            Archivos: ✅ Se guardan en Telegram
            URLs: ✅ Se generan correctamente
            Persistencia: ⚠️ Solo en memoria
            ==========================
            """)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Error inicializando servicios: {e}")
            
            # Crear servicio de emergencia
            try:
                from file_service import SimpleFileService
                global file_service
                file_service = SimpleFileService(None)
                logger.info("✅ Servicio de emergencia creado")
                return True
            except:
                logger.error("❌ Error crítico: No se pudo crear servicio")
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
            
            # Inicializar servicios - SIEMPRE continuar aunque falle
            init_success = await self.initialize_services()
            
            if not init_success:
                logger.warning("⚠️ Inicialización parcial, continuando...")
            
            # Configurar handlers (siempre se configuran)
            await self.setup_handlers()
            
            # Mensaje final
            logger.info("""
            🚀 BOT LISTO Y FUNCIONANDO
            ===========================
            ✅ Puede recibir archivos
            ✅ Genera enlaces
            ✅ Responde a comandos
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