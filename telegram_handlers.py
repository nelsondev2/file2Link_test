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
from filename_utils import safe_filename, clean_for_filesystem, clean_for_url  # NUEVO IMPORT

logger = logging.getLogger(__name__)

# ===== NUEVO: SISTEMA DE COLA MEJORADO =====
user_queues = {}
user_sessions = {}
user_progress_msgs = {}
user_current_processing = {}
user_batch_totals = {}
user_queue_locks = {}  # NUEVO: Locks por usuario para concurrencia

# NUEVO: Estadísticas globales
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

# ===== NUEVO: FUNCIONES AUXILIARES =====
async def send_to_bin_channel(client, text):
    """Enviar mensaje al canal de logs (como primer bot)"""
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

def get_readable_time(seconds: int) -> str:
    """Tiempo legible para estadísticas"""
    count = 0
    time_list = []
    time_suffix_list = ["s", "m", "h", " días"]
    while count < 4:
        count += 1
        if count < 3:
            remainder, result = divmod(seconds, 60)
        else:
            remainder, result = divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    
    if len(time_list) == 4:
        readable_time = time_list.pop() + ", "
    else:
        readable_time = ""
    
    time_list.reverse()
    readable_time += ": ".join(time_list)
    return readable_time

# ===== NUEVO: COMANDOS DE ADMINISTRACIÓN =====
async def users_command(client, message):
    """Comando /users - Solo para owners (como primer bot)"""
    try:
        user_id = message.from_user.id
        
        # Registrar usuario primero
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        # Verificar si es owner
        if user_id not in OWNER_ID:
            await message.reply_text("❌ Este comando es solo para administradores.")
            return
        
        total_users = file_service.total_users_count()
        
        # Obtener usuarios recientes
        recent_users = []
        for uid, user_data in file_service.users.items():
            if 'last_seen' in user_data:
                if time.time() - user_data['last_seen'] < 7 * 24 * 3600:  # Últimos 7 días
                    recent_users.append(user_data)
        
        response = f"""👥 **ESTADÍSTICAS DE USUARIOS**

**Total de usuarios:** `{total_users}`
**Usuarios activos (7 días):** `{len(recent_users)}`

**Últimos 5 usuarios:**
"""
        
        # Ordenar por último acceso
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
        
        response += f"\n**Comando:** `/broadcast` para enviar mensaje a todos"
        
        await message.reply_text(response)
        
        # Enviar a bin channel
        await send_to_bin_channel(
            client,
            f"#USERS_COMMAND\n\n"
            f"**Usuario:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
            f"**Comando:** /users\n"
            f"**Total usuarios:** {total_users}"
        )
        
    except Exception as e:
        logger.error(f"Error en /users: {e}")
        await message.reply_text("❌ Error obteniendo usuarios.")

async def stats_command(client, message):
    """Comando /stats - Estadísticas completas del sistema"""
    try:
        user_id = message.from_user.id
        
        # Registrar usuario primero
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        system_status = load_manager.get_status()
        download_stats = fast_download_service.get_stats()
        total_users = file_service.total_users_count()
        
        # Calcular estadísticas de archivos
        total_files = 0
        total_size = 0
        for uid in file_service.users:
            user_id_int = int(uid)
            downloads = len(file_service.list_user_files(user_id_int, "downloads"))
            packed = len(file_service.list_user_files(user_id_int, "packed"))
            total_files += downloads + packed
            
            user_size = file_service.get_user_storage_usage(user_id_int)
            total_size += user_size
        
        # Estadísticas globales
        uptime_seconds = time.time() - global_stats['start_time']
        readable_uptime = get_readable_time(uptime_seconds)
        
        stats_text = f"""📊 **ESTADÍSTICAS COMPLETAS DEL SISTEMA**

🕐 **Uptime del bot:** {readable_uptime}

👥 **USUARIOS:**
• **Total registrados:** {total_users}
• **Archivos totales:** {total_files}
• **Espacio total usado:** {load_manager.get_readable_file_size(total_size)}

💾 **ALMACENAMIENTO:**
• **CPU:** {system_status['cpu_percent']:.1f}%
• **RAM:** {system_status['memory_percent']:.1f}%
• **Disco:** {system_status['disk_percent']:.1f}%

📡 **RED:**
• **Subida:** {system_status['network_sent']}
• **Descarga:** {system_status['network_recv']}

⬇️ **DESCARGAS:**
• **Total:** {download_stats['total_downloads']}
• **Exitosas:** {download_stats['successful']}
• **Fallidas:** {download_stats['failed']}
• **Bytes totales:** {load_manager.get_readable_file_size(download_stats['total_bytes'])}
• **FloodWaits:** {download_stats['floodwaits']}

⚙️ **SISTEMA:**
• **Procesos activos:** {system_status['active_processes']}/{system_status['max_processes']}
• **Estado:** {"✅ ACEPTANDO TRABAJO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}
• **Colas activas:** {len(user_queues)}"""

        await message.reply_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error en /stats: {e}")
        await message.reply_text("❌ Error obteniendo estadísticas.")

