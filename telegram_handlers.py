import os
import time
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message

from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB
from load_manager import load_manager
from file_service import async_file_service
from progress_service import progress_service
from packing_service import async_packing_service
from download_service import fast_download_service

logger = logging.getLogger(__name__)

# Variables globales
user_sessions = {}
user_queues = {}
user_current_processing = {}
user_batch_totals = {}

def get_user_session(user_id):
    """Obtiene o crea sesión del usuario"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {'current_folder': 'downloads'}
    return user_sessions[user_id]

# ===== COMANDOS BÁSICOS =====

async def start_command(client, message):
    """Comando /start optimizado"""
    try:
        user = message.from_user
        
        welcome_text = f"""👋 **Hola {user.first_name}!**

🤖 **File2Link Bot**
_Almacena y obtén enlaces directos_

**COMANDOS PRINCIPALES:**
• `/list` - Ver archivos
• `/cd [folder]` - Cambiar carpeta
• `/pack [MB]` - Empaquetar

**ENVÍA ARCHIVOS** para almacenarlos automáticamente.

📏 **Límite:** {MAX_FILE_SIZE_MB} MB"""

        await message.reply_text(welcome_text)
        logger.info(f"Nuevo usuario: {user.id}")

    except Exception as e:
        await message.reply_text("❌ Error inicializando. Intenta de nuevo.")

async def help_command(client, message):
    """Comando /help optimizado"""
    try:
        help_text = f"""📚 **Ayuda Rápida**

**📁 NAVEGACIÓN:**
`/cd downloads` - Archivos descargados
`/cd packed` - Archivos empaquetados

**📄 GESTIÓN:**
`/list` - Listar archivos
`/delete N` - Eliminar archivo
`/rename N nombre` - Renombrar
`/clear` - Vaciar carpeta

**📦 EMPAQUETADO:**
`/pack` - Crear ZIP único
`/pack 100` - Dividir en partes de 100MB

**📊 ESTADO:**
`/status` - Ver uso y sistema

📏 **Límite:** {MAX_FILE_SIZE_MB} MB"""

        await message.reply_text(help_text)

    except Exception as e:
        await message.reply_text("❌ Error.")

async def cd_command(client, message):
    """Comando /cd - Cambiar carpeta"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        args = message.text.split()
        
        if len(args) == 1:
            current = session['current_folder']
            await message.reply_text(f"📂 **Carpeta:** `{current}`")
        else:
            folder = args[1].lower()
            if folder in ['downloads', 'packed']:
                session['current_folder'] = folder
                await message.reply_text(f"📂 **Cambiado a:** `{folder}`")
            else:
                await message.reply_text(
                    "❌ **Carpetas disponibles:**\n"
                    "• `downloads`\n"
                    "• `packed`"
                )

    except Exception as e:
        logger.error(f"Error /cd: {e}")
        await message.reply_text("❌ Error.")

async def list_command(client, message):
    """Comando /list optimizado y asíncrono"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        files = await async_file_service.list_user_files(user_id, current_folder)
        
        if not files:
            folder_name = "📥 Descargas" if current_folder == "downloads" else "📦 Empaquetados"
            await message.reply_text(f"{folder_name} está vacía.")
            return
        
        # Máximo 8 archivos por mensaje
        files_to_show = files[:8]
        
        folder_display = "📥 DESCARGAS" if current_folder == "downloads" else "📦 EMPAQUETADOS"
        files_text = f"**{folder_display}**\n"
        files_text += f"({len(files)} archivos)\n\n"
        
        for file_info in files_to_show:
            size = file_info['size_mb']
            name = file_info['name']
            if len(name) > 20:
                name = name[:17] + "..."
            files_text += f"**#{file_info['number']}** - `{name}`\n"
            files_text += f"   📏 {size:.1f}MB\n\n"
        
        if len(files) > 8:
            files_text += f"\n... y {len(files) - 8} más."
        
        files_text += f"\n**Comandos:** `/delete N` | `/rename N nombre`"
        
        await message.reply_text(files_text, disable_web_page_preview=True)

    except Exception as e:
        logger.error(f"Error /list: {e}")
        await message.reply_text("❌ Error listando archivos.")

async def delete_command(client, message):
    """Comando /delete asíncrono"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split()
        
        if len(args) < 2:
            await message.reply_text("❌ **Uso:** `/delete <número>`")
            return
        
        try:
            file_number = int(args[1])
        except:
            await message.reply_text("❌ Número inválido.")
            return
        
        success, result_message = await async_file_service.delete_file_by_number(
            user_id, file_number, current_folder
        )
        
        if success:
            await message.reply_text(f"✅ **{result_message}**")
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error /delete: {e}")
        await message.reply_text("❌ Error.")

