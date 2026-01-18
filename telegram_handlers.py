import os
import logging
import sys
import time
import asyncio
import concurrent.futures
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import fast_download_service
from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB, OWNER_ID
from database import db

logger = logging.getLogger(__name__)

# ===== SISTEMA DE SESIÓN POR USUARIO =====
user_sessions = {}
user_queues = {}
user_progress_msgs = {}
user_current_processing = {}
user_batch_totals = {}

def get_user_session(user_id):
    """Obtiene o crea la sesión del usuario"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'current_folder': 'downloads'}
    return user_sessions[user_id]

# ===== COMANDOS DE NAVEGACIÓN =====

async def start_command(client, message):
    """Maneja el comando /start - MEJORADO"""
    try:
        user = message.from_user
        
        # Registrar usuario en base de datos
        if not await db.is_user_exist(user.id):
            await db.add_user(user.id)
            logger.info(f"📝 Nuevo usuario registrado: {user.id} - {user.first_name}")
        
        welcome_text = f"""👋 **¡Bienvenido/a {user.first_name}!**

🤖 **File2Link Bot** - Sistema Avanzado de Gestión de Archivos

✨ **NUEVAS FUNCIONALIDADES:**
• 🎬 **Streaming en navegador** - Reproduce videos/audio online
• 📊 **Sistema de carpetas** - Organiza tus archivos
• 📦 **Empaquetado inteligente** - Crea ZIPs automáticamente
• 🔄 **Cola de procesamiento** - Sube múltiples archivos
• 🔒 **Nombres seguros** - Caracteres problemáticos eliminados

📁 **SISTEMA DE CARPETAS:**
`/cd downloads` - Tus archivos de descarga
`/cd packed` - Archivos empaquetados
`/list` - Ver archivos en carpeta actual

📄 **GESTIÓN DE ARCHIVOS:**
`/rename <número> <nuevo_nombre>`
`/delete <número>` - Eliminar archivo
`/clear` - Vaciar carpeta actual

📦 **EMPAQUETADO:**
`/pack` - Crear ZIP de downloads
`/pack <MB>` - Dividir en partes

🔄 **COLA DE DESCARGA:**
`/queue` - Ver archivos en cola
`/clearqueue` - Limpiar cola

🔍 **INFORMACIÓN:**
`/status` - Estado del sistema
`/help` - Ayuda completa

📏 **LÍMITES:**
• Tamaño máximo: {MAX_FILE_SIZE_MB} MB por archivo
• Formatos: Todos los soportados por Telegram
• Storage: Ilimitado (mientras haya espacio)

🚀 **¡Envía archivos o usa los comandos para comenzar!**"""

        await message.reply_text(welcome_text)
        logger.info(f"/start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"Error en /start: {e}")

async def help_command(client, message):
    """Maneja el comando /help - MEJORADO"""
    try:
        help_text = f"""📚 **AYUDA COMPLETA - File2Link Bot**

**📁 NAVEGACIÓN:**
`/cd downloads` - Carpeta de archivos descargados
`/cd packed` - Carpeta de archivos empaquetados  
`/cd` - Mostrar carpeta actual

**📄 GESTIÓN EN CARPETA:**
`/list [página]` - Listar archivos (10 por página)
`/rename N NUEVO_NOMBRE` - Renombrar archivo N
`/delete N` - Eliminar archivo N
`/clear` - Vaciar carpeta actual

**📦 EMPAQUETADO:**
`/pack` - Crear ZIP con todos los archivos de downloads
`/pack MB` - Crear ZIP y dividir en partes de MB
`/pack 100` - Ejemplo: partes de 100MB

**🔄 GESTIÓN DE COLA:**
`/queue` - Ver archivos en cola de procesamiento
`/clearqueue` - Limpiar cola de descarga

**🎬 STREAMING:**
• Los videos y audios tienen **URL de streaming**
• Se reproducen directamente en el navegador
• No requiere descarga para ver/escuchar

**🔍 INFORMACIÓN:**
`/status` - Estado del sistema y espacio usado
`/help` - Esta ayuda completa

**📏 LÍMITES:**
• Máximo por archivo: {MAX_FILE_SIZE_MB} MB
• Carpetas separadas: downloads / packed
• Números persistentes: No cambian al eliminar

