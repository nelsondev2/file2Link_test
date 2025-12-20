"""
Handlers actualizados para usar file_service global
"""
import logging
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB, BOT_USERNAME, BOT_TOKEN
# Importar file_service global con alias para evitar conflictos
from file_service import file_service as global_file_service

logger = logging.getLogger(__name__)

# Cache simple para sesiones
user_sessions = {}

async def start_command(client, message):
    """Comando start"""
    try:
        user = message.from_user
        
        welcome_text = f"""👋 **¡Hola {user.first_name}!**

🤖 **File2Link Bot - Sistema Simplificado**

✨ **Características:**
• ✅ Recibe cualquier archivo
• ✅ Genera enlaces de descarga
• ✅ Fácil de usar
• ✅ Hasta {MAX_FILE_SIZE_MB}MB por archivo

📁 **¿Cómo funciona?**
1. **Envía un archivo** al bot
2. **Recibe enlaces** inmediatamente
3. **Comparte** donde quieras

🔧 **Comandos:**
`/list` - Ver tus archivos
`/delete N` - Eliminar archivo #N
`/status` - Estado del sistema
`/help` - Ayuda completa

🚀 **¡Envía un archivo para comenzar!**"""
        
        await message.reply_text(welcome_text)
        
    except Exception as e:
        logger.error(f"Error en /start: {e}")
        await message.reply_text("❌ Error al procesar el comando.")