async def clear_command(client, message):
    """Comando /clear - Vaciar carpeta"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        success, result_message = await async_file_service.delete_all_files(user_id, current_folder)
        
        if success:
            await message.reply_text(f"✅ **{result_message}**")
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error /clear: {e}")
        await message.reply_text("❌ Error.")

async def rename_command(client, message):
    """Comando /rename - Renombrar archivo"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        args = message.text.split(maxsplit=2)
        
        if len(args) < 3:
            await message.reply_text("❌ **Uso:** `/rename <número> <nombre>`")
            return
        
        try:
            file_number = int(args[1])
        except:
            await message.reply_text("❌ Número inválido.")
            return
        
        new_name = args[2].strip()
        
        if not new_name:
            await message.reply_text("❌ Nombre vacío.")
            return
        
        success, result_message, new_url = await async_file_service.rename_file(
            user_id, file_number, new_name, current_folder
        )
        
        if success:
            response_text = f"✅ **{result_message}**\n\n"
            response_text += f"**Nuevo enlace:**\n"
            response_text += f"🔗 [{new_name}]({new_url})"
            
            await message.reply_text(response_text, disable_web_page_preview=True)
        else:
            await message.reply_text(f"❌ **{result_message}**")
            
    except Exception as e:
        logger.error(f"Error /rename: {e}")
        await message.reply_text("❌ Error.")

async def status_command(client, message):
    """Comando /status - Estado del sistema"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        
        downloads = await async_file_service.list_user_files(user_id, "downloads")
        packed = await async_file_service.list_user_files(user_id, "packed")
        
        downloads_count = len(downloads)
        packed_count = len(packed)
        
        total_size = await async_file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        system_status = load_manager.get_status()
        
        status_text = f"""**📊 ESTADO - {message.from_user.first_name}**

**👤 USUARIO:**
• **ID:** `{user_id}`
• **Carpeta:** `{session['current_folder']}`
• **Archivos:** {downloads_count} descargas, {packed_count} empaquetados
• **Espacio:** {size_mb:.2f} MB

**📏 CONFIGURACIÓN:**
• **Límite:** {MAX_FILE_SIZE_MB} MB

**🖥️ SISTEMA:**
• **CPU:** {system_status['cpu_percent']:.1f}%
• **Memoria:** {system_status['memory_percent']:.1f}%
• **Estado:** {"✅ ACTIVO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}"""
        
        await message.reply_text(status_text)
        
    except Exception as e:
        logger.error(f"Error /status: {e}")
        await message.reply_text("❌ Error.")

# ===== EMPAQUETADO =====

async def pack_command(client, message):
    """Comando /pack completamente asíncrono"""
    try:
        user_id = message.from_user.id
        
        # Verificar archivos asíncronamente
        files = await async_file_service.list_user_files(user_id, "downloads")
        if not files:
            await message.reply_text("📭 No hay archivos para empaquetar.")
            return
        
        command_parts = message.text.split()
        split_size = None
        
        if len(command_parts) > 1:
            try:
                split_size = int(command_parts[1])
                if split_size <= 0 or split_size > 200:
                    await message.reply_text("❌ Usa `/pack 100` (1-200 MB)")
                    return
            except:
                await message.reply_text("❌ Usa `/pack` o `/pack 100`")
                return
        
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado.**\n"
                f"CPU: {system_status['cpu_percent']:.1f}%"
            )
            return
        
        status_msg = await message.reply_text("📦 **Empaquetando...**")
        
        files, status_message = await async_packing_service.pack_folder(user_id, split_size)
        
        if not files:
            await status_msg.edit_text(f"❌ {status_message}")
            return
        
        if len(files) == 1:
            file_info = files[0]
            
            response_text = f"""✅ **Empaquetado completado**

📦 `{file_info['filename']}`
📏 {file_info['size_mb']:.1f} MB
🔗 [Descargar]({file_info['url']})"""
            
            await status_msg.edit_text(response_text, disable_web_page_preview=True)
            
        else:
            total_size = sum(f['size_mb'] for f in files)
            
            response_text = f"""✅ **Empaquetado en {len(files)} partes**

📦 {len(files)} archivos
📏 {total_size:.1f} MB total

**Enlaces:**"""
            
            for file_info in files:
                response_text += f"\n\n**Parte {file_info['number']}:**"
                response_text += f"\n🔗 [{file_info['filename']}]({file_info['url']})"
            
            if len(response_text) > 4000:
                await status_msg.edit_text(f"✅ {len(files)} partes creadas")
                
                for file_info in files:
                    await message.reply_text(
                        f"**Parte {file_info['number']}:**\n🔗 [{file_info['filename']}]({file_info['url']})",
                        disable_web_page_preview=True
                    )
            else:
                await status_msg.edit_text(response_text, disable_web_page_preview=True)
                
        logger.info(f"Empaquetado: usuario {user_id}, {len(files)} archivos")
        
    except Exception as e:
        logger.error(f"Error /pack: {e}")
        await message.reply_text("❌ Error empaquetando.")

