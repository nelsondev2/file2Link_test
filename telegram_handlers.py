import os
import logging
import sys
import time
import asyncio
import concurrent.futures
import hashlib
import re
import gc
from collections import deque, OrderedDict
from pyrogram import Client, filters
from pyrogram.types import Message

from config import OWNER_ID, BIN_CHANNEL, MAX_QUEUE_SIZE, MAX_CONCURRENT_UPLOADS, MAX_FILE_SIZE, MAX_FILE_SIZE_MB, MAX_CACHED_USERS, MAX_FILES_PER_USER
from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import fast_download_service
from filename_utils import safe_filename, clean_for_filesystem, clean_for_url
from url_utils import fix_problematic_filename

logger = logging.getLogger(__name__)

# ===== SISTEMA DE COLA OPTIMIZADO =====
class OptimizedUserQueues:
    """Sistema de colas optimizado para bajo consumo de RAM"""
    def __init__(self):
        self.queues = OrderedDict()
        self.locks = {}
        self.queue_metadata = {}  # Solo metadata esencial
        self.last_cleanup = time.time()
    
    def add_to_queue(self, user_id, message):
        """Agregar mensaje a la cola optimizada"""
        if user_id not in self.queues:
            self.queues[user_id] = deque(maxlen=MAX_QUEUE_SIZE)
            self.queue_metadata[user_id] = {
                'added_at': time.time(),
                'processed_count': 0
            }
        
        # Extraer solo datos esenciales del mensaje
        essential_data = self._extract_essential_data(message)
        self.queues[user_id].append(essential_data)
        
        # Limpieza periódica
        self._periodic_cleanup()
        
        return len(self.queues[user_id])
    
    def _extract_essential_data(self, message):
        """Extraer solo los datos esenciales del mensaje para ahorrar RAM"""
        essential = {
            'message_id': message.id,
            'user_id': message.from_user.id,
            'timestamp': time.time()
        }
        
        # Extraer información del archivo
        if message.document:
            essential.update({
                'type': 'document',
                'file_name': message.document.file_name or 'document',
                'file_size': message.document.file_size or 0,
                'mime_type': message.document.mime_type or 'application/octet-stream'
            })
        elif message.video:
            essential.update({
                'type': 'video',
                'file_name': message.video.file_name or 'video.mp4',
                'file_size': message.video.file_size or 0,
                'duration': message.video.duration or 0
            })
        elif message.audio:
            essential.update({
                'type': 'audio',
                'file_name': message.audio.file_name or 'audio.mp3',
                'file_size': message.audio.file_size or 0,
                'duration': message.audio.duration or 0
            })
        elif message.photo:
            essential.update({
                'type': 'photo',
                'file_name': f'photo_{message.id}.jpg',
                'file_size': message.photo[-1].file_size or 0
            })
        else:
            essential.update({
                'type': 'unknown',
                'file_name': 'file',
                'file_size': 0
            })
        
        return essential
    
    def get_queue(self, user_id):
        """Obtener cola del usuario"""
        return self.queues.get(user_id, deque())
    
    def queue_size(self, user_id):
        """Tamaño de la cola del usuario"""
        return len(self.queues.get(user_id, []))
    
    def pop_from_queue(self, user_id):
        """Sacar elemento de la cola"""
        if user_id in self.queues and self.queues[user_id]:
            return self.queues[user_id].popleft()
        return None
    
    def clear_queue(self, user_id):
        """Limpiar cola del usuario"""
        if user_id in self.queues:
            self.queues[user_id].clear()
            return True
        return False
    
    def _periodic_cleanup(self):
        """Limpieza periódica de colas antiguas"""
        current_time = time.time()
        if current_time - self.last_cleanup < 300:  # Cada 5 minutos
            return
        
        self.last_cleanup = current_time
        users_to_remove = []
        
        for user_id, metadata in list(self.queue_metadata.items()):
            # Eliminar colas inactivas por más de 1 hora
            if current_time - metadata['added_at'] > 3600 and self.queue_size(user_id) == 0:
                users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            if user_id in self.queues:
                del self.queues[user_id]
            if user_id in self.queue_metadata:
                del self.queue_metadata[user_id]
            if user_id in self.locks:
                del self.locks[user_id]
        
        if users_to_remove:
            logger.info(f"🧹 Colas limpiadas: {len(users_to_remove)} usuarios inactivos")
            gc.collect()