async def about_command(client, message):
    """Comando /about - VERSIÓN SIMPLIFICADA"""
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
• Enlaces válidos por {file_service.HASH_EXPIRE_DAYS} días

**📞 Soporte:**
Bot para gestión de archivos via Telegram."""

        await message.reply_text(about_text)
        
    except Exception as e:
        logger.error(f"Error en /about: {e}")
        await message.reply_text("❌ Error mostrando información.")

# ===== COMANDOS EXISTENTES MEJORADOS =====
async def start_command(client, message):
    """Maneja el comando /start - VERSIÓN SIMPLIFICADA"""
    try:
        user = message.from_user
        
        # Registrar usuario
        is_new = file_service.add_user(user.id, user.first_name)
        
        if is_new:
            # Enviar a bin channel si está configurado
            await send_to_bin_channel(
                client,
                f"#NEW_USER\n\n"
                f"**Usuario:** [{user.first_name}](tg://user?id={user.id})\n"
                f"**ID:** `{user.id}`\n"
                f"**Username:** @{user.username if user.username else 'N/A'}"
            )
        
        welcome_text = f"""👋 **Hola {user.first_name}!**

🤖 **Bot de Archivos**

**📁 COMANDOS BÁSICOS:**
`/cd downloads` - Tus archivos de descarga
`/cd packed` - Tus archivos empaquetados

**📄 EN CARPETA ACTUAL:**
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
`/status` - Tu información

**🔍 AYUDA:**
`/help` - Ver todos los comandos

**📏 LÍMITE:** {MAX_FILE_SIZE_MB} MB por archivo

**¡Envía archivos para comenzar!**"""

        await message.reply_text(welcome_text)
        logger.info(f"/start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"Error en /start: {e}")

async def help_command(client, message):
    """Maneja el comando /help - VERSIÓN SIMPLIFICADA"""
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
`/list` - Ver archivos (usa `/list 2` para página 2)
`/rename N NUEVO_NOMBRE` - Renombrar archivo #N
`/delete N` - Eliminar archivo #N
`/clear` - Vaciar carpeta

**📦 EMPAQUETADO:**
`/pack` - Crear ZIP de downloads
`/pack MB` - Dividir en partes (ej: `/pack 100`)

**🔄 COLA DE DESCARGA:**
`/queue` - Ver archivos en cola
`/clearqueue` - Limpiar cola
Límite: {MAX_QUEUE_SIZE} archivos en cola

**🔍 INFORMACIÓN:**
`/status` - Tu estado y uso
`/about` - Información del bot

**📌 EJEMPLOS:**
`/cd downloads`
`/list`
`/delete 5`
`/rename 3 mi_documento`
`/pack 100`
`/queue`"""

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
                    "• `packed` - Archivos empaquetados\n\n"
                    "**Uso:** `/cd downloads` o `/cd packed`"
                )

    except Exception as e:
        logger.error(f"Error en /cd: {e}")
        await message.reply_text("❌ Error al cambiar carpeta.")