**📌 EJEMPLOS PRÁCTICOS:**
`/cd downloads` - Ir a descargas
`/list` - Ver mis archivos
`/delete 3` - Eliminar archivo #3
`/rename 5 mi_documento` - Renombrar archivo #5
`/pack 50` - Empaquetar en partes de 50MB
`/queue` - Ver qué se está procesando"""

        await message.reply_text(help_text)

    except Exception as e:
        logger.error(f"Error en /help: {e}")

async def cd_command(client, message):
    """Maneja el comando /cd - Cambiar carpeta actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        args = message.text.split()
        
        if len(args) == 1:
            current = session['current_folder']
            folder_icon = "📥" if current == "downloads" else "📦"
            await message.reply_text(f"{folder_icon} **Carpeta actual:** `{current}`")
        else:
            folder = args[1].lower()
            if folder in ['downloads', 'packed']:
                session['current_folder'] = folder
                folder_icon = "📥" if folder == "downloads" else "📦"
                await message.reply_text(f"{folder_icon} **Cambiado a carpeta:** `{folder}`")
            else:
                await message.reply_text(
                    "❌ **Carpeta no válida.**\n\n"
                    "**Carpetas disponibles:**\n"
                    "• 📥 `downloads` - Tus archivos de descarga\n"  
                    "• 📦 `packed` - Archivos empaquetados\n\n"
                    "**Uso:** `/cd downloads` o `/cd packed`"
                )

    except Exception as e:
        logger.error(f"Error en /cd: {e}")
        await message.reply_text("❌ Error al cambiar carpeta.")

async def list_command(client, message):
    """Maneja el comando /list - Listar archivos de la carpeta actual CON PAGINACIÓN MEJORADA"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        args = message.text.split()
        page = 1
        if len(args) > 1:
            try:
                page = int(args[1])
            except ValueError:
                page = 1
        
        files = file_service.list_user_files(user_id, current_folder)
        
        if not files:
            folder_name = "📥 DESCARGAS" if current_folder == "downloads" else "📦 EMPAQUETADOS"
            await message.reply_text(
                f"📭 **{folder_name} VACÍA**\n\n"
                f"**Para agregar archivos:**\n"
                f"• Envía archivos al bot (van a 'downloads')\n"
                f"• Usa `/pack` para crear archivos en 'packed'\n\n"
                f"**Comando:** `/cd {'packed' if current_folder == 'downloads' else 'downloads'}`"
            )
            return
        
        items_per_page = 8  # Reducido para mejor visualización
        total_pages = (len(files) + items_per_page - 1) // items_per_page
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_files = files[start_idx:end_idx]
        
        folder_icon = "📥" if current_folder == "downloads" else "📦"
        folder_name = "DESCARGAS" if current_folder == "downloads" else "EMPAQUETADOS"
        
        files_text = f"{folder_icon} **{folder_name}** - Página {page}/{total_pages}\n"
        files_text += f"**Total:** {len(files)} archivos\n\n"
        
        for file_info in page_files:
            file_icon = "🎬" if file_info.get('stream_url') else "📄"
            files_text += f"**#{file_info['number']}** {file_icon} `{file_info['name']}`\n"
            files_text += f"📏 **Tamaño:** {file_info['size_mb']:.1f} MB\n"
            
            if file_info.get('stream_url'):
                files_text += f"🎬 **Ver online:** [Haz clic aquí]({file_info['stream_url']})\n"
            
            files_text += f"⬇️ **Descargar:** [Enlace directo]({file_info['url']})\n\n"

        # Información de paginación
        if total_pages > 1:
            files_text += f"**📄 Navegación:**\n"
            if page > 1:
                files_text += f"• `/list {page-1}` - Página anterior\n"
            if page < total_pages:
                files_text += f"• `/list {page+1}` - Página siguiente\n"
            files_text += f"• `/list <número>` - Ir a página específica\n\n"

        # Comandos disponibles
        files_text += f"**⚡ Comandos disponibles:**\n"
        files_text += f"• `/delete <número>` - Eliminar archivo\n"
        files_text += f"• `/rename <número> <nuevo_nombre>` - Renombrar\n"
        files_text += f"• `/clear` - Vaciar carpeta completa\n"
        
        if current_folder == "downloads" and len(files) > 0:
            files_text += f"• `/pack` - Empaquetar todos estos archivos\n"

        # Enviar mensaje (manejar límite de 4096 caracteres)
        if len(files_text) > 4000:
            parts = []
            current_part = ""
            
            for line in files_text.split('\n'):
                if len(current_part + line + '\n') > 4000:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            await message.reply_text(parts[0], disable_web_page_preview=True)
            
            for part in parts[1:]:
                await message.reply_text(part, disable_web_page_preview=True)
        else:
            await message.reply_text(files_text, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error en /list: {e}")
        await message.reply_text("❌ Error al listar archivos.")

async def delete_command(client, message):
    """Maneja el comando /delete - Eliminar archivo actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split()
        
        if len(args) < 2:
            folder_icon = "📥" if current_folder == "downloads" else "📦"
            await message.reply_text(
                f"❌ **Formato incorrecto.**\n\n"
                f"{folder_icon} **Carpeta actual:** `{current_folder}`\n\n"
                "**Uso:** `/delete <número>`\n"
                "**Ejemplo:** `/delete 5`\n\n"
                "Usa `/list` para ver los números de archivo."
            )
            return
        
        try:
            file_number = int(args[1])
        except ValueError:
            await message.reply_text("❌ El número debe ser un valor numérico válido.")
            return
        
        success, result_message = file_service.delete_file_by_number(user_id, file_number, current_folder)
        
        if success:
            folder_icon = "📥" if current_folder == "downloads" else "📦"
            await message.reply_text(f"✅ **{result_message}**\n{folder_icon} Números reorganizados.")
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en /delete: {e}")
        await message.reply_text("❌ Error al eliminar archivo.")