# Instancia global optimizada
user_queues_manager = OptimizedUserQueues()
user_current_processing = {}
user_progress_messages = {}
user_progress_data = {}

# Estadísticas globales optimizadas
global_stats = {
    'total_files_received': 0,
    'total_bytes_received': 0,
    'total_users_served': 0,
    'start_time': time.time(),
    'last_gc': time.time()
}

def get_user_queue_lock(user_id):
    """Obtiene lock para la cola del usuario"""
    if user_id not in user_queues_manager.locks:
        user_queues_manager.locks[user_id] = asyncio.Lock()
    return user_queues_manager.locks[user_id]

# ===== FUNCIONES AUXILIARES OPTIMIZADAS =====
async def send_to_bin_channel(client, text):
    """Enviar mensaje al canal de logs"""
    try:
        if BIN_CHANNEL:
            await client.send_message(
                chat_id=int(BIN_CHANNEL),
                text=text[:4000],  # Limitar tamaño
                disable_web_page_preview=True
            )
    except Exception as e:
        logger.error(f"Error enviando a bin_channel: {e}")

def update_global_stats(bytes_received=0, files_received=0, users_served=0):
    """Actualizar estadísticas globales"""
    global_stats['total_bytes_received'] += bytes_received
    global_stats['total_files_received'] += files_received
    if users_served > 0:
        global_stats['total_users_served'] += users_served
    
    # Garbage collection periódico
    current_time = time.time()
    if current_time - global_stats['last_gc'] > 300:  # Cada 5 minutos
        gc.collect()
        global_stats['last_gc'] = current_time

def force_garbage_collection():
    """Forzar garbage collection"""
    try:
        collected = gc.collect()
        logger.debug(f"🧹 Garbage collection: {collected} objetos recolectados")
    except:
        pass

# ===== COMANDOS DE ADMINISTRACIÓN (sin cambios) =====
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
**Límite en caché:** `{MAX_CACHED_USERS}`

**Últimos 5 usuarios:**"""
        
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
            
            response += f"\n{i}. **{first_name}** (`{user_id}`) - {files_count} archivos - Visto: {last_seen_str}"
        
        response += f"\n\n**⚡ Sistema optimizado para 512MB RAM**"
        
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
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        stats_text = f"""📊 **ESTADÍSTICAS DEL SISTEMA**

👥 **USUARIOS:** {total_users}
📁 **ARCHIVOS:** {total_files}
💾 **ESPACIO:** {load_manager.get_readable_file_size(total_size)}

⚙️ **SISTEMA:**
• Uptime: {days}d {hours}h {minutes}m
• CPU estimada: {system_status['cpu_percent']:.1f}%
• Procesos: {system_status['active_processes']}/{system_status['max_processes']}

⬇️ **DESCARGAS:**
• Total: {download_stats['total_downloads']}
• Exitosas: {download_stats['successful']}
• Fallidas: {download_stats['failed']}

⚡ **OPTIMIZACIÓN:**
• RAM: ✅ Optimizado para 512MB
• Streaming: ✅ Activado
• Límites: {MAX_CACHED_USERS} usuarios, {MAX_FILES_PER_USER} archivos/usuario"""

        await message.reply_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error en /stats: {e}")
        await message.reply_text("❌ Error obteniendo estadísticas.")

# ===== COMANDOS BÁSICOS (sin cambios excepto optimizaciones) =====
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

🤖 **Bot de Archivos - Optimizado**

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
**⚡ OPTIMIZADO:** Sistema para 512MB RAM

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
`/about` - Información del bot
`/stats` - Estadísticas del sistema

**⚡ SISTEMA OPTIMIZADO PARA 512MB RAM**"""

        await message.reply_text(help_text)

    except Exception as e:
        logger.error(f"Error en /help: {e}")

