import os
import logging
import sys
import time
import asyncio
import concurrent.futures
import hashlib
import re
from collections import deque
from pyrogram import Client, filters
from pyrogram.types import Message

from config import OWNER_ID, BIN_CHANNEL, MAX_QUEUE_SIZE, MAX_CONCURRENT_UPLOADS, MAX_FILE_SIZE, MAX_FILE_SIZE_MB
from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import fast_download_service
from filename_utils import safe_filename, clean_for_filesystem, clean_for_url
from url_utils import fix_problematic_filename

logger = logging.getLogger(__name__)

# ===== SISTEMA DE COLA MEJORADO =====
user_queues = {}
user_sessions = {}
user_current_processing = {}
user_batch_totals = {}
user_queue_locks = {}
user_progress_messages = {}
user_completed_files = {}
user_progress_data = {}

# Estadísticas globales
global_stats = {
    'total_files_received': 0,
    'total_bytes_received': 0,
    'total_users_served': 0,
    'start_time': time.time()
}

def get_user_session(user_id):
    """Obtiene o crea la sesión del usuario"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'current_folder': 'downloads'}
    return user_sessions[user_id]

def get_user_queue_lock(user_id):
    """Obtiene lock para la cola del usuario"""
    if user_id not in user_queue_locks:
        user_queue_locks[user_id] = asyncio.Lock()
    return user_queue_locks[user_id]

# ===== FUNCIONES AUXILIARES =====
async def send_to_bin_channel(client, text):
    """Enviar mensaje al canal de logs"""
    try:
        if BIN_CHANNEL:
            await client.send_message(
                chat_id=int(BIN_CHANNEL),
                text=text,
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error enviando a bin_channel: {e}")

def update_global_stats(bytes_received=0, files_received=0, users_served=0):
    """Actualizar estadísticas globales"""
    if bytes_received > 0:
        global_stats['total_bytes_received'] += bytes_received
    if files_received > 0:
        global_stats['total_files_received'] += files_received
    if users_served > 0:
        global_stats['total_users_served'] += users_served

# ===== COMANDOS DE ADMINISTRACIÓN =====
async def users_command(client, message):
    """Comando /users - Solo para owners"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        if user_id not in OWNER_ID:
            await message.reply_text("❌ Este comando es solo para administradores.")
            return
        
        total_users = file_service.total_users_count()
        
        response = f"""👥 **ESTADÍSTICAS DE USUARIOS**

**Total de usuarios:** `{total_users}`

**Últimos 5 usuarios:**
"""
        
        sorted_users = sorted(
            list(file_service.users.values()),
            key=lambda x: x.get('last_seen', 0),
            reverse=True
        )[:5]
        
        for i, user in enumerate(sorted_users, 1):
            user_id = user.get('id', 'N/A')
            first_name = user.get('first_name', 'Desconocido')
            last_seen = user.get('last_seen', 0)
            
            if last_seen > 0:
                time_ago = time.time() - last_seen
                if time_ago < 3600:
                    last_seen_str = f"{int(time_ago/60)} min"
                elif time_ago < 86400:
                    last_seen_str = f"{int(time_ago/3600)} h"
                else:
                    last_seen_str = f"{int(time_ago/86400)} días"
            else:
                last_seen_str = "Nunca"
            
            files_count = user.get('files_count', 0)
            
            response += f"{i}. **{first_name}** (`{user_id}`) - {files_count} archivos - Visto: {last_seen_str}\n"
        
        await message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error en /users: {e}")
        await message.reply_text("❌ Error obteniendo usuarios.")

async def stats_command(client, message):
    """Comando /stats - Estadísticas completas del sistema"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        system_status = load_manager.get_status()
        download_stats = fast_download_service.get_stats()
        total_users = file_service.total_users_count()
        
        total_files = 0
        total_size = 0
        for uid in file_service.users:
            user_id_int = int(uid)
            downloads = len(file_service.list_user_files(user_id_int, "downloads"))
            packed = len(file_service.list_user_files(user_id_int, "packed"))
            total_files += downloads + packed
            
            user_size = file_service.get_user_storage_usage(user_id_int)
            total_size += user_size
        
        uptime_seconds = time.time() - global_stats['start_time']
        
        stats_text = f"""📊 **ESTADÍSTICAS DEL SISTEMA**