async def clear_command(client, message):
    """Maneja el comando /clear - Vaciar carpeta actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        folder_icon = "📥" if current_folder == "downloads" else "📦"
        folder_name = "descargas" if current_folder == "downloads" else "empaquetados"
        
        # Pedir confirmación
        confirm_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, vaciar", callback_data=f"clear_confirm_{user_id}_{current_folder}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="clear_cancel")
            ]
        ])
        
        await message.reply_text(
            f"⚠️ **¿Estás seguro de vaciar la carpeta {folder_name}?**\n\n"
            f"{folder_icon} Esta acción **eliminará todos** los archivos en `{current_folder}`\n"
            f"y no se puede deshacer.\n\n"
            f"**Confirma tu elección:**",
            reply_markup=confirm_keyboard
        )
            
    except Exception as e:
        logger.error(f"Error en /clear: {e}")
        await message.reply_text("❌ Error al vaciar carpeta.")

async def clear_callback_handler(client, callback_query):
    """Maneja la confirmación para vaciar carpeta"""
    try:
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if data == "clear_cancel":
            await callback_query.message.edit_text("❌ **Operación cancelada.**")
            await callback_query.answer()
            return
        
        if data.startswith("clear_confirm_"):
            parts = data.split("_")
            if len(parts) >= 4:
                target_user_id = int(parts[2])
                folder_type = parts[3]
                
                if user_id != target_user_id:
                    await callback_query.answer("❌ Esta confirmación no es para ti.", show_alert=True)
                    return
                
                success, result_message = file_service.delete_all_files(user_id, folder_type)
                
                folder_icon = "📥" if folder_type == "downloads" else "📦"
                
                if success:
                    await callback_query.message.edit_text(
                        f"✅ **{result_message}**\n\n"
                        f"{folder_icon} Carpeta `{folder_type}` vaciada completamente."
                    )
                else:
                    await callback_query.message.edit_text(f"❌ **{result_message}**")
                
                await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Error en clear_callback: {e}")
        await callback_query.answer("❌ Error en la operación.", show_alert=True)

async def rename_command(client, message):
    """Maneja el comando /rename - Renombrar archivo actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split(maxsplit=2)
        
        if len(args) < 3:
            folder_icon = "📥" if current_folder == "downloads" else "📦"
            await message.reply_text(
                f"❌ **Formato incorrecto.**\n\n"
                f"{folder_icon} **Carpeta actual:** `{current_folder}`\n\n"
                "**Uso:** `/rename <número> <nuevo_nombre>`\n"
                "**Ejemplo:** `/rename 3 mi_documento_importante`\n\n"
                "Usa `/list` para ver los números de archivo."
            )
            return
        
        try:
            file_number = int(args[1])
        except ValueError:
            await message.reply_text("❌ El número debe ser un valor numérico válido.")
            return
        
        new_name = args[2].strip()
        
        if not new_name:
            await message.reply_text("❌ El nuevo nombre no puede estar vacío.")
            return
        
        # Sanitizar nombre antes de proceder
        sanitized_name = file_service.sanitize_filename(new_name)
        if sanitized_name != new_name:
            await message.reply_text(
                f"ℹ️ **Nota:** El nombre ha sido ajustado por seguridad.\n"
                f"Original: `{new_name}`\n"
                f"Seguro: `{sanitized_name}`\n\n"
                f"¿Continuar con el nombre seguro?"
            )
            new_name = sanitized_name
        
        success, result_message, new_url, new_stream_url = file_service.rename_file(
            user_id, file_number, new_name, current_folder
        )
        
        if success:
            folder_icon = "📥" if current_folder == "downloads" else "📦"
            response_text = f"✅ **{result_message}**\n\n"
            response_text += f"{folder_icon} **Nuevo enlace de descarga:**\n"
            response_text += f"🔗 [{new_name}]({new_url})\n"
            
            if new_stream_url:
                response_text += f"🎬 **Nuevo enlace de streaming:**\n"
                response_text += f"🔗 [Ver online]({new_stream_url})\n"
            
            await message.reply_text(
                response_text,
                disable_web_page_preview=True
            )
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en comando /rename: {e}")
        await message.reply_text("❌ Error al renombrar archivo.")

async def status_command(client, message):
    """Maneja el comando /status - Estado del sistema MEJORADO"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        
        # Actualizar actividad del usuario
        await db.update_user_activity(user_id)
        
        # Estadísticas del usuario
        downloads = file_service.list_user_files(user_id, "downloads")
        packed = file_service.list_user_files(user_id, "packed")
        total_files = len(downloads) + len(packed)
        
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        # Estadísticas del sistema
        system_status = load_manager.get_status()
        import psutil
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        
        # Archivos con streaming
        streamable_files = sum(1 for f in downloads if f.get('stream_url'))
        
        # Estadísticas de la cola
        queue_size = len(user_queues.get(user_id, []))
        is_processing = user_id in user_current_processing
        
        status_text = f"""📊 **ESTADO DEL SISTEMA - {message.from_user.first_name}**