# ===== MANEJO DE ARCHIVOS OPTIMIZADO =====
async def handle_file(client, message):
    """Maneja la recepción de archivos con sistema de cola optimizado"""
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
        current_queue_size = user_queues_manager.queue_size(user_id)
        
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
        
        # Agregar a cola optimizada
        queue_size = user_queues_manager.add_to_queue(user_id, message)
        
        await message.reply_text(
            f"✅ **Archivo agregado a la cola**\n\n"
            f"**Posición en cola:** #{queue_size}\n"
            f"**Total en cola:** {queue_size} archivo(s)\n"
            f"**Procesando:** {'Sí' if user_id in user_current_processing else 'No'}"
        )
        
        # Iniciar procesamiento si no hay otro en curso
        if user_id not in user_current_processing:
            asyncio.create_task(process_file_queue(client, user_id))
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)

async def process_file_queue(client, user_id):
    """Procesa la cola de archivos del usuario optimizado"""
    try:
        async with get_user_queue_lock(user_id):
            total_files_in_batch = user_queues_manager.queue_size(user_id)
            if total_files_in_batch == 0:
                return
            
            user_current_processing[user_id] = True
            completed_files = []
            current_position = 0
            
            # Procesar archivos UNO POR UNO
            while user_queues_manager.queue_size(user_id) > 0:
                current_position += 1
                
                # Obtener datos esenciales de la cola
                file_data = user_queues_manager.pop_from_queue(user_id)
                if not file_data:
                    break
                
                try:
                    # Obtener el mensaje original para procesarlo
                    message = await client.get_messages(
                        file_data['user_id'],
                        message_ids=file_data['message_id']
                    )
                    
                    if not message:
                        logger.error(f"No se pudo obtener mensaje {file_data['message_id']}")
                        continue
                    
                    # Procesar el archivo
                    result = await process_file_with_progress(
                        client, message, user_id, 
                        current_position, total_files_in_batch
                    )
                    
                    if result:
                        completed_files.append(result)
                    
                    # Pequeña pausa entre archivos
                    if current_position < total_files_in_batch:
                        await asyncio.sleep(0.5)
                    
                except Exception as e:
                    logger.error(f"Error procesando archivo #{current_position}: {e}")
                    continue
            
            # Al finalizar todos los archivos, mostrar resumen
            if completed_files:
                await show_final_summary(client, user_id, completed_files)
            
            # Limpieza final
            cleanup_user_session(user_id)
            force_garbage_collection()
                
    except Exception as e:
        logger.error(f"Error en process_file_queue: {e}", exc_info=True)
        cleanup_user_session(user_id)

async def process_file_with_progress(client, message, user_id, current_position, total_files):
    """Procesa un archivo mostrando progreso"""
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
        stored_filename = safe_filename(original_filename, user_id)
        file_path = os.path.join(user_dir, stored_filename)
        
        # Manejar nombres duplicados
        counter = 1
        base_name, ext = os.path.splitext(stored_filename)
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1

        # Registrar archivo
        file_number = file_service.register_file(user_id, original_filename, stored_filename, "downloads")
        
        # Mostrar progreso solo para el primer archivo
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
                'current_position': current_position
            }
        
        # Actualizar datos de progreso
        if user_id in user_progress_data:
            user_progress_data[user_id].update({
                'current_position': current_position,
                'current_filename': original_filename,
                'current_filesize': file_size,
                'start_time': start_time
            })
        
        async def progress_callback(current, total):
            try:
                if user_id not in user_progress_data:
                    return
                
                elapsed_time = time.time() - start_time
                speed = current / elapsed_time if elapsed_time > 0 else 0
                
                # Suavizar velocidad
                last_speed = user_progress_data[user_id].get('last_speed', 0)
                smoothed_speed = 0.7 * last_speed + 0.3 * speed
                user_progress_data[user_id]['last_speed'] = smoothed_speed

                current_time = time.time()
                last_update = user_progress_data[user_id].get('last_update', 0)

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
                        await client.edit_message_text(
                            chat_id=user_id,
                            message_id=user_progress_messages[user_id],
                            text=progress_message,
                            disable_web_page_preview=True
                        )
                        user_progress_data[user_id]['last_update'] = current_time
                    except:
                        pass

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")
        
        # Descargar archivo
        success, downloaded = await fast_download_service.download_with_retry(
            client=client,
            message=message,
            file_path=file_path,
            progress_callback=progress_callback
        )

        if not success or not os.path.exists(file_path):
            return None

        final_size = os.path.getsize(file_path)
        
        # Generar URL con hash
        download_url = file_service.create_download_url(user_id, stored_filename)
        
        # Actualizar estadísticas globales
        update_global_stats(bytes_received=final_size, files_received=1)
        
        logger.info(f"✅ Archivo procesado: {original_filename} para usuario {user_id}")
        
        return {
            'number': file_number,
            'name': original_filename,
            'display_name': original_filename[:40] + "..." if len(original_filename) > 40 else original_filename,
            'stored_name': stored_filename,
            'size_mb': final_size / (1024 * 1024),
            'url': download_url,
            'position': current_position
        }

    except Exception as e:
        logger.error(f"Error procesando archivo individual: {e}", exc_info=True)
        return None