👥 **USUARIOS:** {total_users}
📁 **ARCHIVOS:** {total_files}
💾 **ESPACIO:** {load_manager.get_readable_file_size(total_size)}

⚙️ **SISTEMA:**
• CPU: {system_status['cpu_percent']:.1f}%
• RAM: {system_status['memory_percent']:.1f}%
• Procesos: {system_status['active_processes']}/{system_status['max_processes']}

⬇️ **DESCARGAS:**
• Total: {download_stats['total_downloads']}
• Exitosas: {download_stats['successful']}
• Fallidas: {download_stats['failed']}"""

        await message.reply_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error en /stats: {e}")
        await message.reply_text("❌ Error obteniendo estadísticas.")

async def about_command(client, message):
    """Comando /about"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        about_text = f"""🤖 **Bot de Archivos**

**Funciones principales:**
• Subir archivos hasta {MAX_FILE_SIZE_MB} MB
• Descargar desde enlaces
• Empaquetar en ZIP
• Renombrar y organizar

**📏 Especificaciones:**
• Tamaño máximo: {MAX_FILE_SIZE_MB} MB
• Archivos en cola: {MAX_QUEUE_SIZE}
• Enlaces válidos por {file_service.HASH_EXPIRE_DAYS} días"""

        await message.reply_text(about_text)
        
    except Exception as e:
        logger.error(f"Error en /about: {e}")
        await message.reply_text("❌ Error mostrando información.")

# ===== COMANDOS BÁSICOS =====
async def start_command(client, message):
    """Maneja el comando /start"""
    try:
        user = message.from_user
        
        is_new = file_service.add_user(user.id, user.first_name)
        
        if is_new:
            await send_to_bin_channel(
                client,
                f"#NEW_USER\n\n"
                f"**Usuario:** [{user.first_name}](tg://user?id={user.id})\n"
                f"**ID:** `{user.id}`"
            )
        
        welcome_text = f"""👋 **Hola {user.first_name}!**

🤖 **Bot de Archivos**

**📁 COMANDOS BÁSICOS:**
`/cd downloads` - Tus archivos de descarga
`/cd packed` - Tus archivos empaquetados
`/list` - Ver archivos
`/rename N nuevo_nombre`
`/delete N`
`/clear` - Vaciar carpeta

**📦 EMPAQUETAR:**
`/pack` - Crear ZIP de tus archivos
`/pack MB` - Dividir en partes

**🔄 GESTIÓN:**
`/queue` - Ver cola de descargas
`/clearqueue` - Limpiar cola

**📏 LÍMITE:** {MAX_FILE_SIZE_MB} MB por archivo

**¡Envía archivos para comenzar!**"""

        await message.reply_text(welcome_text)
        logger.info(f"/start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"Error en /start: {e}")

async def help_command(client, message):
    """Maneja el comando /help"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        help_text = f"""📚 **COMANDOS DISPONIBLES**

**📁 NAVEGACIÓN:**
`/cd downloads` - Archivos de descarga
`/cd packed` - Archivos empaquetados  
`/cd` - Ver carpeta actual

**📄 GESTIÓN (en carpeta actual):**
`/list` - Ver archivos
`/rename N NUEVO_NOMBRE` - Renombrar archivo #N
`/delete N` - Eliminar archivo #N
`/clear` - Vaciar carpeta

**📦 EMPAQUETADO:**
`/pack` - Crear ZIP de downloads
`/pack MB` - Dividir en partes

**🔄 COLA DE DESCARGA:**
`/queue` - Ver archivos en cola
`/clearqueue` - Limpiar cola
Límite: {MAX_QUEUE_SIZE} archivos en cola

**🔍 INFORMACIÓN:**
`/status` - Tu estado y uso
`/about` - Información del bot"""

        await message.reply_text(help_text)

    except Exception as e:
        logger.error(f"Error en /help: {e}")

async def cd_command(client, message):
    """Maneja el comando /cd - Cambiar carpeta actual"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        session = get_user_session(user_id)
        args = message.text.split()
        
        if len(args) == 1:
            current = session['current_folder']
            await message.reply_text(f"📂 **Carpeta actual:** `{current}`")
        else:
            folder = args[1].lower()
            if folder in ['downloads', 'packed']:
                session['current_folder'] = folder
                await message.reply_text(f"📂 **Cambiado a carpeta:** `{folder}`")
            else:
                await message.reply_text(
                    "❌ **Carpeta no válida.**\n\n"
                    "**Carpetas disponibles:**\n"
                    "• `downloads` - Tus archivos de descarga\n"  
                    "• `packed` - Archivos empaquetados"
                )

    except Exception as e:
        logger.error(f"Error en /cd: {e}")
        await message.reply_text("❌ Error al cambiar carpeta.")