👤 **TU INFORMACIÓN:**
• **ID:** `{user_id}`
• **Carpeta actual:** `{session['current_folder']}`
• **Archivos totales:** {total_files}
• **Descargas:** {len(downloads)} (🎬 {streamable_files} streamables)
• **Empaquetados:** {len(packed)}
• **Espacio usado:** {size_mb:.2f} MB

🔄 **COLA DE PROCESAMIENTO:**
• **En cola:** {queue_size} archivos
• **Procesando ahora:** {"✅ Sí" if is_processing else "❌ No"}

📏 **CONFIGURACIÓN:**
• **Límite por archivo:** {MAX_FILE_SIZE_MB} MB
• **Streaming:** ✅ Activado
• **Sanitización:** ✅ Activada

🖥️ **SERVIDOR:**
• **Estado:** {"✅ ÓPTIMO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}
• **Procesos activos:** {system_status['active_processes']}/{system_status['max_processes']}
• **Uso de CPU:** {cpu_percent:.1f}%
• **Uso de memoria:** {memory.percent:.1f}%
• **Memoria libre:** {(memory.available/(1024**3)):.1f} GB"""

        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Error al obtener estado.")

async def pack_command(client, message):
    """Maneja el comando /pack - Empaquetado MEJORADO"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        # Verificar que haya archivos para empaquetar
        downloads = file_service.list_user_files(user_id, "downloads")
        if not downloads:
            await message.reply_text(
                "📭 **No hay archivos para empaquetar.**\n\n"
                "Primero envía algunos archivos a la carpeta `downloads`."
            )
            return
        
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado.**\n\n"
                f"CPU: {system_status['cpu_percent']:.1f}%\n"
                f"Procesos activos: {system_status['active_processes']}\n"
                f"Intenta nuevamente en unos minutos."
            )
            return
        
        split_size = None
        if len(command_parts) > 1:
            try:
                split_size = int(command_parts[1])
                if split_size <= 0:
                    await message.reply_text("❌ El tamaño de división debe ser mayor a 0 MB")
                    return
                if split_size > 200:
                    await message.reply_text("❌ El tamaño máximo por parte es 200 MB")
                    return
            except ValueError:
                await message.reply_text("❌ Formato incorrecto. Usa: `/pack` o `/pack 100`")
                return
        
        status_msg = await message.reply_text(
            "📦 **Iniciando empaquetado...**\n\n"
            f"📁 **Archivos a empaquetar:** {len(downloads)}\n"
            f"⚙️ **Modo:** {'Partes de ' + str(split_size) + 'MB' if split_size else 'ZIP único'}\n\n"
            "🔄 Procesando..."
        )
        
        def run_simple_packing():
            try:
                files, status_message = packing_service.pack_folder(user_id, split_size)
                return files, status_message
            except Exception as e:
                logger.error(f"Error en empaquetado: {e}")
                return None, f"Error al empaquetar: {str(e)}"
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_simple_packing)
            files, status_message = future.result(timeout=300)
        
        if not files:
            await status_msg.edit_text(f"❌ {status_message}")
            return
        
        if len(files) == 1:
            file_info = files[0]
            total_files_info = f" ({file_info['total_files']} archivos)" if 'total_files' in file_info else ""
            
            response_text = f"""✅ **EMPACUETADO COMPLETADO{total_files_info}**

📦 **Archivo generado:**
• **Nombre:** `{file_info['filename']}`
• **Tamaño:** {file_info['size_mb']:.1f} MB
• **Ubicación:** Carpeta `packed`

🔗 **Enlace de Descarga:**
⬇️ [{file_info['filename']}]({file_info['url']})

📁 **Para ver el archivo:**
`/cd packed` y luego `/list`"""

            await status_msg.edit_text(
                response_text, 
                disable_web_page_preview=True
            )
            
        else:
            total_files = 0
            for file_info in files:
                if 'total_files' in file_info:
                    total_files = file_info['total_files']
                    break
            
            total_size = sum(f['size_mb'] for f in files)
            
            response_text = f"""✅ **EMPACUETADO COMPLETADO ({total_files} archivos)**

📦 **Archivos generados:** {len(files)} partes
• **Tamaño total:** {total_size:.1f} MB
• **Tamaño por parte:** {split_size} MB
• **Ubicación:** Carpeta `packed`

🔗 **Enlaces de Descarga:**"""
            
            for file_info in files:
                response_text += f"\n\n**Parte {file_info['number']}:** ⬇️ [{file_info['filename']}]({file_info['url']})"
            
            response_text += "\n\n📁 **Para ver los archivos:**\n`/cd packed` y luego `/list`"
            
            if len(response_text) > 4000:
                await status_msg.edit_text(
                    f"✅ **Empaquetado completado ({total_files} archivos)**\n\n"
                    f"📦 Generadas {len(files)} partes de {split_size}MB\n"
                    f"📏 Tamaño total: {total_size:.1f} MB\n\n"
                    "📨 **Enviando enlaces por separado...**"
                )
                
                for file_info in files:
                    part_text = f"**Parte {file_info['number']}:** ⬇️ [{file_info['filename']}]({file_info['url']})"
                    await message.reply_text(part_text, disable_web_page_preview=True)
            else:
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True
                )
                
        logger.info(f"Empaquetado completado para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text(
            "❌ **Tiempo de empaquetado excedido.**\n\n"
            "Demasiados archivos o muy grandes.\n"
            "Intenta empaquetar menos archivos."
        )
    except Exception as e:
        logger.error(f"Error en comando /pack: {e}")
        await message.reply_text("❌ Error en el proceso de empaquetado.")