# ===== COLA DE DESCARGAS =====

async def queue_command(client, message):
    """Comando /queue - Ver cola"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola vacía**")
            return
        
        queue_size = len(user_queues[user_id])
        
        queue_text = f"📋 **Cola - {queue_size} archivo(s)**\n\n"
        
        for i, msg in enumerate(user_queues[user_id][:5]):  # Mostrar solo 5
            file_info = "Desconocido"
            if msg.document:
                name = msg.document.file_name or 'Documento'
                if len(name) > 20:
                    name = name[:17] + "..."
                file_info = f"📄 {name}"
            elif msg.video:
                name = msg.video.file_name or 'Video'
                if len(name) > 20:
                    name = name[:17] + "..."
                file_info = f"🎥 {name}"
            elif msg.audio:
                name = msg.audio.file_name or 'Audio'
                if len(name) > 20:
                    name = name[:17] + "..."
                file_info = f"🎵 {name}"
            elif msg.photo:
                file_info = f"🖼️ Foto"
            
            queue_text += f"**#{i+1}** - {file_info}\n"
        
        if queue_size > 5:
            queue_text += f"\n... y {queue_size - 5} más."
        
        await message.reply_text(queue_text)
        
    except Exception as e:
        logger.error(f"Error /queue: {e}")
        await message.reply_text("❌ Error.")

async def clear_queue_command(client, message):
    """Comando /clearqueue - Limpiar cola"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola ya vacía**")
            return
        
        queue_size = len(user_queues[user_id])
        user_queues[user_id] = []
        
        if user_id in user_current_processing:
            del user_current_processing[user_id]
        
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n{queue_size} archivos removidos.")
        
    except Exception as e:
        logger.error(f"Error /clearqueue: {e}")
        await message.reply_text("❌ Error.")

async def cleanup_command(client, message):
    """Comando /cleanup - Limpiar archivos"""
    try:
        user_id = message.from_user.id
        
        total_size = await async_file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        await message.reply_text(
            f"🧹 **Espacio utilizado:** {size_mb:.2f} MB\n"
            f"Usa `/delete` o `/clear` para gestionar archivos."
        )
        
    except Exception as e:
        logger.error(f"Error /cleanup: {e}")
        await message.reply_text("❌ Error.")

# ===== MANEJO DE ARCHIVOS =====

async def handle_file(client, message):
    """Maneja recepción de archivos"""
    try:
        user = message.from_user
        user_id = user.id

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
                f"❌ **Archivo demasiado grande**\n\n"
                f"Máximo: {MAX_FILE_SIZE_MB} MB\n"
                f"Tuyo: {async_file_service.format_bytes(file_size)}"
            )
            return

        if user_id not in user_queues:
            user_queues[user_id] = []
        
        user_queues[user_id].append(message)
        
        if len(user_queues[user_id]) == 1:
            await process_file_queue(client, user_id)
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}")
        try:
            await message.reply_text("❌ Error.")
        except:
            pass

async def process_file_queue(client, user_id):
    """Procesa cola de archivos"""
    try:
        total_files_in_batch = len(user_queues[user_id])
        user_batch_totals[user_id] = total_files_in_batch
        
        current_position = 0
        
        while user_queues.get(user_id) and user_queues[user_id]:
            message = user_queues[user_id][0]
            current_position += 1
            
            logger.info(f"Procesando {current_position}/{total_files_in_batch} para {user_id}")
            
            await process_single_file(client, message, user_id, current_position, total_files_in_batch)
            
            await asyncio.sleep(1)
        
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
                
    except Exception as e:
        logger.error(f"Error process_file_queue: {e}")
        if user_id in user_queues:
            user_queues[user_id] = []
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]