async def list_command(client, message):
    """Maneja el comando /list - Listar archivos de la carpeta actual"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        files = file_service.list_user_files(user_id, current_folder)
        
        if not files:
            await message.reply_text(
                f"📂 **Carpeta {current_folder} vacía.**\n\n"
                f"**Para agregar archivos:**\n"
                f"• Envía archivos al bot (van a 'downloads')\n"
                f"• Usa `/pack` para crear archivos en 'packed'\n"
            )
            return
        
        folder_display = "📥 DESCARGAS" if current_folder == "downloads" else "📦 EMPAQUETADOS"
        files_text = f"**{folder_display}**\n"
        files_text += f"**Total de archivos:** {len(files)}\n\n"
        
        for file_info in files:
            # Mostrar nombre original pero truncado si es muy largo
            display_name = file_info['name']
            if len(display_name) > 40:
                display_name = display_name[:37] + "..."
            
            files_text += f"**#{file_info['number']}** - `{display_name}`\n"
            files_text += f"📏 **Tamaño:** {file_info['size_mb']:.1f} MB\n"
            files_text += f"🔗 **Enlace:** [Descargar]({file_info['url']})\n\n"

        files_text += f"\n**Comandos disponibles:**\n"
        files_text += f"• `/delete <número>` - Eliminar archivo\n"
        files_text += f"• `/rename <número> <nuevo_nombre>` - Renombrar\n"
        files_text += f"• `/clear` - Vaciar carpeta completa"

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
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split()
        
        if len(args) < 2:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
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
            await message.reply_text(f"✅ **{result_message}**")
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en /delete: {e}")
        await message.reply_text("❌ Error al eliminar archivo.")

async def clear_command(client, message):
    """Maneja el comando /clear - Vaciar carpeta actual"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        success, result_message = file_service.delete_all_files(user_id, current_folder)
        
        if success:
            await message.reply_text(f"✅ **{result_message}**")
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en /clear: {e}")
        await message.reply_text("❌ Error al vaciar carpeta.")

async def rename_command(client, message):
    """Maneja el comando /rename - Renombrar archivo actual"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split(maxsplit=2)
        
        if len(args) < 3:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
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
        
        success, result_message, new_url = file_service.rename_file(user_id, file_number, new_name, current_folder)
        
        if success:
            response_text = f"✅ **{result_message}**\n\n"
            response_text += f"**Nuevo enlace:**\n"
            response_text += f"🔗 [{new_name}]({new_url})"
            
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
    """Maneja el comando /status"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        session = get_user_session(user_id)
        
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        queue_size = len(user_queues.get(user_id, []))
        is_processing = user_id in user_current_processing
        
        status_text = f"""📊 **TU INFORMACIÓN**

**👤 USUARIO:**
• Carpeta actual: `{session['current_folder']}`
• Archivos descargados: {downloads_count}
• Archivos empaquetados: {packed_count}
• Espacio usado: {size_mb:.2f} MB

**🔄 COLA:**
• Archivos en cola: {queue_size}
• Procesando: {"Sí" if is_processing else "No"}
• Límite: {MAX_QUEUE_SIZE} archivos

**💡 TIPS:**
• Usa `/queue` para ver cola detallada
• Usa `/clearqueue` para limpiar cola"""

        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Error al obtener estado.")

async def pack_command(client, message):
    """Maneja el comando /pack - Empaquetado"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        command_parts = message.text.split()
        
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
            "Uniendo todos tus archivos en un ZIP seguro..."
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
            
            response_text = f"""✅ **Empaquetado completado{total_files_info}**

**Archivo:** `{file_info['filename']}`
**Tamaño:** {file_info['size_mb']:.1f} MB

**Enlace de descarga:**
🔗 [{file_info['filename']}]({file_info['url']})"""
            
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
            
            total_files_info = f" ({total_files} archivos)" if total_files > 0 else ""
            
            response_text = f"""✅ **Empaquetado completado{total_files_info}**

**Archivos:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