async def queue_command(client, message):
    """Maneja el comando /queue - Ver estado de la cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text(
                "📭 **Cola vacía**\n\n"
                "No hay archivos en cola de descarga.\n"
                "Envía archivos para que se agreguen automáticamente."
            )
            return
        
        queue = user_queues[user_id]
        queue_size = len(queue)
        current_processing = "✅ Sí" if user_id in user_current_processing else "❌ No"
        
        # Obtener información del primer archivo en cola
        next_file_info = "Desconocido"
        if queue and queue[0].document:
            next_file_info = f"📄 {queue[0].document.file_name or 'Documento sin nombre'}"
        elif queue and queue[0].video:
            next_file_info = f"🎥 {queue[0].video.file_name or 'Video sin nombre'}"
        elif queue and queue[0].audio:
            next_file_info = f"🎵 {queue[0].audio.file_name or 'Audio sin nombre'}"
        elif queue and queue[0].photo:
            next_file_info = f"🖼️ Foto"
        
        queue_text = f"""📋 **ESTADO DE LA COLA - {queue_size} archivo(s)**

🔄 **Estado actual:** {current_processing}
⏭️ **Siguiente archivo:** {next_file_info}

📜 **Archivos en cola:**"""
        
        for i, msg in enumerate(queue[:10]):  # Mostrar máximo 10
            file_info = "Desconocido"
            if msg.document:
                file_info = f"📄 {msg.document.file_name or 'Documento'}"
            elif msg.video:
                file_info = f"🎥 {msg.video.file_name or 'Video'}"
            elif msg.audio:
                file_info = f"🎵 {msg.audio.file_name or 'Audio'}"
            elif msg.photo:
                file_info = f"🖼️ Foto"
            
            queue_text += f"\n**#{i+1}** - {file_info}"
        
        if queue_size > 10:
            queue_text += f"\n\n... y {queue_size - 10} archivos más"
        
        queue_text += "\n\n⚡ **Los archivos se procesan automáticamente en orden.**"
        
        await message.reply_text(queue_text)
        
    except Exception as e:
        logger.error(f"Error en /queue: {e}")
        await message.reply_text("❌ Error al obtener estado de la cola.")

async def clear_queue_command(client, message):
    """Maneja el comando /clearqueue - Limpiar cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola ya está vacía**")
            return
        
        queue_size = len(user_queues[user_id])
        
        # Pedir confirmación
        confirm_keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, limpiar", callback_data=f"clearqueue_confirm_{user_id}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="clearqueue_cancel")
            ]
        ])
        
        await message.reply_text(
            f"⚠️ **¿Estás seguro de limpiar la cola?**\n\n"
            f"Esta acción eliminará **{queue_size} archivos** de la cola de procesamiento.\n"
            f"Los archivos ya procesados **NO** se verán afectados.\n\n"
            f"**Confirma tu elección:**",
            reply_markup=confirm_keyboard
        )
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Error al limpiar la cola.")

async def clearqueue_callback_handler(client, callback_query):
    """Maneja la confirmación para limpiar cola"""
    try:
        data = callback_query.data
        user_id = callback_query.from_user.id
        
        if data == "clearqueue_cancel":
            await callback_query.message.edit_text("❌ **Operación cancelada.**")
            await callback_query.answer()
            return
        
        if data.startswith("clearqueue_confirm_"):
            parts = data.split("_")
            if len(parts) >= 3:
                target_user_id = int(parts[2])
                
                if user_id != target_user_id:
                    await callback_query.answer("❌ Esta confirmación no es para ti.", show_alert=True)
                    return
                
                if target_user_id in user_queues:
                    queue_size = len(user_queues[target_user_id])
                    user_queues[target_user_id] = []
                    
                    if target_user_id in user_current_processing:
                        del user_current_processing[target_user_id]
                    
                    if target_user_id in user_batch_totals:
                        del user_batch_totals[target_user_id]
                    
                    await callback_query.message.edit_text(
                        f"🗑️ **Cola limpiada exitosamente**\n\n"
                        f"Se removieron {queue_size} archivos de la cola de procesamiento."
                    )
                else:
                    await callback_query.message.edit_text("📭 **La cola ya estaba vacía.**")
                
                await callback_query.answer()
    
    except Exception as e:
        logger.error(f"Error en clearqueue_callback: {e}")
        await callback_query.answer("❌ Error en la operación.", show_alert=True)