async def list_command(client, message):
    """Maneja el comando /list - Listar archivos de la carpeta actual CON PAGINACIÓN"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
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
            await message.reply_text(
                f"📂 **Carpeta {current_folder} vacía.**\n\n"
                f"**Para agregar archivos:**\n"
                f"• Envía archivos al bot (van a 'downloads')\n"
                f"• Usa `/pack` para crear archivos en 'packed'\n"
            )
            return
        
        items_per_page = 10
        total_pages = (len(files) + items_per_page - 1) // items_per_page
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_files = files[start_idx:end_idx]
        
        folder_display = "📥 DESCARGAS" if current_folder == "downloads" else "📦 EMPAQUETADOS"
        files_text = f"**{folder_display}** - Página {page}/{total_pages}\n"
        files_text += f"**Total de archivos:** {len(files)}\n\n"
        
        for file_info in page_files:
            # Mostrar hash en la URL (primeros 8 caracteres)
            url_hash = file_info['url'].split('/')[-1].split('?')[0][:8]
            files_text += f"**#{file_info['number']}** - `{file_info['name']}`\n"
            files_text += f"📏 **Tamaño:** {file_info['size_mb']:.1f} MB\n"
            files_text += f"🔗 **Enlace:** [Descargar]({file_info['url']})\n\n"

        if total_pages > 1:
            files_text += f"**Navegación:**\n"
            if page > 1:
                files_text += f"• `/list {page-1}` - Página anterior\n"
            if page < total_pages:
                files_text += f"• `/list {page+1}` - Página siguiente\n"
            files_text += f"• `/list <número>` - Ir a página específica\n"

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
            
            # Enviar a bin channel
            await send_to_bin_channel(
                client,
                f"#FILE_DELETED\n\n"
                f"**Usuario:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
                f"**Archivo:** #{file_number} en {current_folder}\n"
                f"**Resultado:** {result_message}"
            )
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
            
            await send_to_bin_channel(
                client,
                f"#FOLDER_CLEARED\n\n"
                f"**Usuario:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
                f"**Carpeta:** {current_folder}\n"
                f"**Resultado:** {result_message}"
            )
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
            
            await send_to_bin_channel(
                client,
                f"#FILE_RENAMED\n\n"
                f"**Usuario:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
                f"**Archivo:** #{file_number} en {current_folder}\n"
                f"**Nuevo nombre:** {new_name}"
            )
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error en comando /rename: {e}")
        await message.reply_text("❌ Error al renombrar archivo.")

async def status_command(client, message):
    """Maneja el comando /status - VERSIÓN SIMPLIFICADA"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        session = get_user_session(user_id)
        
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        # Estadísticas de cola
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
        
        # Enviar a bin channel
        await send_to_bin_channel(
            client,
            f"#PACK_COMPLETED\n\n"
            f"**Usuario:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
            f"**Archivos:** {total_files if 'total_files' in locals() else 'N/A'}\n"
            f"**Partes:** {len(files)}\n"
            f"**Split size:** {split_size if split_size else 'No split'}"
        )
        
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
            
            # Indicador visual del orden
            if i == 1 and user_id not in user_current_processing:
                queue_text += f"**👉 #{i}** - {file_info} ({size_mb:.1f} MB) **[PRÓXIMO]**\n"
            else:
                queue_text += f"**#{i}** - {file_info} ({size_mb:.1f} MB)\n"
        
        queue_text += f"\n**Comandos:**\n"
        queue_text += f"• `/clearqueue` - Limpiar cola completa\n"
        queue_text += f"• `/status` - Ver tu estado\n"
        queue_text += f"• Los archivos se procesan UNO POR UNO en el orden mostrado"
        
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
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n\nSe removieron {queue_size} archivos de la cola.")
        
        await send_to_bin_channel(
            client,
            f"#QUEUE_CLEARED\n\n"
            f"**Usuario:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
            f"**Archivos removidos:** {queue_size}\n"
            f"**Comando:** /clearqueue"
        )
        
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
        
        # Limpiar hashes expirados
        expired_count = file_service.cleanup_expired_hashes()
        
        # Obtener estadísticas del usuario
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        
        await status_msg.edit_text(
            f"✅ **Limpieza completada**\n\n"
            f"• Hashes expirados limpiados: {expired_count}\n"
            f"• Tus archivos downloads: {downloads_count}\n"
            f"• Tus archivos packed: {packed_count}\n"
            f"• Tu espacio usado: {size_mb:.2f} MB\n"
            f"• Sistema optimizado y listo"
        )
        
    except Exception as e:
        logger.error(f"Error en comando cleanup: {e}")
        await message.reply_text("❌ Error durante la limpieza.")

# ===== NUEVO: SISTEMA DE COLA MEJORADO =====
async def handle_file(client, message):
    """Maneja la recepción de archivos con sistema de cola - SIN MENSAJES DE CONFIRMACIÓN"""
    try:
        user = message.from_user
        user_id = user.id

        # Registrar usuario silenciosamente
        file_service.add_user(user_id, user.first_name)
        
        logger.info(f"📥 Archivo recibido de {user_id} - {user.first_name}")

        # Obtener tamaño del archivo
        file_size = 0
        if message.document:
            file_size = message.document.file_size or 0
        elif message.video:
            file_size = message.video.file_size or 0
        elif message.audio:
            file_size = message.audio.file_size or 0
        elif message.photo:
            file_size = message.photo[-1].file_size or 0

        # Verificar tamaño máximo (SOLO mostrar mensaje si es demasiado grande)
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                "❌ **Archivo demasiado grande**\n\n"
                f"**Tamaño máximo permitido:** {MAX_FILE_SIZE_MB} MB\n"
                f"**Tu archivo:** {file_service.format_bytes(file_size)}\n\n"
                "Por favor, divide el archivo en partes más pequeñas."
            )
            return

        # Inicializar cola si no existe
        if user_id not in user_queues:
            user_queues[user_id] = []
        
        # Verificar límite de cola (NO mostrar mensaje si está llena)
        if len(user_queues[user_id]) >= MAX_QUEUE_SIZE:
            # Silenciosamente ignorar el archivo si la cola está llena
            logger.warning(f"Cola llena para usuario {user_id}, ignorando archivo")
            return
        
        # Agregar archivo a la cola - SIN CONFIRMACIÓN
        user_queues[user_id].append(message)
        
        # Iniciar procesamiento si no hay otro en curso
        if user_id not in user_current_processing:
            # Marcar como procesando y ejecutar en background
            user_current_processing[user_id] = True
            asyncio.create_task(process_user_queue(client, user_id))
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        # NO enviar mensaje de error al usuario