**Enlaces de descarga:**"""
            
            for file_info in files:
                response_text += f"\n\n**Parte {file_info['number']}:** 🔗 [{file_info['filename']}]({file_info['url']})"
            
            response_text += "\n\n**Nota:** Usa `/cd packed` y `/list` para ver tus archivos empaquetados"
            
            if len(response_text) > 4000:
                await status_msg.edit_text("✅ **Empaquetado completado**\n\nLos enlaces se enviarán en varios mensajes...")
                
                for file_info in files:
                    part_text = f"**Parte {file_info['number']}:** 🔗 [{file_info['filename']}]({file_info['url']})"
                    await message.reply_text(part_text, disable_web_page_preview=True)
            else:
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True
                )
                
        logger.info(f"Empaquetado completado para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text("❌ El empaquetado tardó demasiado tiempo. Intenta con menos archivos.")
    except Exception as e:
        logger.error(f"Error en comando /pack: {e}")
        await message.reply_text("❌ Error en el proceso de empaquetado.")

async def queue_command(client, message):
    """Maneja el comando /queue - Ver estado de la cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola vacía**\n\nNo hay archivos en cola de descarga.")
            return
        
        queue_size = len(user_queues[user_id])
        current_processing = "✅ **EN PROCESO AHORA**" if user_id in user_current_processing else "⏸️ **Esperando turno**"
        
        queue_text = f"📋 **Estado de la Cola - {queue_size} archivo(s)**\n\n"
        queue_text += f"**Estado actual:** {current_processing}\n"
        queue_text += f"**Límite de cola:** {MAX_QUEUE_SIZE} archivos\n"
        queue_text += f"**Procesamiento:** UNO POR UNO (orden estricto)\n\n"
        queue_text += f"**Archivos en cola (en este orden):**\n"
        
        for i, msg in enumerate(user_queues[user_id], 1):
            file_info = "Desconocido"
            file_size = 0
            
            if msg.document:
                file_info = f"📄 {msg.document.file_name or 'Documento sin nombre'}"
                file_size = msg.document.file_size or 0
            elif msg.video:
                file_info = f"🎥 {msg.video.file_name or 'Video sin nombre'}"
                file_size = msg.video.file_size or 0
            elif msg.audio:
                file_info = f"🎵 {msg.audio.file_name or 'Audio sin nombre'}"
                file_size = msg.audio.file_size or 0
            elif msg.photo:
                file_info = f"🖼️ Foto"
                file_size = msg.photo[-1].file_size or 0
            
            size_mb = file_size / (1024 * 1024) if file_size > 0 else 0
            
            queue_text += f"**#{i}** - {file_info} ({size_mb:.1f} MB)\n"
        
        queue_text += f"\n**Comandos:**\n"
        queue_text += f"• `/clearqueue` - Limpiar cola completa"
        
        await message.reply_text(queue_text)
        
    except Exception as e:
        logger.error(f"Error en /queue: {e}")
        await message.reply_text("❌ Error al obtener estado de la cola.")

async def clear_queue_command(client, message):
    """Maneja el comando /clearqueue - Limpiar cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola ya está vacía**")
            return
        
        queue_size = len(user_queues[user_id])
        user_queues[user_id] = []
        
        if user_id in user_current_processing:
            del user_current_processing[user_id]
        
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
        
        if user_id in user_progress_messages:
            del user_progress_messages[user_id]
        
        if user_id in user_completed_files:
            del user_completed_files[user_id]
        
        if user_id in user_progress_data:
            del user_progress_data[user_id]
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n\nSe removieron {queue_size} archivos de la cola.")
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Error al limpiar la cola.")

async def cleanup_command(client, message):
    """Limpia archivos temporales y optimiza el sistema"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        status_msg = await message.reply_text("🧹 **Limpiando y optimizando sistema...**")
        
        expired_count = file_service.cleanup_expired_hashes()
        
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        
        await status_msg.edit_text(
            f"✅ **Limpieza completada**\n\n"
            f"• Hashes expirados limpiados: {expired_count}\n"
            f"• Tus archivos downloads: {downloads_count}\n"
            f"• Tus archivos packed: {packed_count}\n"
            f"• Tu espacio usado: {size_mb:.2f} MB"
        )
        
    except Exception as e:
        logger.error(f"Error en comando cleanup: {e}")
        await message.reply_text("❌ Error durante la limpieza.")