async def cleanup_command(client, message):
    """Limpia archivos temporales y optimiza el sistema"""
    try:
        status_msg = await message.reply_text("🧹 **Optimizando sistema...**")
        
        # Actualizar metadata
        file_service.save_metadata()
        
        # Estadísticas actuales
        total_size = file_service.get_user_storage_usage(message.from_user.id)
        size_mb = total_size / (1024 * 1024)
        
        downloads = len(file_service.list_user_files(message.from_user.id, "downloads"))
        packed = len(file_service.list_user_files(message.from_user.id, "packed"))
        
        await status_msg.edit_text(
            f"✅ **Sistema optimizado**\n\n"
            f"📊 **Tus estadísticas:**\n"
            f"• 📥 Descargas: {downloads} archivos\n"
            f"• 📦 Empaquetados: {packed} archivos\n"
            f"• 💾 Espacio usado: {size_mb:.2f} MB\n"
            f"• 🔄 Metadata guardada\n\n"
            f"⚡ **Sistema listo para seguir trabajando.**"
        )
        
    except Exception as e:
        logger.error(f"Error en comando cleanup: {e}")
        await message.reply_text("❌ Error durante la optimización.")

async def handle_file(client, message):
    """Maneja la recepción de archivos con sistema de cola MEJORADO"""
    try:
        user = message.from_user
        user_id = user.id

        # Actualizar actividad del usuario
        await db.update_user_activity(user_id)

        logger.info(f"📥 Archivo recibido de {user_id} - Agregando a cola")

        file_size = 0
        file_name = "archivo"
        
        if message.document:
            file_size = message.document.file_size or 0
            file_name = message.document.file_name or "documento_sin_nombre"
        elif message.video:
            file_size = message.video.file_size or 0
            file_name = message.video.file_name or "video_sin_nombre.mp4"
        elif message.audio:
            file_size = message.audio.file_size or 0
            file_name = message.audio.file_name or "audio_sin_nombre.mp3"
        elif message.photo:
            file_size = message.photo[-1].file_size or 0
            file_name = f"foto_{message.id}.jpg"

        # Sanitizar nombre
        safe_name = file_service.sanitize_filename(file_name)
        if safe_name != file_name:
            logger.info(f"Nombre sanitizado: {file_name} -> {safe_name}")

        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                "❌ **Archivo demasiado grande**\n\n"
                f"📏 **Límite máximo:** {MAX_FILE_SIZE_MB} MB\n"
                f"📏 **Tu archivo:** {file_service.format_bytes(file_size)}\n\n"
                "⚠️ **Solución:** Divide el archivo en partes más pequeñas."
            )
            return

        if user_id not in user_queues:
            user_queues[user_id] = []
        
        user_queues[user_id].append(message)
        
        # Notificar al usuario
        queue_size = len(user_queues[user_id])
        queue_position = queue_size
        
        if queue_size == 1:
            await message.reply_text(
                f"✅ **Archivo agregado a la cola**\n\n"
                f"📁 **Nombre:** `{safe_name}`\n"
                f"📏 **Tamaño:** {file_service.format_bytes(file_size)}\n"
                f"📋 **Posición en cola:** #{queue_position}\n"
                f"🔄 **Estado:** Procesando inmediatamente...\n\n"
                f"⚡ El archivo se procesará automáticamente."
            )
            await process_file_queue(client, user_id)
        else:
            await message.reply_text(
                f"✅ **Archivo agregado a la cola**\n\n"
                f"📁 **Nombre:** `{safe_name}`\n"
                f"📏 **Tamaño:** {file_service.format_bytes(file_size)}\n"
                f"📋 **Posición en cola:** #{queue_position}\n"
                f"🔄 **Estado:** En espera...\n\n"
                f"📊 **Archivos en cola:** {queue_size}\n"
                f"⏳ **Se procesará en orden de llegada.**"
            )
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text(
                "❌ **Error al procesar el archivo.**\n\n"
                "Intenta enviarlo nuevamente o contacta soporte."
            )
        except:
            pass

async def process_file_queue(client, user_id):
    """Procesa la cola de archivos del usuario de manera secuencial"""
    try:
        if user_id not in user_queues or not user_queues[user_id]:
            return
        
        total_files_in_batch = len(user_queues[user_id])
        user_batch_totals[user_id] = total_files_in_batch
        
        current_position = 0
        
        while user_queues.get(user_id) and user_queues[user_id]:
            message = user_queues[user_id][0]
            current_position += 1
            
            logger.info(f"🔄 Procesando archivo {current_position}/{total_files_in_batch} para usuario {user_id}")
            
            await process_single_file(client, message, user_id, current_position, total_files_in_batch)
            
            # Pequeña pausa entre archivos
            await asyncio.sleep(1)
        
        # Limpiar después de procesar todo
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
                
    except Exception as e:
        logger.error(f"Error en process_file_queue: {e}", exc_info=True)
        if user_id in user_queues:
            user_queues[user_id] = []
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]

