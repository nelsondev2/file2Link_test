import asyncio
import logging
import sys
from contextlib import suppress
from typing import Optional

from pyrogram import Client, idle
from pyrogram.errors import RPCError

from config import API_ID, API_HASH, BOT_TOKEN
from telegram_handlers import setup_handlers

logger = logging.getLogger(__name__)


class TelegramBot:
    """Bot profesional con gestión de ciclo de vida y recuperación de errores"""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self.is_running = False
        self._shutdown_event = asyncio.Event()
        
    async def _create_client(self) -> Client:
        """Crea cliente Pyrogram con configuración optimizada"""
        return Client(
            name="nelson_file2link_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workdir="./session_data",
            sleep_threshold=30,  # Reducido para mejor respuesta
            max_concurrent_transmissions=2,  # Optimizado para Render
            workers=2,  # Workers limitados para bajos recursos
            plugins=dict(root="handlers"),
            in_memory=True  # Mejor para entornos efímeros
        )
    
    async def _setup_client(self) -> bool:
        """Configura el cliente con recuperación de errores"""
        max_retries = 3
        retry_delay = 5
        
        for attempt in range(max_retries):
            try:
                logger.info(f"Intentando crear cliente (intento {attempt + 1}/{max_retries})")
                self.client = await self._create_client()
                
                # Configurar handlers
                setup_handlers(self.client)
                
                # Conectar
                await self.client.start()
                
                # Verificar conexión
                bot_info = await self.client.get_me()
                logger.info(f"✅ Bot iniciado: @{bot_info.username} (ID: {bot_info.id})")
                
                return True
                
            except RPCError as e:
                logger.error(f"Error RPC en intento {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    logger.info(f"Reintentando en {retry_delay} segundos...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Backoff exponencial
                else:
                    logger.critical("No se pudo conectar después de todos los intentos")
                    return False
                    
            except Exception as e:
                logger.critical(f"Error crítico al iniciar bot: {e}", exc_info=True)
                return False
        
        return False
    
    async def _keep_alive(self):
        """Mantiene el bot vivo y monitorea conexión"""
        while self.is_running:
            try:
                # Verificar conexión periódicamente
                if self.client and self.client.is_connected:
                    await self.client.get_me()
                    logger.debug("✅ Conexión verificada")
                else:
                    logger.warning("⚠️ Conexión perdida, intentando reconectar...")
                    await self._reconnect()
                    
            except Exception as e:
                logger.error(f"Error en keep-alive: {e}")
                
            # Esperar antes de la siguiente verificación
            await asyncio.sleep(60)  # Verificar cada minuto
    
    async def _reconnect(self):
        """Reconexión automática con limpieza de estado"""
        try:
            if self.client:
                await self.client.stop()
                await asyncio.sleep(2)
            
            success = await self._setup_client()
            if success:
                logger.info("✅ Reconexión exitosa")
            else:
                logger.error("❌ No se pudo reconectar")
                
        except Exception as e:
            logger.error(f"Error en reconexión: {e}")
    
    async def start_bot(self):
        """Inicia el bot con gestión profesional del ciclo de vida"""
        try:
            logger.info("🚀 Iniciando bot de Telegram...")
            
            # Configurar cliente
            success = await self._setup_client()
            if not success:
                logger.critical("No se pudo iniciar el bot")
                return
            
            self.is_running = True
            
            # Iniciar tarea de keep-alive
            keep_alive_task = asyncio.create_task(self._keep_alive())
            
            # Esperar señal de apagado
            logger.info("🤖 Bot listo y respondiendo a comandos")
            await self._shutdown_event.wait()
            
            # Cancelar keep-alive
            keep_alive_task.cancel()
            with suppress(asyncio.CancelledError):
                await keep_alive_task
                
        except Exception as e:
            logger.critical(f"Error crítico en el bot: {e}", exc_info=True)
            self.is_running = False
            
        finally:
            await self._cleanup()
    
    async def _cleanup(self):
        """Limpieza profesional al apagar"""
        logger.info("🔽 Iniciando limpieza...")
        
        if self.client:
            try:
                await self.client.stop()
                logger.info("✅ Cliente Pyrogram detenido")
            except Exception as e:
                logger.error(f"Error deteniendo cliente: {e}")
        
        self.is_running = False
        logger.info("👋 Bot apagado correctamente")
    
    def run_bot(self):
        """Ejecuta el bot con gestión profesional de eventos"""
        try:
            # Configurar loop de eventos optimizado
            if sys.platform == 'win32':
                loop = asyncio.ProactorEventLoop()
                asyncio.set_event_loop(loop)
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Configurar manejo de señales
            try:
                loop.add_signal_handler(signal.SIGINT, lambda: asyncio.create_task(self.shutdown()))
                loop.add_signal_handler(signal.SIGTERM, lambda: asyncio.create_task(self.shutdown()))
            except (NotImplementedError, RuntimeError):
                pass  # Windows o ya en hilo
            
            # Ejecutar bot
            loop.run_until_complete(self.start_bot())
            
        except KeyboardInterrupt:
            logger.info("Apagado solicitado por usuario")
            loop.run_until_complete(self.shutdown())
            
        except Exception as e:
            logger.critical(f"Error en el loop del bot: {e}", exc_info=True)
            
        finally:
            # Limpiar loop
            if not loop.is_closed():
                loop.run_until_complete(loop.shutdown_asyncgens())
                loop.close()
    
    async def shutdown(self):
        """Apagado controlado del bot"""
        if self.is_running:
            logger.info("🔄 Apagando bot...")
            self._shutdown_event.set()