# ===== SISTEMA DE COLA CON PROGRESO INDIVIDUAL POR ARCHIVO =====
async def handle_file(client, message):
    """Maneja la recepción de archivos con sistema de cola"""
    try:
        user = message.from_user
        user_id = user.id

        # Registrar usuario primero
        is_new_user = file_service.add_user(user_id, user.first_name)
        if is_new_user:
            update_global_stats(users_served=1)
        
        logger.info(f"📥 Archivo recibido de {user_id} - {user.first_name}")

        file_size = 0
        if message.document:
            file_size = message.document.file_size or 0
        elif message.video:
            file_size = message.video.file_size or 0
        elif message.audio:
            file_size = message.audio.file_size or 0
        elif message.photo:
            file_size = message.photo[-1].file_size or 0

        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                "❌ **Archivo demasiado grande**\n\n"
                f"**Tamaño máximo permitido:** {MAX_FILE_SIZE_MB} MB\n"
                f"**Tu archivo:** {file_service.format_bytes(file_size)}\n\n"
                "Por favor, divide el archivo en partes más pequeñas."
            )
            return

        # Verificar límites de cola
        if user_id not in user_queues:
            user_queues[user_id] = []
        
        current_queue_size = len(user_queues[user_id])
        
        can_upload, message_text = load_manager.can_accept_upload(user_id, current_queue_size)
        if not can_upload:
            await message.reply_text(f"⚠️ **{message_text}**")
            return
        
        if current_queue_size >= MAX_QUEUE_SIZE:
            await message.reply_text(
                f"❌ **Límite de cola alcanzado**\n\n"
                f"Solo puedes tener {MAX_QUEUE_SIZE} archivos en cola.\n"
                f"Espera a que se procesen algunos o usa `/clearqueue`."
            )
            return
        
        # Agregar a cola
        user_queues[user_id].append(message)
        
        # Iniciar procesamiento si no hay otro en curso
        if user_id not in user_current_processing:
            asyncio.create_task(process_file_queue(client, user_id))
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)

async def process_file_queue(client, user_id):
    """Procesa la cola de archivos del usuario con progreso individual"""
    try:
        async with get_user_queue_lock(user_id):
            total_files_in_batch = len(user_queues[user_id])
            if total_files_in_batch == 0:
                return
            
            user_batch_totals[user_id] = total_files_in_batch
            user_current_processing[user_id] = True
            
            # Inicializar lista de archivos completados
            user_completed_files[user_id] = []
            
            current_position = 0
            completed_files = []
            
            # Procesar archivos UNO POR UNO
            while user_queues.get(user_id) and user_queues[user_id]:
                # Tomar SOLO UN archivo de la cola
                if not user_queues[user_id]:
                    break
                
                message = user_queues[user_id].pop(0)
                current_position += 1
                
                try:
                    # Procesar el archivo individualmente con progreso
                    result = await process_file_with_progress(
                        client, message, user_id, 
                        current_position, total_files_in_batch
                    )
                    
                    if result:
                        completed_files.append(result)
                    
                    # Pequeña pausa entre archivos para estabilidad
                    if current_position < total_files_in_batch:
                        await asyncio.sleep(0.3)
                    
                except Exception as e:
                    logger.error(f"Error procesando archivo #{current_position}: {e}")
                    continue
            
            # Al finalizar todos los archivos, mostrar resumen con enlaces
            if completed_files:
                await show_final_summary(client, user_id, completed_files)
            
            # Limpieza final
            cleanup_user_session(user_id)
                
    except Exception as e:
        logger.error(f"Error en process_file_queue: {e}", exc_info=True)
        cleanup_user_session(user_id)