async def process_single_file(client, message, user_id, current_position, total_files):
    """Procesa un solo archivo de forma asíncrona optimizada"""
    start_time = time.time()
    
    try:
        file_obj = None
        file_type = None
        original_filename = None
        file_size = 0

        if message.document:
            file_obj = message.document
            file_type = "documento"
            original_filename = message.document.file_name or "archivo"
            file_size = file_obj.file_size or 0
        elif message.video:
            file_obj = message.video
            file_type = "video"
            original_filename = message.video.file_name or "video.mp4"
            file_size = file_obj.file_size or 0
        elif message.audio:
            file_obj = message.audio
            file_type = "audio"
            original_filename = message.audio.file_name or "audio.mp3"
            file_size = file_obj.file_size or 0
        elif message.photo:
            file_obj = message.photo[-1]
            file_type = "foto"
            original_filename = f"foto_{message.id}.jpg"
            file_size = file_obj.file_size or 0
        else:
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            return

        if not file_obj:
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            await message.reply_text("❌ Error: Archivo no identificado.")
            return

        # Verificar cuota antes de descargar
        can_download, quota_message = await async_file_service.check_user_quota(user_id, file_size)
        if not can_download:
            await message.reply_text(f"❌ **{quota_message}**")
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            return
        
        user_dir = await async_file_service.get_user_directory(user_id, "downloads")
        
        sanitized_name = async_file_service.sanitize_filename(original_filename)
        
        stored_filename = sanitized_name
        counter = 1
        base_name, ext = os.path.splitext(sanitized_name)
        file_path = os.path.join(user_dir, stored_filename)
        
        loop = asyncio.get_event_loop()
        while await loop.run_in_executor(None, os.path.exists, file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        file_number = await async_file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        logger.info(f"Registrado: #{file_number} - {original_filename}")

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
                    except:
                        pass

            except Exception as e:
                logger.error(f"Error callback: {e}")

        try:
            logger.info(f"Descargando: {original_filename}")
            
            success, downloaded = await fast_download_service.download_with_retry(
                client=client,
                message=message,
                file_path=file_path,
                progress_callback=progress_callback
            )

            if not success or not os.path.exists(file_path):
                await progress_msg.edit_text("❌ Error en descarga.")
                if user_id in user_queues and user_queues[user_id]:
                    user_queues[user_id].pop(0)
                return

            final_size = await loop.run_in_executor(None, os.path.getsize, file_path)
            size_mb = final_size / (1024 * 1024)
            
            await async_file_service.update_file_size(user_id, file_number, final_size, "downloads")

            download_url = await async_file_service.create_download_url(user_id, stored_filename)
            
            files_list = await async_file_service.list_user_files(user_id, "downloads")
            current_file_number = None
            for file_info in files_list:
                if file_info['stored_name'] == stored_filename:
                    current_file_number = file_info['number']
                    break

            next_files_count = len(user_queues[user_id]) - 1 if user_id in user_queues and user_queues[user_id] else 0
            
            queue_info = ""
            if next_files_count > 0:
                queue_info = f"\n\n⏭️ **Siguiente archivo...** ({next_files_count} restantes)"

            success_text = f"""✅ **Archivo #{current_file_number or file_number} Almacenado!**

**Nombre:** `{original_filename}`
**Tipo:** {file_type}
**Tamaño:** {size_mb:.2f} MB

**Enlace:**
🔗 [{original_filename}]({download_url}){queue_info}"""

            await progress_msg.edit_text(success_text, disable_web_page_preview=True)
            
            logger.info(f"✅ Archivo guardado: {stored_filename}")

        except Exception as download_error:
            logger.error(f"❌ Error descarga: {download_error}")
            await progress_msg.edit_text("❌ Error al descargar.")
        
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

    except Exception as e:
        logger.error(f"❌ Error procesando archivo: {e}")
        try:
            await message.reply_text(f"❌ Error: {str(e)[:100]}")
        except:
            pass
        
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        if user_id in user_current_processing:
            del user_current_processing[user_id]

# ===== CONFIGURACIÓN DE HANDLERS =====

def setup_handlers(client):
    """Configura todos los handlers"""
    commands = [
        ("start", start_command),
        ("help", help_command),
        ("status", status_command),
        ("cd", cd_command),
        ("list", list_command),
        ("delete", delete_command),
        ("clear", clear_command),
        ("rename", rename_command),
        ("pack", pack_command),
        ("queue", queue_command),
        ("clearqueue", clear_queue_command),
        ("cleanup", cleanup_command)
    ]
    
    for cmd, handler in commands:
        client.on_message(filters.command(cmd) & filters.private)(handler)
    
    # Handler para archivos
    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) &
        filters.private
    )(handle_file)