async def process_user_queue(client, user_id):
    """Procesa TODOS los archivos en cola del usuario - CORREGIDO"""
    try:
        logger.info(f"Iniciando procesamiento de cola para usuario {user_id}")
        
        # Procesar todos los archivos que estén en la cola
        while user_queues.get(user_id) and user_queues[user_id]:
            total_files = len(user_queues[user_id])
            
            # Procesar cada archivo en orden
            for position, message in enumerate(list(user_queues[user_id]), 1):
                # Verificar que el mensaje aún esté en la cola antes de procesar
                if not user_queues.get(user_id) or position > len(user_queues[user_id]):
                    continue
                    
                # Tomar el primer archivo de la cola
                current_message = user_queues[user_id].pop(0)
                
                # Procesar el archivo
                await process_single_file_silent(
                    client, current_message, user_id, position, total_files
                )
                
                # Pequeña pausa entre archivos
                await asyncio.sleep(0.5)
            
            # Verificar si llegaron más archivos mientras procesábamos
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Error en process_user_queue: {e}", exc_info=True)
    finally:
        # Siempre liberar el flag de procesamiento
        if user_id in user_current_processing:
            del user_current_processing[user_id]
        logger.info(f"Procesamiento completado para usuario {user_id}")

async def process_single_file_silent(client, message, user_id, position, total):
    """Procesa un solo archivo solo mostrando mensaje final"""
    try:
        # Obtener información del archivo
        file_obj = None
        original_filename = ""
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
            logger.warning(f"Mensaje no contiene archivo manejable: {message.media}")
            return

        if not file_obj:
            logger.error("No se pudo obtener el objeto de archivo")
            return

        # Crear nombre seguro para almacenamiento
        user_dir = file_service.get_user_directory(user_id, "downloads")
        stored_filename = safe_filename(original_filename)
        
        # Verificar si el nombre es seguro
        from filename_utils import is_filename_safe
        if not is_filename_safe(stored_filename):
            logger.warning(f"Nombre no seguro después de limpieza: {stored_filename}")
            stored_filename = f"archivo_{int(time.time()) % 10000}"
            if original_filename and '.' in original_filename:
                _, ext = os.path.splitext(original_filename)
                stored_filename += ext
        
        # Evitar colisiones de nombres
        file_path = os.path.join(user_dir, stored_filename)
        counter = 1
        base_name, ext = os.path.splitext(stored_filename)
        
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        # Registrar archivo en el sistema
        file_number = file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        logger.info(f"📝 Archivo registrado: #{file_number} - {original_filename}")

        # Descargar el archivo
        success, downloaded = await fast_download_service.download_with_retry(
            client=client,
            message=message,
            file_path=file_path,
            progress_callback=None  # Sin progreso
        )

        if not success or not os.path.exists(file_path):
            logger.error(f"Error al descargar archivo: {original_filename}")
            return

        # Obtener información final
        final_size = os.path.getsize(file_path)
        size_mb = final_size / (1024 * 1024)
        
        # Generar URL de descarga
        download_url = file_service.create_download_url(user_id, stored_filename)
        
        # Actualizar estadísticas
        update_global_stats(bytes_received=final_size, files_received=1)
        
        # Enviar mensaje final con el enlace
        success_text = f"""✅ **Archivo guardado**

**Nombre:** `{original_filename}`
**Tamaño:** {size_mb:.1f} MB

**Enlace:** [Descargar]({download_url})"""
        
        await message.reply_text(success_text, disable_web_page_preview=True)
        
        logger.info(f"✅ Archivo procesado: {original_filename} para usuario {user_id}")
        
        # Enviar a bin channel
        await send_to_bin_channel(
            client,
            f"#FILE_UPLOADED\n\n"
            f"**Usuario:** [{message.from_user.first_name}](tg://user?id={user_id})\n"
            f"**Archivo:** #{file_number} - {original_filename}\n"
            f"**Tamaño:** {size_mb:.2f} MB\n"
            f"**Posición:** {position}/{total}"
        )

    except Exception as e:
        logger.error(f"❌ Error procesando archivo individual: {e}", exc_info=True)

def setup_handlers(client):
    """Configura todos los handlers del bot MEJORADO"""
    # Comandos básicos
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    client.on_message(filters.command("stats") & filters.private)(stats_command)
    client.on_message(filters.command("about") & filters.private)(about_command)
    
    # Comandos de administración (solo owners)
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
    
    # Manejo de archivos (SIN MENSAJES DE CONFIRMACIÓN)
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)