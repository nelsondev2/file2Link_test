import os
import time
import asyncio
import logging
import traceback
from pyrogram import filters
from pyrogram.types import Message
from config import MAX_FILE_SIZE_MB, MAX_FILE_SIZE, BASE_DIR
from load_manager import load_manager
from file_service import file_service
from download_service import fast_download_service
from packing_service import packing_service
from progress_service import progress_service

logger = logging.getLogger(__name__)

# Variables globales para gestión de cola
user_queues = {}  # {user_id: {'queue': [], 'active': False, 'last_activity': time.time()}}
MAX_QUEUE_SIZE = 20
MAX_CONCURRENT_UPLOADS = 2

def setup_handlers(app):
    """Configura todos los handlers del bot"""
    
    # ===== COMANDO /start =====
    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message: Message):
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "Usuario"
        
        # Registrar usuario si es nuevo
        file_service.add_user(user_id, user_name)
        
        welcome_text = f"""
🤖 **Nelson File2Link - V2 Mejorado**

¡Hola {user_name}! 👋

✨ **Características principales:**
• 📤 Sube archivos hasta **{MAX_FILE_SIZE_MB} MB**
• 🔒 URLs seguras con hash único (12 caracteres)
• 📦 Empaqueta múltiples archivos en ZIP
• ⚡ Descargas rápidas optimizadas
• 📊 Gestión completa de tus archivos

📁 **Comandos disponibles:**
• `/list` - Ver tus archivos
• `/pack` - Empaquetar en ZIP
• `/pack 100` - Dividir en partes de 100MB
• `/cd downloads` - Carpeta de descargas
• `/cd packed` - Carpeta empaquetados
• `/rename 3 nuevo` - Renombrar archivo #3
• `/delete 5` - Eliminar archivo #5
• `/clear` - Vaciar carpeta actual
• `/status` - Estado del sistema
• `/about` - Información técnica

⚠️ **Límites:**
• Máximo {MAX_QUEUE_SIZE} archivos en cola
• Máximo {MAX_CONCURRENT_UPLOADS} subidas simultáneas
• Archivos expiran después de 30 días

📤 **¡Envía cualquier archivo para comenzar!**
"""
        await message.reply_text(welcome_text, quote=True)
    
    # ===== COMANDO /status =====
    @app.on_message(filters.command("status") & filters.private)
    async def status_command(client, message: Message):
        try:
            # Obtener estadísticas del sistema
            system_health = load_manager.get_system_health()
            load_status = load_manager.get_status()
            download_stats = fast_download_service.get_stats()
            
            # Estadísticas de usuario
            user_id = message.from_user.id
            user_files_downloads = len(file_service.list_user_files(user_id, "downloads"))
            user_files_packed = len(file_service.list_user_files(user_id, "packed"))
            user_storage = file_service.get_user_storage_usage(user_id)
            user_storage_mb = user_storage / (1024 * 1024)
            
            # Formato legible
            total_users = file_service.total_users_count()
            total_storage = 0
            total_files = 0
            
            # Calcular estadísticas globales (sin broadcast)
            try:
                for user_dir in os.listdir(BASE_DIR):
                    user_path = os.path.join(BASE_DIR, user_dir)
                    if os.path.isdir(user_path) and user_dir.isdigit():
                        for root, dirs, files in os.walk(user_path):
                            total_files += len(files)
                            for file in files:
                                file_path = os.path.join(root, file)
                                total_storage += os.path.getsize(file_path)
            except Exception as e:
                logger.error(f"Error calculando estadísticas globales: {e}")
            
            total_storage_mb = total_storage / (1024 * 1024)
            
            status_text = f"""
📊 **Estado del Sistema**

⚙️ **Carga del Sistema:**
• CPU: {system_health['cpu']['percent']:.1f}% (límite: {system_health['cpu']['limit']}%)
• Memoria: {system_health['memory']['percent']:.1f}% ({system_health['memory']['available_gb']:.1f}GB libres)
• Disco: {system_health['disk']['percent']:.1f}% ({system_health['disk']['free_gb']:.1f}GB libres)
• Procesos activos: {load_status['active_processes']}/{load_status['max_processes']}

📁 **Tu Almacenamiento:**
• Archivos en downloads: {user_files_downloads}
• Archivos empaquetados: {user_files_packed}
• Espacio usado: {user_storage_mb:.1f} MB

🌍 **Estadísticas Globales:**
• Usuarios totales: {total_users}
• Archivos totales: {total_files}
• Almacenamiento total: {total_storage_mb:.1f} MB

⚡ **Rendimiento:**
• Descargas exitosas: {download_stats['successful']}
• Descargas fallidas: {download_stats['failed']}
• Tiempo activo: {load_status['uptime']}

🛡️ **Seguridad:**
• Hashes activos: {len(file_service.file_hashes)}
• Expiración de hashes: {file_service.HASH_EXPIRE_DAYS} días
"""
            await message.reply_text(status_text, quote=True)
            
        except Exception as e:
            logger.error(f"Error en /status: {e}", exc_info=True)
            await message.reply_text("❌ Error al obtener el estado del sistema", quote=True)
    
    # ===== COMANDO /about =====
    @app.on_message(filters.command("about") & filters.private)
    async def about_command(client, message: Message):
        about_text = f"""
🤖 **Nelson File2Link - V2 Mejorado**

🔐 **Seguridad Profesional:**
• URLs con hash único de 12 caracteres (MD5)
• Expiración automática después de {file_service.HASH_EXPIRE_DAYS} días
• Sistema idéntico al primer bot profesional
• Protección contra path traversal

📁 **Gestión de Archivos:**
• Sistema de numeración persistente (#1, #2, #3...)
• Renombrado y eliminación con reasignación automática
• Empaquetado ZIP sin compresión (máxima velocidad)
• División en partes crudas (.001, .002, .003...)

⚡ **Optimizaciones:**
• Descargas con buffer optimizado (128KB chunks)
• Sistema de cola anti-abuso ({MAX_QUEUE_SIZE} archivos máx.)
• Límite de {MAX_CONCURRENT_UPLOADS} subidas simultáneas
• Optimizado para Render.com (512MB RAM)

📊 **Estadísticas en Tiempo Real:**
• Barra de progreso con ETA
• Velocidad de descarga en MB/s
• Uso de CPU/Memoria/DISCO en /status

🌐 **Endpoints Web:**
• `/` - Página principal
• `/health` - Health check
• `/system-status` - Estado detallado
• `/api/stats` - Estadísticas JSON
• `/files` - Explorador de archivos

⚠️ **Nota Importante:**
Este bot NO incluye sistema de broadcast/administración.
Enfoque 100% en funcionalidad principal y seguridad.

© 2024 - Nelson File2Link V2 Mejorado
"""
        await message.reply_text(about_text, quote=True)
    
    # ===== COMANDO /list =====
    @app.on_message(filters.command("list") & filters.private)
    async def list_command(client, message: Message):
        user_id = message.from_user.id
        
        # Determinar carpeta actual (downloads por defecto)
        user_key = f"{user_id}_current_dir"
        current_dir = file_service.metadata.get(user_key, "downloads")
        
        files = file_service.list_user_files(user_id, current_dir)
        
        if not files:
            await message.reply_text(
                f"📭 Carpeta `{current_dir}` vacía\n\nUsa `/cd downloads` o `/cd packed` para cambiar de carpeta",
                quote=True
            )
            return
        
        # Paginación (máximo 10 archivos por mensaje)
        page = 1
        page_size = 10
        total_pages = (len(files) + page_size - 1) // page_size
        
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        page_files = files[start_idx:end_idx]
        
        list_text = f"📁 **Archivos en `{current_dir}`** (Página {page}/{total_pages})\n\n"
        
        for file in page_files:
            size_str = file_service.format_bytes(file['size'])
            list_text += f"`#{file['number']}` **{file['name']}** ({size_str})\n"
        
        list_text += f"\n✅ Total: {len(files)} archivos"
        
        await message.reply_text(list_text, quote=True)
    
    # ===== COMANDO /cd (change directory) =====
    @app.on_message(filters.command("cd") & filters.private)
    async def cd_command(client, message: Message):
        user_id = message.from_user.id
        parts = message.text.split(maxsplit=1)
        
        if len(parts) < 2:
            await message.reply_text("❌ Uso: `/cd downloads` o `/cd packed`", quote=True)
            return
        
        target_dir = parts[1].strip().lower()
        
        if target_dir not in ["downloads", "packed"]:
            await message.reply_text("❌ Carpeta inválida. Usa `downloads` o `packed`", quote=True)
            return
        
        # Guardar carpeta actual en metadata
        user_key = f"{user_id}_current_dir"
        file_service.metadata[user_key] = target_dir
        file_service.save_metadata()
        
        # Listar archivos en la nueva carpeta
        files = file_service.list_user_files(user_id, target_dir)
        count = len(files)
        
        await message.reply_text(
            f"✅ Carpeta cambiada a `{target_dir}`\n\nArchivos: {count}\nUsa `/list` para verlos",
            quote=True
        )
    
    # ===== COMANDO /rename =====
    @app.on_message(filters.command("rename") & filters.private)
    async def rename_command(client, message: Message):
        user_id = message.from_user.id
        parts = message.text.split(maxsplit=2)
        
        if len(parts) < 3:
            await message.reply_text(
                "❌ Uso: `/rename <número> <nuevo_nombre>`\nEj: `/rename 3 documento.pdf`",
                quote=True
            )
            return
        
        try:
            file_number = int(parts[1])
            new_name = parts[2].strip()
        except ValueError:
            await message.reply_text("❌ El número debe ser un entero válido", quote=True)
            return
        
        # Determinar carpeta actual
        user_key = f"{user_id}_current_dir"
        current_dir = file_service.metadata.get(user_key, "downloads")
        
        success, msg, new_url = file_service.rename_file(user_id, file_number, new_name, current_dir)
        
        if success:
            await message.reply_text(
                f"✅ {msg}\n\n🔗 Nuevo enlace:\n`{new_url}`",
                quote=True
            )
        else:
            await message.reply_text(f"❌ {msg}", quote=True)
    
    # ===== COMANDO /delete =====
    @app.on_message(filters.command("delete") & filters.private)
    async def delete_command(client, message: Message):
        user_id = message.from_user.id
        parts = message.text.split(maxsplit=1)
        
        if len(parts) < 2:
            await message.reply_text(
                "❌ Uso: `/delete <número>`\nEj: `/delete 5`",
                quote=True
            )
            return
        
        try:
            file_number = int(parts[1])
        except ValueError:
            await message.reply_text("❌ El número debe ser un entero válido", quote=True)
            return
        
        # Determinar carpeta actual
        user_key = f"{user_id}_current_dir"
        current_dir = file_service.metadata.get(user_key, "downloads")
        
        success, msg = file_service.delete_file_by_number(user_id, file_number, current_dir)
        
        if success:
            await message.reply_text(f"✅ {msg}", quote=True)
        else:
            await message.reply_text(f"❌ {msg}", quote=True)
    
    # ===== COMANDO /clear =====
    @app.on_message(filters.command("clear") & filters.private)
    async def clear_command(client, message: Message):
        user_id = message.from_user.id
        
        # Determinar carpeta actual
        user_key = f"{user_id}_current_dir"
        current_dir = file_service.metadata.get(user_key, "downloads")
        
        success, msg = file_service.delete_all_files(user_id, current_dir)
        
        if success:
            await message.reply_text(f"✅ {msg}", quote=True)
        else:
            await message.reply_text(f"❌ {msg}", quote=True)
    
    # ===== COMANDO /pack =====
    @app.on_message(filters.command("pack") & filters.private)
    async def pack_command(client, message: Message):
        user_id = message.from_user.id
        parts = message.text.split(maxsplit=1)
        
        # Verificar si hay archivos para empaquetar
        downloads = file_service.list_user_files(user_id, "downloads")
        if not downloads:
            await message.reply_text("❌ No tienes archivos en la carpeta `downloads` para empaquetar", quote=True)
            return
        
        # Verificar carga del sistema
        can_start, msg = load_manager.can_start_process()
        if not can_start:
            await message.reply_text(f"⚠️ {msg}", quote=True)
            return
        
        # Determinar si se especificó tamaño de división
        split_size = None
        if len(parts) > 1:
            try:
                split_size = int(parts[1])
                if split_size < 10 or split_size > 2000:
                    await message.reply_text(
                        "❌ Tamaño de división inválido. Debe estar entre 10 y 2000 MB",
                        quote=True
                    )
                    return
            except ValueError:
                await message.reply_text(
                    "❌ El tamaño debe ser un número entero (MB)\nEj: `/pack 100`",
                    quote=True
                )
                return
        
        # Iniciar empaquetado
        msg = await message.reply_text(
            f"📦 Empaquetando {len(downloads)} archivos...\n" +
            (f"Dividiendo en partes de {split_size}MB" if split_size else "Creando ZIP único"),
            quote=True
        )
        
        try:
            if split_size:
                result, status_msg = await asyncio.to_thread(
                    packing_service.pack_folder, user_id, split_size
                )
            else:
                result, status_msg = await asyncio.to_thread(
                    packing_service.pack_folder, user_id
                )
            
            if result is None:
                await msg.edit(f"❌ Error al empaquetar:\n{status_msg}")
                return
            
            # Mostrar resultados
            response = f"✅ {status_msg}\n\n**Archivos generados:**\n"
            for file_info in result:
                response += f"\n`#{file_info['number']}` **{file_info['filename']}** ({file_info['size_mb']:.1f} MB)"
                if 'url' in file_info and file_info['url']:
                    response += f"\n🔗 `{file_info['url']}`"
            
            await msg.edit(response)
            
        except Exception as e:
            logger.error(f"Error en /pack: {e}", exc_info=True)
            await msg.edit(f"❌ Error crítico al empaquetar:\n{str(e)}")
    
    # ===== MANEJADOR DE ARCHIVOS (document, video, audio, photo) =====
    @app.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
    async def handle_file_upload(client, message: Message):
        user_id = message.from_user.id
        user_name = message.from_user.first_name or "Usuario"
        
        # Registrar usuario si es nuevo
        file_service.add_user(user_id, user_name)
        
        # Obtener información del archivo
        if message.document:
            file_obj = message.document
            file_name = file_obj.file_name or f"file_{int(time.time())}"
            file_size = file_obj.file_size or 0
        elif message.video:
            file_obj = message.video
            file_name = file_obj.file_name or f"video_{int(time.time())}.mp4"
            file_size = file_obj.file_size or 0
        elif message.audio:
            file_obj = message.audio
            file_name = file_obj.file_name or f"audio_{int(time.time())}.mp3"
            file_size = file_obj.file_size or 0
        elif message.photo:
            file_obj = message.photo[-1]  # La más grande
            file_name = f"photo_{int(time.time())}.jpg"
            file_size = file_obj.file_size or 0
        else:
            await message.reply_text("❌ Tipo de archivo no soportado", quote=True)
            return
        
        # Verificar tamaño máximo
        if file_size > MAX_FILE_SIZE:
            await message.reply_text(
                f"❌ Archivo demasiado grande ({file_size/(1024*1024):.1f} MB)\n"
                f"Límite: {MAX_FILE_SIZE_MB} MB",
                quote=True
            )
            return
        
        # Verificar cola del usuario
        if user_id not in user_queues:
            user_queues[user_id] = {'queue': [], 'active': False, 'last_activity': time.time()}
        
        queue_info = user_queues[user_id]
        
        # Limpiar cola inactiva (> 1 hora)
        if time.time() - queue_info['last_activity'] > 3600:
            queue_info['queue'] = []
            queue_info['active'] = False
        
        queue_info['last_activity'] = time.time()
        
        # Verificar límite de cola
        if len(queue_info['queue']) >= MAX_QUEUE_SIZE:
            await message.reply_text(
                f"❌ Límite de cola alcanzado ({len(queue_info['queue'])}/{MAX_QUEUE_SIZE})\n"
                "Espera a que se procesen los archivos actuales",
                quote=True
            )
            return
        
        # Añadir a cola
        position = len(queue_info['queue']) + 1
        queue_info['queue'].append({
            'message': message,
            'file_name': file_name,
            'file_size': file_size,
            'position': position
        })
        
        # Confirmación inmediata
        await message.reply_text(
            f"✅ Archivo añadido a la cola\n"
            f"Posición: #{position}/{len(queue_info['queue'])}\n"
            f"Tamaño: {file_size/(1024*1024):.1f} MB\n\n"
            f"⏳ Espera tu turno para la descarga...",
            quote=True
        )
        
        # Procesar cola si no hay procesos activos
        if not queue_info['active']:
            await process_user_queue(client, user_id)
    
    # ===== FUNCIÓN AUXILIAR: Procesar cola de usuario =====
    async def process_user_queue(client, user_id):
        if user_id not in user_queues:
            return
        
        queue_info = user_queues[user_id]
        queue_info['active'] = True
        
        while queue_info['queue']:
            # Verificar límite global de concurrencia
            can_accept, msg = load_manager.can_accept_upload(
                user_id, 
                len(queue_info['queue'])
            )
            
            if not can_accept:
                logger.warning(f"Usuario {user_id} bloqueado temporalmente: {msg}")
                await asyncio.sleep(5)
                continue
            
            # Obtener siguiente archivo
            job = queue_info['queue'].pop(0)
            message = job['message']
            file_name = job['file_name']
            file_size = job['file_size']
            position = job['position']
            
            try:
                # Crear directorio y ruta
                user_dir = file_service.get_user_directory(user_id, "downloads")
                safe_filename = file_service.sanitize_filename(file_name)
                file_path = os.path.join(user_dir, safe_filename)
                
                # Verificar si ya existe (evitar sobrescritura)
                counter = 1
                base_name, ext = os.path.splitext(safe_filename)
                while os.path.exists(file_path):
                    safe_filename = f"{base_name}_{counter}{ext}"
                    file_path = os.path.join(user_dir, safe_filename)
                    counter += 1
                
                # Callback de progreso
                start_time = time.time()
                last_update = start_time
                last_downloaded = 0
                
                async def progress_callback(downloaded, total):
                    nonlocal last_update, last_downloaded
                    
                    current_time = time.time()
                    if current_time - last_update < 0.5:
                        return
                    
                    # Calcular velocidad
                    elapsed = current_time - last_update
                    if elapsed > 0:
                        speed = (downloaded - last_downloaded) / elapsed
                    else:
                        speed = 0
                    
                    # Actualizar mensaje de progreso
                    progress_msg = progress_service.create_progress_message(
                        filename=safe_filename,
                        current=downloaded,
                        total=total,
                        speed=speed,
                        user_first_name=message.from_user.first_name,
                        process_type="Descargando",
                        current_file=position,
                        total_files=len(queue_info['queue']) + 1
                    )
                    
                    try:
                        await message.edit_text(progress_msg)
                    except Exception:
                        pass  # Ignorar errores de edición
                    
                    last_update = current_time
                    last_downloaded = downloaded
                
                # Descargar archivo
                msg = await message.reply_text(
                    f"⏬ Iniciando descarga: `{safe_filename}`\n"
                    f"Tamaño: {file_size/(1024*1024):.1f} MB",
                    quote=True
                )
                
                success, downloaded = await fast_download_service.download_with_retry(
                    client, message, file_path, progress_callback
                )
                
                if not success:
                    await msg.edit_text(
                        f"❌ Falló la descarga de `{safe_filename}`\n"
                        "Intenta enviar el archivo nuevamente"
                    )
                    continue
                
                # Registrar archivo
                file_num = file_service.register_file(
                    user_id, 
                    original_name=file_name,
                    stored_name=safe_filename,
                    file_type="downloads"
                )
                
                # Generar URL segura
                download_url = file_service.create_download_url(user_id, safe_filename)
                
                # Enviar resultado
                size_str = file_service.format_bytes(downloaded)
                await msg.edit_text(
                    f"✅ **¡Descarga completada!**\n\n"
                    f"📁 Archivo: `{safe_filename}`\n"
                    f"📦 Tamaño: {size_str}\n"
                    f"🔢 Número: #{file_num}\n\n"
                    f"🔗 **Enlace seguro:**\n`{download_url}`\n\n"
                    f"⚠️ Este enlace expira en {file_service.HASH_EXPIRE_DAYS} días",
                    quote=True
                )
                
            except Exception as e:
                logger.error(f"Error procesando archivo para usuario {user_id}: {e}", exc_info=True)
                await message.reply_text(
                    f"❌ Error crítico al procesar el archivo:\n`{str(e)}`",
                    quote=True
                )
            finally:
                # Limpiar metadata del mensaje
                load_manager.finish_process()
        
        queue_info['active'] = False
    
    # ===== MANEJADOR DE MENSAJES DE TEXTO (echo) =====
    @app.on_message(filters.private & filters.text & ~filters.command)
    async def echo_handler(client, message: Message):
        await message.reply_text(
            "🤖 ¡Hola! Envía un archivo para convertirlo en enlace seguro.\n\n"
            "Usa `/start` para ver los comandos disponibles.",
            quote=True
        )
    
    # ===== MANEJADOR DE ERRORES GLOBALES =====
    @app.on_message(filters.private)
    async def error_handler(client, message: Message):
        try:
            # Este handler captura mensajes no manejados
            if not message.text or message.text.startswith('/'):
                return  # Ya manejado por otros handlers
            
            # Responder a mensajes de texto simples
            await message.reply_text(
                "❓ Comando no reconocido. Usa `/start` para ver los comandos disponibles.",
                quote=True
            )
        except Exception as e:
            logger.error(f"Error en error_handler: {e}", exc_info=True)
    
    logger.info("✅ Handlers de Telegram configurados correctamente")