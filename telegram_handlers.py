import os
import logging
import sys
import time
import asyncio
import concurrent.futures
import re
from pyrogram import Client, filters
from pyrogram.types import Message

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import fast_download_service
from url_download_service import url_download_service
from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

# ===== SISTEMA DE SESIÓN POR USUARIO =====
user_sessions = {}
user_queues = {}
user_progress_msgs = {}
user_current_processing = {}
user_batch_totals = {}

# Expresión regular para detectar URLs
URL_PATTERN = re.compile(r'https?://[^\s]+')

def get_user_session(user_id):
    """Obtiene o crea la sesión del usuario"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'current_folder': 'downloads'}
    return user_sessions[user_id]

# ===== COMANDOS DE NAVEGACIÓN =====

async def start_command(client, message):
    """Maneja el comando /start"""
    try:
        user = message.from_user
        
        welcome_text = f"""👋 **Bienvenido/a {user.first_name}!**

🤖 File2Link Bot - Sistema de Gestión de Archivos por Carpetas

**📁 SISTEMA DE CARPETAS:**
`/cd downloads` - Acceder a archivos de descarga
`/cd packed` - Acceder a archivos empaquetados
`/cd` - Mostrar carpeta actual

**📄 COMANDOS EN CARPETA:**
`/list` - Listar archivos de la carpeta actual
`/rename <número> <nuevo_nombre>`
`/delete <número>`
`/clear` - Vaciar carpeta actual

**📦 EMPAQUETADO:**
`/pack` - Empaquetar downloads → packed
`/pack <MB>` - Empaquetar y dividir

**🔗 DESCARGA DESDE URL:**
`/dl <url>` - Descargar archivo desde URL directa
`/cancel` - Cancelar descarga actual

**🔄 GESTIÓN DE COLA:**
`/queue` - Ver archivos en cola de descarga
`/clearqueue` - Limpiar cola de descarga

**🔍 INFORMACIÓN:**
`/status` - Estado del sistema
`/help` - Ayuda completa

**📏 LÍMITE DE ARCHIVOS:**
Tamaño máximo: {MAX_FILE_SIZE_MB} MB

**¡Envía archivos, URLs o usa /cd para comenzar!**"""

        await message.reply_text(welcome_text)
        logger.info(f"/start recibido de {user.id} - {user.first_name}")

    except Exception as e:
        logger.error(f"Error en /start: {e}")

async def help_command(client, message):
    """Maneja el comando /help"""
    try:
        help_text = f"""📚 **Ayuda - Sistema de Carpetas**

**📁 NAVEGACIÓN:**
`/cd downloads` - Archivos de descarga
`/cd packed` - Archivos empaquetados  
`/cd` - Carpeta actual

**📄 GESTIÓN (en carpeta actual):**
`/list` - Ver archivos
`/rename N NUEVO_NOMBRE` - Renombrar
`/delete N` - Eliminar archivo
`/clear` - Vaciar carpeta

**📦 EMPAQUETADO:**
`/pack` - Crear ZIP de downloads
`/pack MB` - Dividir en partes

**🔗 DESCARGA DESDE URL:**
`/dl <url>` - Descargar archivo desde URL directa
`/cancel` - Cancelar descarga actual

**🔄 GESTIÓN DE COLA:**
`/queue` - Ver archivos en cola de descarga
`/clearqueue` - Limpiar cola de descarga

**🔍 INFORMACIÓN:**
`/status` - Estado del sistema
`/help` - Esta ayuda

**📏 LÍMITE DE ARCHIVOS:**
Tamaño máximo: {MAX_FILE_SIZE_MB} MB