async def process_single_file(client, message, user_id, current_position, total_files):
    """Procesa un solo archivo con progreso MEJORADO"""
    max_retries = 3
    start_time = time.time()
    
    try:
        file_obj = None
        file_type = None
        original_filename = None
        file_size = 0

        if message.document:
            file_obj = message.document
            file_type = "documento"
            original_filename = message.document.file_name or "archivo_sin_nombre"
            file_size = file_obj.file_size or 0
        elif message.video:
            file_obj = message.video
            file_type = "video"
            original_filename = message.video.file_name or "video_sin_nombre.mp4"
            file_size = file_obj.file_size or 0
        elif message.audio:
            file_obj = message.audio
            file_type = "audio"
            original_filename = message.audio.file_name or "audio_sin_nombre.mp3"
            file_size = file_obj.file_size or 0
        elif message.photo:
            file_obj = message.photo[-1]
            file_type = "foto"
            original_filename = f"foto_{message.id}.jpg"
            file_size = file_obj.file_size or 0
        else:
            logger.warning(f"Mensaje no contiene archivo manejable: {message.media}")
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            return

        if not file_obj:
            logger.error("No se pudo obtener el objeto de archivo")
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            await message.reply_text("❌ Error: No se pudo identificar el archivo.")
            return

        # Sanitizar nombre
        sanitized_name = file_service.sanitize_filename(original_filename)
        if sanitized_name != original_filename:
            logger.info(f"Nombre sanitizado para almacenamiento: {original_filename} -> {sanitized_name}")

        user_dir = file_service.get_user_directory(user_id, "downloads")
        
        stored_filename = sanitized_name
        counter = 1
        base_name, ext = os.path.splitext(sanitized_name)
        file_path = os.path.join(user_dir, stored_filename)
        
        # Evitar colisiones de nombres
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        # Registrar archivo en metadata
        file_number = file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        logger.info(f"📝 Archivo registrado: #{file_number} - {original_filename}")

        # Crear mensaje de progreso inicial
        initial_message = progress_service.create_progress_message(
            filename=original_filename,
            current=0,
            total=file_size,
            speed=0,
            user_first_name=message.from_user.first_name,
            process_type="Subiendo",
            current_file=current_position,
            total_files=total_files
        )
        
        progress_msg = await message.reply_text(initial_message)
        
        user_current_processing[user_id] = progress_msg.id

        progress_data = {'last_update': 0, 'last_speed': 0}

        async def progress_callback(current, total):
            try:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0
                
                # Suavizar velocidad
                progress_data['last_speed'] = (
                    0.7 * progress_data.get('last_speed', 0) + 0.3 * speed
                )
                smoothed_speed = progress_data['last_speed']

                current_time = time.time()
                last_update = progress_data.get('last_update', 0)

                if current_time - last_update >= 0.5 or current == total:
                    progress_message = progress_service.create_progress_message(
                        filename=original_filename,
                        current=current,
                        total=total,
                        speed=smoothed_speed,
                        user_first_name=message.from_user.first_name,
                        process_type="Subiendo",
                        current_file=current_position,
                        total_files=total_files
                    )

                    try:
                        await progress_msg.edit_text(progress_message)
                        progress_data['last_update'] = current_time
                    except Exception as edit_error:
                        logger.warning(f"No se pudo editar mensaje de progreso: {edit_error}")

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")

        try:
            logger.info(f"⚡ Iniciando descarga rápida: {original_filename}")
            
            success, downloaded = await fast_download_service.download_with_retry(
                client=client,
                message=message,
                file_path=file_path,
                progress_callback=progress_callback
            )

            if not success or not os.path.exists(file_path):
                await progress_msg.edit_text("❌ Error: El archivo no se descargó correctamente.")
                if user_id in user_queues and user_queues[user_id]:
                    user_queues[user_id].pop(0)
                return

            final_size = os.path.getsize(file_path)
            size_mb = final_size / (1024 * 1024)
            
            # Verificar integridad
            if file_size > 0 and final_size < file_size * 0.95:
                logger.warning(f"⚠️ Posible descarga incompleta: esperado {file_size}, obtenido {final_size}")
                await progress_msg.edit_text("⚠️ Advertencia: El archivo podría estar incompleto.")

            # Generar URLs
            download_url = file_service.create_download_url(user_id, stored_filename)
            stream_url = file_service.create_stream_url(user_id, stored_filename)
            
            logger.info(f"🔗 URLs generadas para archivo #{file_number}")

            # Información de la cola
            next_files_count = len(user_queues[user_id]) - 1 if user_id in user_queues and user_queues[user_id] else 0
            queue_info = f"\n\n⏭️ **Siguiente archivo en cola...** ({next_files_count} restantes)" if next_files_count > 0 else ""

            # Determinar icono según tipo
            file_icon = "📄"
            if file_type == "video":
                file_icon = "🎥"
            elif file_type == "audio":
                file_icon = "🎵"
            elif file_type == "foto":
                file_icon = "🖼️"

            # Crear mensaje de éxito
            success_text = f"""✅ **{file_icon} ARCHIVO #{file_number} ALMACENADO**

**📁 Nombre:** `{original_filename}`
**📦 Tipo:** {file_type}
**📏 Tamaño:** {size_mb:.2f} MB
**📂 Carpeta:** `downloads`

🔗 **Enlaces disponibles:**
• ⬇️ **Descargar:** [Enlace directo]({download_url})"""

            # Añadir streaming si es video/audio
            if file_type in ["video", "audio"]:
                success_text += f"\n• 🎬 **Streaming:** [Ver online]({stream_url})"
            
            success_text += queue_info

            # Crear teclado con botones
            keyboard = None
            if file_type in ["video", "audio"]:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🎬 Ver Online", url=stream_url),
                        InlineKeyboardButton("⬇️ Descargar", url=download_url)
                    ],
                    [
                        InlineKeyboardButton("📁 Ir a Downloads", callback_data="goto_downloads")
                    ]
                ])
            else:
                keyboard = InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("⬇️ Descargar", url=download_url)
                    ],
                    [
                        InlineKeyboardButton("📁 Ir a Downloads", callback_data="goto_downloads")
                    ]
                ])

            await progress_msg.edit_text(
                success_text, 
                disable_web_page_preview=True,
                reply_markup=keyboard
            )
            
            logger.info(f"✅ Archivo #{file_number} procesado exitosamente para usuario {user_id}")

        except Exception as download_error:
            logger.error(f"❌ Error en descarga: {download_error}", exc_info=True)
            await progress_msg.edit_text(
                f"❌ **Error al procesar el archivo**\n\n"
                f"**Detalle:** {str(download_error)[:100]}\n\n"
                f"Intenta enviar el archivo nuevamente."
            )
        
        # Limpiar de la cola
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

    except Exception as e:
        logger.error(f"❌ Error procesando archivo individual: {e}", exc_info=True)
        try:
            await message.reply_text(
                f"❌ **Error crítico al procesar archivo**\n\n"
                f"El sistema ha encontrado un error inesperado.\n"
                f"Por favor, intenta nuevamente."
            )
        except:
            pass
        
        # Limpiar en caso de error
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