async def process_file_with_progress(client, message, user_id, current_position, total_files):
    """Procesa un archivo mostrando solo progreso DURANTE la subida"""
    start_time = time.time()
    
    try:
        file_obj = None
        original_filename = None
        file_size = 0

        if message.document:
            file_obj = message.document
            original_filename = message.document.file_name or "archivo_sin_nombre"
            file_size = file_obj.file_size or 0
        elif message.video:
            file_obj = message.video
            original_filename = message.video.file_name or "video_sin_nombre.mp4"
            file_size = file_obj.file_size or 0
        elif message.audio:
            file_obj = message.audio
            original_filename = message.audio.file_name or "audio_sin_nombre.mp3"
            file_size = file_obj.file_size or 0
        elif message.photo:
            file_obj = message.photo[-1]
            original_filename = f"foto_{message.id}.jpg"
            file_size = file_obj.file_size or 0
        else:
            return None

        if not file_obj:
            return None

        user_dir = file_service.get_user_directory(user_id, "downloads")
        
        # Manejo de nombres problemáticos
        stored_filename = safe_filename(original_filename, user_id)
        
        # Verificar si el nombre todavía tiene problemas
        from filename_utils import is_filename_safe
        if not is_filename_safe(stored_filename):
            # Generar nombre completamente seguro
            import time as t
            import random
            timestamp = int(t.time())
            random_num = random.randint(1000, 9999)
            
            # Obtener extensión
            _, ext = os.path.splitext(original_filename)
            if not ext:
                ext = ".dat"
            
            stored_filename = f"file_{timestamp}_{random_num}{ext}"
            logger.warning(f"Nombre problemático detectado: {original_filename} -> {stored_filename}")
        
        file_path = os.path.join(user_dir, stored_filename)
        counter = 1
        base_name, ext = os.path.splitext(stored_filename)
        
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        # Registrar archivo
        file_number = file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        
        # Solo crear mensaje de progreso para el PRIMER archivo
        if current_position == 1 and user_id not in user_progress_messages:
            progress_text = progress_service.create_progress_message(
                filename=original_filename,
                current=0,
                total=file_size,
                speed=0,
                user_first_name=message.from_user.first_name,
                process_type="Subiendo",
                current_file=current_position,
                total_files=total_files
            )
            
            progress_msg = await client.send_message(
                user_id,
                progress_text,
                disable_web_page_preview=True
            )
            user_progress_messages[user_id] = progress_msg.id
            user_progress_data[user_id] = {
                'last_update': 0,
                'last_speed': 0,
                'start_time': start_time,
                'current_position': current_position,
                'total_files': total_files
            }
        
        # Actualizar datos de progreso para el archivo actual
        if user_id in user_progress_data:
            user_progress_data[user_id].update({
                'current_position': current_position,
                'current_filename': original_filename,
                'current_filesize': file_size,
                'start_time': start_time,
                'last_speed': 0,
                'last_update': 0
            })
        
        async def progress_callback(current, total):
            try:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0
                
                # Suavizar velocidad
                if user_id in user_progress_data:
                    last_speed = user_progress_data[user_id].get('last_speed', 0)
                    smoothed_speed = 0.7 * last_speed + 0.3 * speed
                    user_progress_data[user_id]['last_speed'] = smoothed_speed

                    current_time = time.time()
                    last_update = user_progress_data[user_id].get('last_update', 0)

                    if current_time - last_update >= 0.5 or current == total:
                        # Solo actualizar si es el archivo actual
                        if user_progress_data[user_id].get('current_position') == current_position:
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
                                await client.edit_message_text(
                                    chat_id=user_id,
                                    message_id=user_progress_messages[user_id],
                                    text=progress_message,
                                    disable_web_page_preview=True
                                )
                                user_progress_data[user_id]['last_update'] = current_time
                            except Exception as edit_error:
                                logger.warning(f"No se pudo editar mensaje de progreso: {edit_error}")

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")
        
        # Descargar archivo con progreso
        success, downloaded = await fast_download_service.download_with_retry(
            client=client,
            message=message,
            file_path=file_path,
            progress_callback=progress_callback
        )

        if not success or not os.path.exists(file_path):
            # Solo mostrar error si es el último archivo
            if current_position == total_files and user_id in user_progress_messages:
                error_text = f"❌ **Error al subir archivo**\n\n`{original_filename}`\n\nEl archivo no se descargó correctamente."
                try:
                    await client.edit_message_text(
                        chat_id=user_id,
                        message_id=user_progress_messages[user_id],
                        text=error_text,
                        disable_web_page_preview=True
                    )
                except:
                    pass
            return None

        final_size = os.path.getsize(file_path)
        size_mb = final_size / (1024 * 1024)
        
        # Generar URL con hash
        download_url = file_service.create_download_url(user_id, stored_filename)
        
        # NO mostrar nada entre archivos
        # Solo pasar al siguiente archivo en silencio
        
        # Actualizar estadísticas globales
        update_global_stats(bytes_received=final_size, files_received=1)
        
        logger.info(f"✅ Archivo procesado: {original_filename} -> {stored_filename} para usuario {user_id}")
        
        return {
            'number': file_number,
            'name': original_filename,
            'display_name': original_filename[:40] + "..." if len(original_filename) > 40 else original_filename,
            'stored_name': stored_filename,
            'size_mb': size_mb,
            'url': download_url,
            'position': current_position
        }

    except Exception as e:
        logger.error(f"Error procesando archivo individual: {e}", exc_info=True)
        
        # Solo mostrar error si es el último archivo
        if current_position == total_files and user_id in user_progress_messages:
            error_text = f"❌ **Error procesando archivo**\n\n`{original_filename if 'original_filename' in locals() else 'Archivo'}`\n\n{str(e)[:100]}"
            try:
                await client.edit_message_text(
                    chat_id=user_id,
                    message_id=user_progress_messages[user_id],
                    text=error_text,
                    disable_web_page_preview=True
                )
            except:
                pass
        
        return None