async def show_final_summary(client, user_id, completed_files):
    """Muestra el resumen final optimizado"""
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
            display_name = file_info['display_name']
            
            summary_text += f"\n**#{file_info['number']}** - `{display_name}`\n"
            summary_text += f"📏 **Tamaño:** {file_info['size_mb']:.1f} MB\n"
            summary_text += f"🔗 [{file_info['name']}]({file_info['url']})\n"
        
        summary_text += f"\n**📁 Ubicación:** Carpeta `downloads`"
        summary_text += f"\n**📋 Comando:** `/list` para ver todos tus archivos"
        
        # Si el mensaje es muy largo, dividirlo
        if len(summary_text) > 4000:
            first_part = summary_text[:4000]
            last_newline = first_part.rfind('\n')
            if last_newline > 0:
                first_part = first_part[:last_newline]
            
            await client.send_message(
                user_id,
                first_part,
                disable_web_page_preview=True
            )
            
            second_part = summary_text[last_newline + 1:]
            await client.send_message(
                user_id,
                second_part,
                disable_web_page_preview=True
            )
        else:
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
    if user_id in user_progress_messages:
        del user_progress_messages[user_id]
    if user_id in user_progress_data:
        del user_progress_data[user_id]
    
    # Forzar garbage collection
    force_garbage_collection()

# ===== COMANDOS DE COLA OPTIMIZADOS =====
async def queue_command(client, message):
    """Maneja el comando /queue - Ver estado de la cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if not file_service.is_user_exist(user_id):
            file_service.add_user(user_id, message.from_user.first_name)
        
        queue_size = user_queues_manager.queue_size(user_id)
        
        if queue_size == 0:
            await message.reply_text("📭 **Cola vacía**\n\nNo hay archivos en cola de descarga.")
            return
        
        current_processing = "✅ **EN PROCESO AHORA**" if user_id in user_current_processing else "⏸️ **Esperando turno**"
        
        queue_text = f"📋 **Estado de la Cola - {queue_size} archivo(s)**\n\n"
        queue_text += f"**Estado actual:** {current_processing}\n"
        queue_text += f"**Límite de cola:** {MAX_QUEUE_SIZE} archivos\n"
        queue_text += f"**Procesamiento:** UNO POR UNO (orden estricto)\n\n"
        queue_text += f"**Archivos en cola:**\n"
        
        # Mostrar solo los primeros 5 archivos para ahorrar espacio
        queue_items = list(user_queues_manager.get_queue(user_id))[:5]
        for i, file_data in enumerate(queue_items, 1):
            file_name = file_data.get('file_name', 'Desconocido')
            file_size = file_data.get('file_size', 0)
            size_mb = file_size / (1024 * 1024) if file_size > 0 else 0
            
            queue_text += f"**#{i}** - {file_name} ({size_mb:.1f} MB)\n"
        
        if queue_size > 5:
            queue_text += f"\n... y {queue_size - 5} archivo(s) más"
        
        queue_text += f"\n\n**Comandos:**\n"
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
        
        queue_size = user_queues_manager.queue_size(user_id)
        if queue_size == 0:
            await message.reply_text("📭 **Cola ya está vacía**")
            return
        
        user_queues_manager.clear_queue(user_id)
        cleanup_user_session(user_id)
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n\nSe removieron {queue_size} archivos de la cola.")
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Error al limpiar la cola.")

# ===== SETUP DE HANDLERS (sin cambios) =====
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