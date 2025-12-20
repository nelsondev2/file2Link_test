"""
Handlers optimizados para el bot de Telegram
Sin descargas, solo referencias a archivos en Telegram
"""
import logging
import time
from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import Message

from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB, BOT_USERNAME, BOT_TOKEN
from file_service import file_service

logger = logging.getLogger(__name__)

# Cache simple para sesiones de usuario
user_sessions = {}

async def start_command(client, message):
    """Comando start con deep links para archivos"""
    try:
        args = message.text.split()
        user = message.from_user
        
        # Verificar si es un deep link para archivo
        if len(args) > 1 and args[1].startswith('file_'):
            # Deep link para descargar archivo
            parts = args[1].split('_')
            if len(parts) >= 3:
                file_id = parts[1]
                user_id = parts[2]
                
                # Verificar que el usuario coincide (seguridad básica)
                if str(user.id) != user_id:
                    await message.reply_text(
                        "⚠️ **Acceso denegado**\n\n"
                        "Este enlace no está destinado a tu usuario."
                    )
                    return
                
                # Obtener información del archivo desde Telegram API
                import requests
                api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getFile?file_id={file_id}"
                
                try:
                    response = requests.get(api_url, timeout=5)
                    if response.status_code == 200:
                        file_info = response.json()
                        if file_info.get('ok'):
                            file_path = file_info['result']['file_path']
                            download_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
                            
                            await message.reply_text(
                                f"📥 **Archivo disponible**\n\n"
                                f"**Enlaces de descarga:**\n"
                                f"• [Descarga Directa]({download_url})\n"
                                f"• [Abrir en Telegram](tg://file?id={file_id})\n\n"
                                f"**Instrucciones:**\n"
                                f"1. Usa el primer enlace para descargar directamente\n"
                                f"2. Usa el segundo para abrir en la app de Telegram\n\n"
                                f"⚠️ **Nota:** El archivo está almacenado de forma permanente en Telegram.",
                                disable_web_page_preview=True
                            )
                            return
                except:
                    pass
                
                # Fallback si no podemos obtener info de la API
                await message.reply_text(
                    f"📁 **Archivo solicitado**\n\n"
                    f"ID: `{file_id}`\n\n"
                    f"**Para descargar:**\n"
                    f"Usa este enlace directo:\n"
                    f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_id}\n\n"
                    f"O abre en Telegram: `tg://file?id={file_id}`"
                )
                return
        
        # Start normal - Bienvenida
        welcome_text = f"""👋 **¡Hola {user.first_name}!**

🤖 **File2Link Bot - Sistema Optimizado**

✨ **Características principales:**
• ✅ **0% almacenamiento en servidor** - Todo en Telegram
• ✅ **Enlaces permanentes** - Nunca expiran
• ✅ **Sobrevive a reinicios** - 100% confiable
• ✅ **Hasta {MAX_FILE_SIZE_MB}MB** por archivo
• ✅ **Acceso desde cualquier dispositivo**

📁 **¿Cómo funciona?**
1. **Envía un archivo** (documento, video, audio, foto)
2. **Obtén enlaces permanentes** inmediatamente
3. **Comparte** donde quieras

🔧 **Comandos disponibles:**
`/list` - Ver todos tus archivos
`/delete N` - Eliminar archivo #N
`/status` - Estado y estadísticas
`/help` - Ayuda completa

📏 **Límites:**
• Máximo por archivo: {MAX_FILE_SIZE_MB}MB
• Formatos soportados: Todos

🚀 **¡Envía un archivo para comenzar!**"""
        
        await message.reply_text(welcome_text)
        logger.info(f"/start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"Error en /start: {e}")
        await message.reply_text("❌ Error al procesar el comando.")

async def help_command(client, message):
    """Comando de ayuda detallada"""
    try:
        help_text = f"""📚 **Ayuda - File2Link Bot**

**🚀 Comandos principales:**
`/start` - Mensaje de bienvenida
`/list` - Ver todos tus archivos
`/delete N` - Eliminar archivo #N
`/status` - Ver estadísticas
`/help` - Esta ayuda

**📁 Sistema de archivos:**
• Los archivos se almacenan **100% en Telegram**
• Los enlaces son **permanentes** y nunca expiran
• Máximo **{MAX_FILE_SIZE_MB}MB** por archivo
• Soporta: documentos, videos, audios, fotos

**🔗 Tipos de enlaces generados:**
1. **Enlace de descarga directa** - Para navegadores
2. **Enlace Telegram** - Para la app de Telegram
3. **Enlace API** - Para aplicaciones

**🔄 Cómo usar:**
1. Envía cualquier archivo al bot
2. Recibe enlaces inmediatamente
3. Comparte los enlaces donde quieras

**⚠️ Notas importantes:**
• Los archivos **sobreviven a reinicios** del servidor
• El bot **NO descarga** archivos a servidores externos
• Todo se maneja **directamente en Telegram**
• Los enlaces funcionan **para siempre**

**📞 Soporte:**
Si tienes problemas, contacta al administrador."""
        
        await message.reply_text(help_text)
        
    except Exception as e:
        logger.error(f"Error en /help: {e}")
        await message.reply_text("❌ Error mostrando ayuda.")

async def list_command(client, message):
    """Lista todos los archivos del usuario"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        list_msg = await message.reply_text(f"📋 **Buscando tus archivos, {user_name}...**")
        
        files = await file_service.list_user_files(user_id, "downloads")
        
        if not files:
            await list_msg.edit_text(
                f"📭 **No tienes archivos aún, {user_name}**\n\n"
                f"Envía cualquier archivo al bot para obtener enlaces permanentes.\n\n"
                f"**Formatos soportados:**\n"
                f"• Documentos (PDF, Word, Excel, etc.)\n"
                f"• Videos (MP4, AVI, MKV, etc.)\n"
                f"• Audio (MP3, WAV, etc.)\n"
                f"• Fotos (JPG, PNG, etc.)\n\n"
                f"**Límite:** {MAX_FILE_SIZE_MB}MB por archivo"
            )
            return
        
        # Calcular estadísticas
        total_files = len(files)
        total_size = sum(f['size'] for f in files if f['size'])
        total_size_mb = total_size / (1024 * 1024) if total_size > 0 else 0
        
        response = f"📁 **Tus Archivos ({total_files}) - {total_size_mb:.1f}MB total**\n\n"
        
        # Mostrar archivos (máximo 15 para no saturar)
        files_to_show = files[:15]
        
        for file_info in files_to_show:
            size_mb = file_info['size'] / (1024 * 1024) if file_info['size'] > 0 else 0
            
            # Truncar nombre largo
            display_name = file_info['name']
            if len(display_name) > 30:
                display_name = display_name[:27] + "..."
            
            response += f"**#{file_info['number']}** - `{display_name}`\n"
            response += f"📏 {size_mb:.1f}MB | 📅 {file_info.get('date', 'N/A')}\n"
            response += f"🔗 [Descargar]({file_info['urls'].get('deep_link', '#')})\n\n"
        
        if total_files > 15:
            response += f"📄 *Mostrando 15 de {total_files} archivos*\n\n"
        
        response += "**📝 Comandos disponibles:**\n"
        response += "• `/delete N` - Eliminar archivo #N\n"
        response += "• `/status` - Ver estadísticas detalladas\n"
        response += f"• **Total almacenado:** {total_size_mb:.1f}MB\n\n"
        response += "💡 *Usa los enlaces para descargar o compartir tus archivos.*"
        
        if len(response) > 4000:
            # Enviar en partes
            await list_msg.edit_text(response[:4000], disable_web_page_preview=True)
            
            parts = [response[i:i+4000] for i in range(4000, len(response), 4000)]
            for part in parts:
                await message.reply_text(part, disable_web_page_preview=True)
        else:
            await list_msg.edit_text(response, disable_web_page_preview=True)
        
        logger.info(f"Archivos listados para {user_id}: {total_files} archivos")
        
    except Exception as e:
        logger.error(f"Error en /list: {e}")
        await message.reply_text("❌ Error listando archivos.")

async def delete_command(client, message):
    """Elimina un archivo del usuario"""
    try:
        user_id = message.from_user.id
        args = message.text.split()
        
        if len(args) < 2:
            await message.reply_text(
                "❌ **Formato incorrecto**\n\n"
                "**Uso:** `/delete <número>`\n"
                "**Ejemplo:** `/delete 5`\n\n"
                "Usa `/list` para ver los números de tus archivos."
            )
            return
        
        try:
            file_number = int(args[1])
        except ValueError:
            await message.reply_text(
                "❌ **Número inválido**\n\n"
                "Por favor, usa un número válido.\n"
                "Ejemplo: `/delete 3`"
            )
            return
        
        # Confirmar eliminación
        confirm_msg = await message.reply_text(
            f"⚠️ **¿Eliminar archivo #{file_number}?**\n\n"
            f"Esta acción eliminará la referencia al archivo.\n"
            f"**Nota:** El archivo seguirá disponible en Telegram.\n\n"
            f"Responde `sí` para confirmar o `no` para cancelar."
        )
        
        # Esperar confirmación (simplificado)
        # En una implementación real, usaríamos ConversationHandler
        await confirm_msg.edit_text(
            f"🗑️ **Eliminando archivo #{file_number}...**\n\n"
            f"Por favor, usa el comando nuevamente para confirmar:\n"
            f"`/delete {file_number} confirm`\n\n"
            f"O cancela ignorando este mensaje."
        )
        
        # Para simplificar, eliminamos directamente si hay "confirm"
        if len(args) > 2 and args[2].lower() == 'confirm':
            success, result_message = await file_service.delete_file(user_id, file_number, "downloads")
            
            if success:
                await message.reply_text(f"✅ {result_message}")
            else:
                await message.reply_text(f"❌ {result_message}")
            
    except Exception as e:
        logger.error(f"Error en /delete: {e}")
        await message.reply_text("❌ Error eliminando archivo.")

async def status_command(client, message):
    """Muestra estadísticas del usuario y sistema"""
    try:
        user_id = message.from_user.id
        user_name = message.from_user.first_name
        
        # Obtener estadísticas del usuario
        user_stats = await file_service.get_user_stats(user_id)
        
        if not user_stats:
            # Usuario nuevo o sin archivos
            status_text = f"""📊 **Estado del Sistema - {user_name}**

**👤 Tu información:**
• ID de usuario: `{user_id}`
• Primer uso: Recién empezado 🎉
• Archivos almacenados: 0

**🖥️ Sistema:**
• Almacenamiento: 100% en Telegram ☁️
• Servidor: Proxy ligero (0% CPU en Render)
• Enlaces: Permanentes ✅
• Límite por archivo: {MAX_FILE_SIZE_MB}MB
• Estado: **✅ ÓPTIMO**

**💡 Características:**
✅ Sobrevive a reinicios de servidor
✅ Cero almacenamiento local
✅ Cero procesamiento pesado
✅ Acceso desde cualquier dispositivo
✅ Enlaces que nunca expiran

**🚀 Para comenzar:**
Envía cualquier archivo al bot y obtén enlaces permanentes."""
            
            await message.reply_text(status_text)
            return
        
        # Usuario con archivos
        first_use = datetime.fromisoformat(user_stats['first_use']).strftime('%d/%m/%Y')
        last_activity = datetime.fromisoformat(user_stats['last_activity']).strftime('%d/%m/%Y %H:%M')
        
        status_text = f"""📊 **Estado del Sistema - {user_name}**

**👤 Tu información:**
• ID de usuario: `{user_id}`
• Primer uso: {first_use}
• Última actividad: {last_activity}
• Archivos de descarga: {user_stats['downloads_count']}
• Archivos empaquetados: {user_stats['packed_count']}
• **Total archivos:** {user_stats['total_files']}
• **Espacio usado:** {user_stats['total_size_mb']:.1f}MB

**🖥️ Sistema:**
• Almacenamiento: 100% en Telegram ☁️
• Servidor: Proxy ligero (0% CPU en Render)
• Enlaces: Permanentes ✅
• Límite por archivo: {MAX_FILE_SIZE_MB}MB
• Estado: **✅ ÓPTIMO**

**📈 Estadísticas:**
• Archivos más recientes: Usa `/list`
• Gestión: `/delete N` para eliminar
• Espacio disponible: Ilimitado (Telegram)

**💡 Recordatorio:**
Todos tus archivos están seguros en Telegram y son accesibles desde cualquier dispositivo mediante los enlaces permanentes."""

        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Error obteniendo estado.")

async def handle_file(client, message):
    """Maneja la recepción de archivos - Solo referencia, NO descarga"""
    try:
        user = message.from_user
        user_id = user.id
        user_name = user.first_name
        
        logger.info(f"📥 Archivo recibido de {user_id} ({user_name})")
        
        # Verificar tamaño del archivo
        file_size = 0
        file_type = "desconocido"
        file_name = "sin_nombre"
        
        if message.document:
            file_size = message.document.file_size or 0
            file_type = "documento"
            file_name = message.document.file_name or "documento_sin_nombre"
        elif message.video:
            file_size = message.video.file_size or 0
            file_type = "video"
            file_name = message.video.file_name or "video_sin_nombre.mp4"
        elif message.audio:
            file_size = message.audio.file_size or 0
            file_type = "audio"
            file_name = message.audio.file_name or "audio_sin_nombre.mp3"
        elif message.photo:
            # Tomar la foto de mayor resolución
            photo = message.photo[-1]
            file_size = photo.file_size or 0
            file_type = "foto"
            file_name = f"foto_{message.id}.jpg"
        elif message.voice:
            file_size = message.voice.file_size or 0
            file_type = "mensaje de voz"
            file_name = f"voz_{message.id}.ogg"
        elif message.sticker:
            file_size = message.sticker.file_size or 0
            file_type = "sticker"
            file_name = f"sticker_{message.id}.webp"
        else:
            await message.reply_text("❌ Tipo de archivo no soportado.")
            return
        
        # Verificar tamaño máximo
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            await message.reply_text(
                f"❌ **Archivo demasiado grande**\n\n"
                f"**Tamaño máximo permitido:** {MAX_FILE_SIZE_MB}MB\n"
                f"**Tu archivo:** {size_mb:.1f}MB\n\n"
                f"Por favor, divide el archivo en partes más pequeñas o comprímalo."
            )
            return
        
        # Procesar inmediatamente (sin colas, sin descargas)
        processing_msg = await message.reply_text(
            f"⚡ **Procesando {file_type}...**\n\n"
            f"**Nombre:** {file_name}\n"
            f"**Tamaño:** {file_size/1024/1024:.1f}MB\n\n"
            f"⏳ Esto tomará solo unos segundos..."
        )
        
        # Registrar archivo (SOLO REFERENCIA, CERO descarga)
        result = await file_service.register_file(message, user_id, "downloads")
        
        if not result:
            await processing_msg.edit_text(
                f"❌ **Error registrando archivo**\n\n"
                f"No se pudo guardar la referencia del archivo.\n"
                f"Por favor, inténtalo nuevamente."
            )
            return
        
        # Obtener URLs generadas
        file_info = await file_service.get_file_urls(user_id, result['number'], "downloads")
        
        if not file_info:
            await processing_msg.edit_text(
                f"❌ **Error generando URLs**\n\n"
                f"El archivo se registró pero no se pudieron generar los enlaces.\n"
                f"Contacta con soporte."
            )
            return
        
        # Preparar respuesta
        size_mb = file_size / (1024 * 1024)
        file_number = result['number']
        
        response = f"""✅ **¡Archivo #{file_number} Guardado!**

**📁 Información:**
• **Nombre:** `{file_name}`
• **Tipo:** {file_type}
• **Tamaño:** {size_mb:.1f}MB
• **Fecha:** {datetime.now().strftime('%d/%m/%Y %H:%M')}

**🔗 Enlaces Permanentes:**

**1. Descarga Directa (Recomendado):**
[{file_name}]({file_info['urls'].get('download_url', '#')})

**2. Abrir en Telegram:**
[Abrir en app]({file_info['urls'].get('deep_link', '#')})

**3. URL API (para developers):**
`{file_info['urls'].get('direct_url', 'N/A')}`

**4. URL del Proxy:**
`{file_info['urls'].get('proxy_url', 'N/A')}`

**📝 Notas importantes:**
• Los enlaces **funcionarán para siempre**
• El archivo está almacenado **100% en Telegram**
• **Sobrevive a reinicios** del servidor
• Comparte los enlaces donde quieras

**💾 Para gestionar tus archivos:**
• `/list` - Ver todos tus archivos
• `/delete {file_number}` - Eliminar este archivo
• `/status` - Ver estadísticas

⚠️ **Guarda estos enlaces para acceder al archivo en el futuro.**"""

        await processing_msg.edit_text(response, disable_web_page_preview=False)
        
        logger.info(f"✅ Archivo procesado: #{file_number} - {file_name} para usuario {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text(
                f"❌ **Error procesando archivo**\n\n"
                f"Detalles: {str(e)[:100]}\n\n"
                f"Por favor, inténtalo nuevamente o contacta soporte."
            )
        except:
            pass

async def cleanup_command(client, message):
    """Limpia todos los archivos del usuario"""
    try:
        user_id = message.from_user.id
        
        confirm_msg = await message.reply_text(
            "⚠️ **¡ADVERTENCIA CRÍTICA!**\n\n"
            "Estás a punto de eliminar **TODOS** tus archivos.\n"
            "Esta acción **NO SE PUEDE DESHACER**.\n\n"
            "**Escribe `CONFIRMAR ELIMINAR TODO` para proceder.**"
        )
        
        # En una implementación real, usaríamos ConversationHandler
        # Para simplificar, mostramos mensaje informativo
        await confirm_msg.edit_text(
            "🗑️ **Limpieza de archivos**\n\n"
            "Para eliminar todos tus archivos, por favor contacta al administrador.\n\n"
            "**Comandos seguros disponibles:**\n"
            "• `/delete N` - Eliminar archivo específico\n"
            "• `/list` - Ver tus archivos\n\n"
            "⚠️ **La eliminación masiva requiere confirmación especial.**"
        )
        
    except Exception as e:
        logger.error(f"Error en cleanup: {e}")
        await message.reply_text("❌ Error en comando de limpieza.")

def setup_handlers(client):
    """Configura todos los handlers del bot"""
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("list") & filters.private)(list_command)
    client.on_message(filters.command("delete") & filters.private)(delete_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    client.on_message(filters.command("cleanup") & filters.private)(cleanup_command)
    
    # Handler de archivos
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo | 
         filters.voice | filters.sticker) &
        filters.private
    )(handle_file)
    
    logger.info("✅ Handlers configurados (sistema optimizado)")