async def goto_downloads_callback(client, callback_query):
    """Maneja callback para ir a downloads"""
    try:
        user_id = callback_query.from_user.id
        
        # Cambiar carpeta a downloads
        session = get_user_session(user_id)
        session['current_folder'] = 'downloads'
        
        await callback_query.answer("📂 Cambiando a carpeta downloads...")
        await callback_query.message.reply_text("📥 **Cambiado a carpeta:** `downloads`\n\nUsa `/list` para ver tus archivos.")
        
    except Exception as e:
        logger.error(f"Error en goto_downloads_callback: {e}")
        await callback_query.answer("❌ Error al cambiar carpeta.", show_alert=True)

def setup_handlers(client):
    """Configura todos los handlers del bot"""
    # Comandos básicos
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    
    # Comandos de navegación
    client.on_message(filters.command("cd") & filters.private)(cd_command)
    client.on_message(filters.command("list") & filters.private)(list_command)
    client.on_message(filters.command("delete") & filters.private)(delete_command)
    client.on_message(filters.command("clear") & filters.private)(clear_command)
    client.on_message(filters.command("rename") & filters.private)(rename_command)
    
    # Comandos de empaquetado
    client.on_message(filters.command("pack") & filters.private)(pack_command)
    
    # Comandos de cola
    client.on_message(filters.command("queue") & filters.private)(queue_command)
    client.on_message(filters.command("clearqueue") & filters.private)(clear_queue_command)
    
    # Comandos de mantenimiento
    client.on_message(filters.command("cleanup") & filters.private)(cleanup_command)
    
    # Callbacks
    client.on_callback_query(filters.regex(r"^clear_confirm_"))(clear_callback_handler)
    client.on_callback_query(filters.regex(r"^clear_cancel$"))(clear_callback_handler)
    client.on_callback_query(filters.regex(r"^clearqueue_confirm_"))(clearqueue_callback_handler)
    client.on_callback_query(filters.regex(r"^clearqueue_cancel$"))(clearqueue_callback_handler)
    client.on_callback_query(filters.regex(r"^goto_downloads$"))(goto_downloads_callback)
    
    # Handler de archivos
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)
    
    # Importar y configurar handlers administrativos
    from admin_handlers import setup_admin_handlers
    setup_admin_handlers(client)