async def show_final_summary(client, user_id, completed_files):
    """Muestra el resumen final con todos los enlaces"""
    try:
        if not completed_files:
            return
        
        # Eliminar el mensaje de progreso si existe
        if user_id in user_progress_messages:
            try:
                await client.delete_messages(
                    chat_id=user_id,
                    message_ids=user_progress_messages[user_id]
                )
            except:
                pass
        
        # Crear mensaje de resumen
        summary_text = f"""✅ **¡Procesamiento completado!**

**📊 Resumen:**
• **Total de archivos procesados:** {len(completed_files)}
• **Archivos exitosos:** {len(completed_files)}

**🔗 Enlaces de descarga:**
"""
        
        for file_info in completed_files:
            # Mostrar nombre original truncado
            display_name = file_info['display_name']
            
            summary_text += f"\n**#{file_info['number']}** - `{display_name}`\n"
            summary_text += f"📏 **Tamaño:** {file_info['size_mb']:.1f} MB\n"
            summary_text += f"🔗 [{file_info['name']}]({file_info['url']})\n"
        
        summary_text += f"\n**📁 Ubicación:** Carpeta `downloads`"
        summary_text += f"\n**📋 Comando:** `/list` para ver todos tus archivos"
        summary_text += f"\n**✏️ Renombrar:** `/rename <número> <nuevo_nombre>` si algún enlace no funciona"
        
        # Si el mensaje es muy largo, dividirlo
        if len(summary_text) > 4000:
            # Primera parte
            first_part = summary_text[:4000]
            last_newline = first_part.rfind('\n')
            if last_newline > 0:
                first_part = first_part[:last_newline]
            
            # Enviar primera parte
            await client.send_message(
                user_id,
                first_part,
                disable_web_page_preview=True
            )
            
            # Segunda parte (el resto)
            second_part = summary_text[last_newline + 1:]
            await client.send_message(
                user_id,
                second_part,
                disable_web_page_preview=True
            )
        else:
            # Enviar mensaje completo
            await client.send_message(
                user_id,
                summary_text,
                disable_web_page_preview=True
            )
        
        # Enviar a bin channel
        await send_to_bin_channel(
            client,
            f"#BATCH_COMPLETED\n\n"
            f"**Usuario:** {user_id}\n"
            f"**Archivos procesados:** {len(completed_files)}\n"
            f"**Estado:** Completado exitosamente"
        )
        
    except Exception as e:
        logger.error(f"Error mostrando resumen final: {e}")

def cleanup_user_session(user_id):
    """Limpia la sesión del usuario"""
    if user_id in user_current_processing:
        del user_current_processing[user_id]
    if user_id in user_batch_totals:
        del user_batch_totals[user_id]
    if user_id in user_progress_messages:
        del user_progress_messages[user_id]
    if user_id in user_completed_files:
        del user_completed_files[user_id]
    if user_id in user_progress_data:
        del user_progress_data[user_id]

def setup_handlers(client):
    """Configura todos los handlers del bot"""
    # Comandos básicos
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    client.on_message(filters.command("stats") & filters.private)(stats_command)
    client.on_message(filters.command("about") & filters.private)(about_command)
    
    # Comandos de administración
    client.on_message(filters.command("users") & filters.private)(users_command)
    
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
    
    # Comandos de limpieza
    client.on_message(filters.command("cleanup") & filters.private)(cleanup_command)
    
    # Manejo de archivos
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)