**📌 EJEMPLOS:**
`/cd downloads`
`/list`
`/delete 5`
`/rename 3 mi_documento`
`/pack 100`
`/dl https://ejemplo.com/archivo.zip`
`/queue` - Ver qué archivos están en cola"""

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
                f"• Usa `/dl <url>` para descargar desde URL\n"
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
    """Maneja el comando /status - Estado del sistema"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        system_status = load_manager.get_status()
        
        status_text = f"""**📊 ESTADO DEL SISTEMA - {message.from_user.first_name}**

**👤 USUARIO:**
• **ID:** `{user_id}`
• **Carpeta actual:** `{session['current_folder']}`
• **Archivos downloads:** {downloads_count}
• **Archivos packed:** {packed_count}
• **Espacio usado:** {size_mb:.2f} MB

**📏 CONFIGURACIÓN:**
• **Límite por archivo:** {MAX_FILE_SIZE_MB} MB

**🖥️ SERVIDOR:**
• **Procesos activos:** {system_status['active_processes']}/{system_status['max_processes']}
• **Uso de CPU:** {system_status['cpu_percent']:.1f}%
• **Uso de memoria:** {system_status['memory_percent']:.1f}%
• **Estado:** {"✅ ACEPTANDO TRABAJO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}"""
        
        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Error al obtener estado.")