async def handle_file(client, message):
    """Maneja la recepción de archivos - VERSIÓN SIMPLIFICADA"""
    try:
        user = message.from_user
        user_id = user.id
        
        logger.info(f"📥 Archivo recibido de {user_id}")
        
        # Verificar tamaño
        file_size = 0
        file_name = "archivo"
        
        if message.document:
            file_size = message.document.file_size or 0
            file_name = message.document.file_name or "documento"
        elif message.video:
            file_size = message.video.file_size or 0
            file_name = message.video.file_name or "video.mp4"
        elif message.audio:
            file_size = message.audio.file_size or 0
            file_name = message.audio.file_name or "audio.mp3"
        elif message.photo:
            photo = message.photo[-1]
            file_size = photo.file_size or 0
            file_name = f"foto_{message.id}.jpg"
        
        # Verificar tamaño máximo
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            await message.reply_text(
                f"❌ **Archivo demasiado grande**\n\n"
                f"Límite: {MAX_FILE_SIZE_MB}MB\n"
                f"Tu archivo: {size_mb:.1f}MB"
            )
            return
        
        # Procesar
        processing_msg = await message.reply_text(
            f"⚡ **Procesando archivo...**\n\n"
            f"**Nombre:** {file_name}\n"
            f"**Tamaño:** {file_size/1024/1024:.1f}MB"
        )
        
        # ¡IMPORTANTE! Usar global_file_service
        if global_file_service is None:
            await processing_msg.edit_text("❌ Error: Servicio no disponible")
            return
        
        # Registrar archivo
        result = await global_file_service.register_file(message, user_id, "downloads")
        
        if not result:
            await processing_msg.edit_text("❌ Error registrando archivo")
            return
        
        # Obtener URLs
        file_info = await global_file_service.get_file_urls(user_id, result['number'], "downloads")
        
        if not file_info:
            await processing_msg.edit_text("❌ Error generando URLs")
            return
        
        # Preparar respuesta
        response = f"""✅ **¡Archivo #{result['number']} Procesado!**

**📁 Información:**
• **Nombre:** `{file_name}`
• **Tamaño:** {file_size/1024/1024:.1f}MB

**🔗 Enlaces de Descarga:**

**1. Descarga Directa:**
[{file_name}]({file_info['urls'].get('download_url', '#')})

**2. Abrir en Telegram:**
[Abrir en app]({file_info['urls'].get('deep_link', '#')})

**💾 Para gestionar:**
• `/list` - Ver todos tus archivos
• `/delete {result['number']}` - Eliminar este archivo

⚠️ **Nota:** Los enlaces funcionan mientras el bot esté activo."""

        await processing_msg.edit_text(response, disable_web_page_preview=False)
        
        logger.info(f"✅ Archivo procesado: #{result['number']} para {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text(f"❌ Error: {str(e)[:100]}")
        except:
            pass

async def list_command(client, message):
    """Lista archivos del usuario"""
    try:
        user_id = message.from_user.id
        
        list_msg = await message.reply_text("📋 **Buscando tus archivos...**")
        
        # Usar global_file_service
        if global_file_service is None:
            await list_msg.edit_text("❌ Servicio no disponible")
            return
        
        files = await global_file_service.list_user_files(user_id, "downloads")
        
        if not files:
            await list_msg.edit_text(
                "📭 **No tienes archivos aún**\n\n"
                "Envía cualquier archivo al bot para comenzar."
            )
            return
        
        response = f"📁 **Tus Archivos ({len(files)})**\n\n"
        
        for file_info in files[:10]:  # Mostrar máximo 10
            size_mb = file_info['size'] / (1024 * 1024) if file_info['size'] > 0 else 0
            display_name = file_info['name'][:30] + "..." if len(file_info['name']) > 30 else file_info['name']
            
            response += f"**#{file_info['number']}** - `{display_name}`\n"
            response += f"📏 {size_mb:.1f}MB | 🔗 [Descargar]({file_info['urls'].get('deep_link', '#')})\n\n"
        
        if len(files) > 10:
            response += f"📄 *Mostrando 10 de {len(files)} archivos*\n\n"
        
        response += "**Comandos:**\n"
        response += "• `/delete N` - Eliminar archivo #N\n"
        
        await list_msg.edit_text(response, disable_web_page_preview=True)
        
    except Exception as e:
        logger.error(f"Error en /list: {e}")
        await message.reply_text("❌ Error listando archivos.")

async def delete_command(client, message):
    """Elimina un archivo"""
    try:
        args = message.text.split()
        if len(args) < 2:
            await message.reply_text("Uso: `/delete <número>`")
            return
        
        file_number = int(args[1])
        user_id = message.from_user.id
        
        # Usar global_file_service
        if global_file_service is None:
            await message.reply_text("❌ Servicio no disponible")
            return
        
        success, msg = await global_file_service.delete_file(user_id, file_number, "downloads")
        
        await message.reply_text(msg)
            
    except Exception as e:
        logger.error(f"Error en /delete: {e}")
        await message.reply_text("❌ Error eliminando archivo.")

async def status_command(client, message):
    """Estado del sistema"""
    try:
        user_id = message.from_user.id
        
        # Usar global_file_service
        files = []
        if global_file_service:
            files = await global_file_service.list_user_files(user_id, "downloads")
        
        status_text = f"""📊 **Estado del Sistema**

**👤 Tu información:**
• Archivos activos: {len(files)}
• ID de usuario: `{user_id}`

**🖥️ Sistema:**
• Estado: ✅ ACTIVO
• Límite por archivo: {MAX_FILE_SIZE_MB}MB
• Bot: @{BOT_USERNAME}

**💡 Características:**
✅ Recibe cualquier archivo
✅ Genera enlaces de descarga
✅ Fácil de usar
✅ Sin configuración compleja

**Para comenzar:** Envía cualquier archivo al bot."""
        
        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Error obteniendo estado.")

async def help_command(client, message):
    """Comando de ayuda"""
    try:
        help_text = f"""📚 **Ayuda - File2Link Bot**

**🚀 Comandos:**
`/start` - Mensaje de bienvenida
`/list` - Ver tus archivos
`/delete N` - Eliminar archivo #N
`/status` - Ver estado
`/help` - Esta ayuda

**📁 Cómo usar:**
1. Envía cualquier archivo al bot
2. Recibe enlaces de descarga
3. Comparte los enlaces

**📏 Límites:**
• Máximo {MAX_FILE_SIZE_MB}MB por archivo
• Soporta: documentos, videos, audios, fotos

**⚠️ Notas:**
• Los enlaces funcionan mientras el bot esté activo
• Los archivos se guardan en Telegram
• Usa `/delete` para eliminar archivos que ya no necesites"""
        
        await message.reply_text(help_text)
        
    except Exception as e:
        logger.error(f"Error en /help: {e}")
        await message.reply_text("❌ Error mostrando ayuda.")

def setup_handlers(client):
    """Configura todos los handlers"""
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("list") & filters.private)(list_command)
    client.on_message(filters.command("delete") & filters.private)(delete_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    
    # Handler de archivos
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)
    
    logger.info("✅ Handlers configurados (sistema simplificado)")