async def pack_command(client, message):
    """Maneja el comando /pack - Empaquetado COMPLETO como el original"""
    try:
        user_id = message.from_user.id
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
                if split_size > 501:
                    await message.reply_text("❌ El tamaño máximo por parte es 500 MB")
                    return
            except ValueError:
                await message.reply_text("❌ Formato incorrecto. Usa: `/pack` o `/pack 100`")
                return
        
        status_msg = await message.reply_text(
            "📦 **Iniciando empaquetado...**\n\n"
            f"{'Dividiendo en partes...' if split_size else 'Creando archivo ZIP...'}"
        )
        
        def run_advanced_packing():
            try:
                files, status_message = packing_service.pack_folder(user_id, split_size)
                return files, status_message
            except Exception as e:
                logger.error(f"Error en empaquetado optimizado: {e}")
                return None, f"Error al empaquetar: {str(e)}"
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_advanced_packing)
            files, status_message = future.result(timeout=300)
        
        if not files:
            await status_msg.edit_text(f"❌ {status_message}")
            return
        
        if len(files) == 1:
            file_info = files[0]
            total_files_info = f" ({file_info['total_files']} archivos)" if 'total_files' in file_info else ""
            
            response_text = f"""✅ **Empaquetado Completado{total_files_info}**

**Archivo:** `{file_info['filename']}`
**Tamaño:** {file_info['size_mb']:.1f} MB

**Enlace de Descarga:**
🔗 [{file_info['filename']}]({file_info['url']})

**Nota:** Usa `/cd packed` y `/list` para ver tus archivos empaquetados"""
            
            await status_msg.edit_text(
                response_text, 
                disable_web_page_preview=True
            )
            
        else:
            total_files = 0
            for file_info in files:
                if 'total_files' in file_info and file_info['total_files'] > 0:
                    total_files = file_info['total_files']
                    break
            
            total_files_info = f" ({total_files} archivos)" if total_files > 0 else ""
            
            # Buscar archivo de lista de partes (.txt)
            user_dir = file_service.get_user_directory(user_id, "packed")
            base_name = None
            for file_info in files:
                if '.001' in file_info['filename']:
                    base_name = file_info['filename'].rsplit('.', 2)[0]
                    break
            
            list_filename = f"{base_name}.txt" if base_name else None
            list_url = None
            
            if list_filename and os.path.exists(os.path.join(user_dir, list_filename)):
                list_url = file_service.create_packed_url(user_id, list_filename)
            
            # CONSTRUIR MENSAJE COMPLETO CON TODOS LOS ENLACES (COMO EL ORIGINAL)
            response_text = f"""✅ **Empaquetado Completado{total_files_info}**

**Archivos Generados:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB

**Enlaces de Descarga:**"""
            
            # Agregar TODOS los enlaces en el mensaje (como el original)
            for file_info in files:
                response_text += f"\n\n**{file_info['filename']}**\n"
                response_text += f"🔗 {file_info['url']}"
            
            # Agregar enlace al archivo .txt si existe
            if list_url:
                response_text += f"\n\n**📑 Lista completa en archivo:**"
                response_text += f"\n🔗 [{list_filename}]({list_url})"
            
            response_text += "\n\n**Nota:** Usa `/cd packed` y `/list` para ver tus archivos empaquetados"
            
            # Manejar mensajes largos (dividir si es necesario)
            if len(response_text) > 4000:
                await status_msg.edit_text("✅ **Empaquetado completado**\n\nLos enlaces se enviarán en varios mensajes...")
                
                # Enviar primero el mensaje con estadísticas
                stats_msg = f"""✅ **Empaquetado Completado{total_files_info}**

**Archivos Generados:** {len(files)} partes
**Tamaño Total:** {sum(f['size_mb'] for f in files):.1f} MB"""
                
                if list_url:
                    stats_msg += f"\n\n**📑 Lista completa en archivo:**"
                    stats_msg += f"\n🔗 [{list_filename}]({list_url})"
                
                await message.reply_text(stats_msg, disable_web_page_preview=True)
                
                # Enviar enlaces en grupos de 10
                for i in range(0, len(files), 10):
                    group = files[i:i+10]
                    group_text = ""
                    for file_info in group:
                        group_text += f"\n\n**{file_info['filename']}**\n"
                        group_text += f"🔗 {file_info['url']}"
                    
                    await message.reply_text(group_text, disable_web_page_preview=True)
                    
                await message.reply_text(f"✅ **Total: {len(files)} partes generadas**")
            else:
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True
                )
                
        logger.info(f"Empaquetado optimizado completado para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await status_msg.edit_text("❌ El empaquetado tardó demasiado tiempo. Intenta con menos archivos.")
    except Exception as e:
        logger.error(f"Error en comando /pack optimizado: {e}")
        await message.reply_text("❌ Error en el proceso de empaquetado.")

async def queue_command(client, message):
    """Maneja el comando /queue - Ver estado de la cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola vacía**\n\nNo hay archivos en cola de descarga.")
            return
        
        queue_size = len(user_queues[user_id])
        current_processing = "Sí" if user_id in user_current_processing else "No"
        
        queue_text = f"📋 **Estado de la Cola - {queue_size} elemento(s)**\n\n"
        
        for i, item in enumerate(user_queues[user_id]):
            if isinstance(item, dict) and item.get('type') == 'url':
                # Es una URL
                url = item.get('url', 'URL desconocida')
                queue_text += f"**#{i+1}** - 🔗 URL: `{url[:50]}...`\n"
            else:
                # Es un archivo normal
                msg = item
                file_info = "Desconocido"
                if msg.document:
                    file_info = f"📄 {msg.document.file_name or 'Documento sin nombre'}"
                elif msg.video:
                    file_info = f"🎥 {msg.video.file_name or 'Video sin nombre'}"
                elif msg.audio:
                    file_info = f"🎵 {msg.audio.file_name or 'Audio sin nombre'}"
                elif msg.photo:
                    file_info = f"🖼️ Foto"
                
                queue_text += f"**#{i+1}** - {file_info}\n"
        
        queue_text += f"\n**Procesando actualmente:** {current_processing}"
        
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
        user_queues[user_id] = []
        
        if user_id in user_current_processing:
            del user_current_processing[user_id]
        
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n\nSe removieron {queue_size} elementos de la cola.")
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Error al limpiar la cola.")

async def cleanup_command(client, message):
    """Limpia archivos temporales y optimiza el sistema"""
    try:
        status_msg = await message.reply_text("🧹 **Limpiando archivos temporales...**")
        
        total_size = file_service.get_user_storage_usage(message.from_user.id)
        size_mb = total_size / (1024 * 1024)
        
        await status_msg.edit_text(
            f"✅ **Limpieza completada**\n\n"
            f"• Espacio usado: {size_mb:.2f} MB\n"
            f"• Sistema optimizado"
        )
        
    except Exception as e:
        logger.error(f"Error en comando cleanup: {e}")
        await message.reply_text("❌ Error durante la limpieza.")

# ===== URL DOWNLOAD HANDLERS =====

async def download_url_command(client, message):
    """Maneja el comando /dl <url> - Descargar archivo desde URL"""
    try:
        user_id = message.from_user.id
        args = message.text.split(maxsplit=1)
        
        if len(args) < 2:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/dl <url_directa>`\n"
                "**Ejemplo:** `/dl https://ejemplo.com/archivo.zip`\n\n"
                "**Nota:** Solo URLs de descarga directa."
            )
            return
        
        url = args[1].strip()
        
        # Verificar que sea una URL válida
        if not URL_PATTERN.match(url):
            await message.reply_text("❌ **URL no válida.**\n\nPor favor, envía una URL completa comenzando con http:// o https://")
            return
        
        # Verificar estado del sistema
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado.**\n\n"
                f"CPU: {system_status['cpu_percent']:.1f}%\n"
                f"Procesos activos: {system_status['active_processes']}\n"
                f"Intenta nuevamente en unos minutos."
            )
            return
        
        # Verificar cola
        if user_id not in user_queues:
            user_queues[user_id] = []
        
        # Guardar información de la URL para procesar
        url_info = {
            'type': 'url',
            'url': url,
            'user_id': user_id,
            'message': message
        }
        
        user_queues[user_id].append(url_info)
        
        await message.reply_text(
            f"🔗 **URL agregada a la cola de descarga**\n\n"
            f"**URL:** `{url}`\n"
            f"**Posición en cola:** {len(user_queues[user_id])}\n\n"
            f"Usa `/queue` para ver el estado de la cola."
        )
        
        # Si es el único en cola, comenzar procesamiento
        if len(user_queues[user_id]) == 1:
            await process_queue(client, user_id)
        
    except Exception as e:
        logger.error(f"Error en comando /dl: {e}")
        await message.reply_text(f"❌ Error al procesar la URL: {str(e)}")

async def cancel_download_command(client, message):
    """Maneja el comando /cancel - Cancelar descarga actual"""
    try:
        user_id = message.from_user.id
        
        if user_id in user_current_processing:
            # Marcar para cancelar
            if user_id in url_download_service.active_downloads:
                del url_download_service.active_downloads[user_id]
            
            await message.reply_text("⏹️ **Cancelando descarga actual...**")
            
            # Limpiar estado
            del user_current_processing[user_id]
        else:
            await message.reply_text("❌ No hay ninguna descarga activa para cancelar.")
            
    except Exception as e:
        logger.error(f"Error en /cancel: {e}")
        await message.reply_text("❌ Error al cancelar descarga.")

async def process_queue(client, user_id):
    """Procesa la cola del usuario (archivos y URLs)"""
    try:
        total_items = len(user_queues[user_id])
        user_batch_totals[user_id] = total_items
        current_position = 0
        
        while user_queues.get(user_id) and user_queues[user_id]:
            item = user_queues[user_id][0]
            current_position += 1
            
            if isinstance(item, dict) and item.get('type') == 'url':
                await process_single_url(item['url'], item['message'], user_id, current_position, total_items)
            else:
                # Es un mensaje normal de archivo
                await process_single_file(client, item, user_id, current_position, total_items)
            
            await asyncio.sleep(1)
        
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
                
    except Exception as e:
        logger.error(f"Error en process_queue: {e}", exc_info=True)
        if user_id in user_queues:
            user_queues[user_id] = []
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]

async def process_single_url(url, message, user_id, current_position, total_items):
    """Procesa una sola URL para descargar"""
    start_time = time.time()
    
    try:
        # Mensaje de inicio
        initial_msg = await message.reply_text(
            f"🔗 **Iniciando descarga desde URL...**\n\n"
            f"**URL:** `{url}`\n"
            f"**Posición:** {current_position}/{total_items}"
        )
        
        user_current_processing[user_id] = initial_msg.id
        progress_data = {'last_update': 0, 'last_speed': 0}
        
        async def progress_callback(current, total):
            try:
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0
                
                progress_data['last_speed'] = (
                    0.7 * progress_data.get('last_speed', 0) + 0.3 * speed
                )
                smoothed_speed = progress_data['last_speed']
                
                current_time = time.time()
                last_update = progress_data.get('last_update', 0)
                
                if current_time - last_update >= 0.5 or current == total:
                    # Formato de progreso manual
                    percent = min(100, (current / total * 100)) if total > 0 else 0
                    bar_length = 15
                    filled = int(bar_length * current / total) if total > 0 else 0
                    bar = '█' * filled + '░' * (bar_length - filled)
                    
                    # Formatear tamaños
                    current_mb = current / (1024 * 1024)
                    total_mb = total / (1024 * 1024) if total > 0 else 0
                    speed_mb = speed / (1024 * 1024) if speed > 0 else 0
                    
                    progress_text = f"""🔗 **Descargando desde URL...**

**URL:** `{url[:50]}...` 
**Progreso:** `[{bar}] {percent:.1f}%`
**Descargado:** {current_mb:.1f} MB / {total_mb:.1f} MB
**Velocidad:** {speed_mb:.1f} MB/s
**Posición:** {current_position}/{total_items}"""
                    
                    try:
                        await initial_msg.edit_text(progress_text)
                        progress_data['last_update'] = current_time
                    except:
                        pass
                        
            except Exception as e:
                logger.error(f"Error en progress callback URL: {e}")
        
        # Generar nombre temporal para el archivo
        temp_filename = f"url_download_{int(time.time())}"
        user_dir = file_service.get_user_directory(user_id, "downloads")
        file_path = os.path.join(user_dir, temp_filename)
        
        # Descargar desde URL
        success, downloaded, filename = await url_download_service.download_from_url(
            url=url,
            file_path=file_path,
            progress_callback=progress_callback,
            user_id=user_id
        )
        
        if not success:
            await initial_msg.edit_text(f"❌ **Error en descarga:** {downloaded}")
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        
        # Sanitizar nombre
        safe_filename = file_service.sanitize_filename(filename)
        
        # Verificar si el archivo ya existe
        final_path = os.path.join(user_dir, safe_filename)
        counter = 1
        base_name, ext = os.path.splitext(safe_filename)
        while os.path.exists(final_path):
            final_path = os.path.join(user_dir, f"{base_name}_{counter}{ext}")
            counter += 1
        
        # Renombrar archivo temporal al nombre final
        os.rename(file_path, final_path)
        stored_filename = os.path.basename(final_path)
        
        # Registrar archivo
        file_number = file_service.register_file(user_id, filename, stored_filename, "downloads")
        
        # Generar URL de descarga
        download_url = file_service.create_download_url(user_id, stored_filename)
        
        size_mb = os.path.getsize(final_path) / (1024 * 1024)
        
        # Mensaje de éxito
        success_text = f"""✅ **Descarga desde URL completada!**

**Nombre:** `{filename}`
**Tamaño:** {size_mb:.2f} MB
**Número:** #{file_number}

**Enlace de Descarga:**
🔗 [{filename}]({download_url})

**Ubicación:** Carpeta `downloads`"""

        await initial_msg.edit_text(success_text, disable_web_page_preview=True)
        
        # Eliminar de la cola
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]
        
    except Exception as e:
        logger.error(f"Error procesando URL: {e}", exc_info=True)
        try:
            await message.reply_text(f"❌ Error procesando URL: {str(e)}")
        except:
            pass
        
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

async def process_single_file(client, message, user_id, current_position, total_files):
    """Procesa un solo archivo con progreso MEJORADO y descarga rápida"""
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

        user_dir = file_service.get_user_directory(user_id, "downloads")
        
        sanitized_name = file_service.sanitize_filename(original_filename)
        
        stored_filename = sanitized_name
        counter = 1
        base_name, ext = os.path.splitext(sanitized_name)
        file_path = os.path.join(user_dir, stored_filename)
        
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        file_number = file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        logger.info(f"📝 Archivo registrado: #{file_number} - {original_filename} -> {stored_filename}")

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
            if file_size > 0 and final_size < file_size * 0.95:
                logger.warning(f"⚠️ Posible descarga incompleta: esperado {file_size}, obtenido {final_size}")
                await progress_msg.edit_text("⚠️ Advertencia: El archivo podría estar incompleto.")
            
            size_mb = final_size / (1024 * 1024)

            download_url = file_service.create_download_url(user_id, stored_filename)
            logger.info(f"🔗 URL generada: {download_url}")

            files_list = file_service.list_user_files(user_id, "downloads")
            current_file_number = None
            for file_info in files_list:
                if file_info['stored_name'] == stored_filename:
                    current_file_number = file_info['number']
                    break

            queue_info = ""
            next_files_count = len(user_queues[user_id]) - 1 if user_id in user_queues and user_queues[user_id] else 0
            
            if next_files_count > 0:
                queue_info = f"\n\n⏭️ **Siguiente archivo en cola...** ({next_files_count} restantes)"

            success_text = f"""✅ **Archivo #{current_file_number or file_number} Almacenado!**

**Nombre:** `{original_filename}`
**Tipo:** {file_type}
**Tamaño:** {size_mb:.2f} MB

**Enlace de Descarga:**
🔗 [{original_filename}]({download_url})

**Ubicación:** Carpeta `downloads`{queue_info}"""

            await progress_msg.edit_text(success_text, disable_web_page_preview=True)
            
            logger.info(f"✅ Archivo guardado exitosamente: {stored_filename} para usuario {user_id}")

        except Exception as download_error:
            logger.error(f"❌ Error en descarga: {download_error}", exc_info=True)
            await progress_msg.edit_text(f"❌ Error al descargar el archivo: {str(download_error)}")
        
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

    except Exception as e:
        logger.error(f"❌ Error procesando archivo individual: {e}", exc_info=True)
        try:
            await message.reply_text(f"❌ Error procesando archivo: {str(e)}")
        except:
            pass
        
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

async def handle_file_or_url(client, message):
    """Maneja la recepción de archivos o URLs"""
    try:
        user_id = message.from_user.id
        text = message.text or message.caption or ""
        
        # Detectar si el mensaje contiene una URL
        urls = URL_PATTERN.findall(text)
        
        if urls:
            # Es una URL
            for url in urls:
                # Verificar estado del sistema
                system_status = load_manager.get_status()
                if not system_status['can_accept_work']:
                    await message.reply_text(
                        f"⚠️ **Sistema sobrecargado.**\n\n"
                        f"CPU: {system_status['cpu_percent']:.1f}%\n"
                        f"Intenta nuevamente en unos minutos."
                    )
                    return
                
                # Agregar a cola
                if user_id not in user_queues:
                    user_queues[user_id] = []
                
                url_info = {
                    'type': 'url',
                    'url': url,
                    'user_id': user_id,
                    'message': message
                }
                
                user_queues[user_id].append(url_info)
                
                await message.reply_text(
                    f"🔗 **URL agregada a la cola de descarga**\n\n"
                    f"**URL:** `{url}`\n"
                    f"**Posición en cola:** {len(user_queues[user_id])}"
                )
                
                # Si es el único en cola, comenzar procesamiento
                if len(user_queues[user_id]) == 1:
                    await process_queue(client, user_id)
        
        elif message.document or message.video or message.audio or message.photo:
            # Es un archivo normal
            logger.info(f"📥 Archivo recibido de {user_id} - Agregando a cola")
            
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
            
            if user_id not in user_queues:
                user_queues[user_id] = []
            
            user_queues[user_id].append(message)
            
            queue_position = len(user_queues[user_id])
            await message.reply_text(
                f"📥 **Archivo agregado a la cola**\n\n"
                f"**Posición:** {queue_position}\n"
                f"**Total en cola:** {queue_position}\n\n"
                f"Usa `/queue` para ver el estado."
            )
            
            if queue_position == 1:
                await process_queue(client, user_id)
        
    except Exception as e:
        logger.error(f"Error procesando mensaje: {e}", exc_info=True)
        try:
            await message.reply_text("❌ Error al procesar el mensaje.")
        except:
            pass

def setup_handlers(client):
    """Configura todos los handlers del bot"""
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    
    client.on_message(filters.command("cd") & filters.private)(cd_command)
    client.on_message(filters.command("list") & filters.private)(list_command)
    client.on_message(filters.command("delete") & filters.private)(delete_command)
    client.on_message(filters.command("clear") & filters.private)(clear_command)
    client.on_message(filters.command("rename") & filters.private)(rename_command)
    
    client.on_message(filters.command("pack") & filters.private)(pack_command)
    
    client.on_message(filters.command("queue") & filters.private)(queue_command)
    client.on_message(filters.command("clearqueue") & filters.private)(clear_queue_command)
    
    # NUEVOS COMANDOS PARA URLS
    client.on_message(filters.command("dl") & filters.private)(download_url_command)
    client.on_message(filters.command("cancel") & filters.private)(cancel_download_command)
    
    client.on_message(filters.command("cleanup") & filters.private)(cleanup_command)
    
    # Handler universal para archivos y URLs
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo | filters.text) &
        filters.private
    )(handle_file_or_url)