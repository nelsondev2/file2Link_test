import os
import time
import psutil
import logging
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

from config import OWNER_ID, MAX_FILE_SIZE_MB
from database import db
from file_service import file_service
from load_manager import load_manager

logger = logging.getLogger(__name__)

async def admin_stats_command(client, message):
    """Comando /adminstats - Estadísticas administrativas"""
    try:
        if message.from_user.id not in OWNER_ID:
            return
        
        # Estadísticas de usuarios
        total_users = await db.total_users_count()
        active_users = await db.get_active_users_count(days=7)
        
        # Estadísticas del sistema
        system_status = load_manager.get_status()
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Estadísticas de archivos
        total_files = 0
        total_size = 0
        base_dir = "storage"
        
        if os.path.exists(base_dir):
            for root, dirs, files in os.walk(base_dir):
                total_files += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
        
        total_size_gb = total_size / (1024**3)
        
        # Uso por tipo de archivo
        downloads_count = 0
        packed_count = 0
        
        for user_key in file_service.metadata.keys():
            if "_downloads" in user_key:
                downloads_count += len(file_service.metadata[user_key]["files"])
            elif "_packed" in user_key:
                packed_count += len(file_service.metadata[user_key]["files"])
        
        stats_text = f"""📊 **ESTADÍSTICAS ADMINISTRATIVAS**

👥 **USUARIOS:**
• Total registrados: {total_users}
• Activos (7 días): {active_users}

📁 **ARCHIVOS:**
• Total archivos: {total_files}
• Descargas: {downloads_count}
• Empaquetados: {packed_count}
• Espacio usado: {total_size_gb:.2f} GB

🖥️ **SERVIDOR:**
• CPU: {cpu_percent}%
• RAM: {memory.percent}% ({memory.used/(1024**3):.1f}GB/{memory.total/(1024**3):.1f}GB)
• Disco: {disk.percent}% ({disk.used/(1024**3):.1f}GB/{disk.total/(1024**3):.1f}GB)
• Procesos activos: {system_status['active_processes']}/{system_status['max_processes']}

⚙️ **CONFIGURACIÓN:**
• Límite por archivo: {MAX_FILE_SIZE_MB} MB
• Máx. procesos: {system_status['max_processes']}
• Límite CPU: {system_status.get('cpu_percent', 0):.1f}%

📈 **ESTADO:** {"✅ ÓPTIMO" if system_status['can_accept_work'] else "⚠️ SOBRECARGADO"}"""

        await message.reply_text(stats_text)
        
    except Exception as e:
        logger.error(f"Error en admin_stats: {e}")
        await message.reply_text("❌ Error al obtener estadísticas.")

async def broadcast_command(client, message):
    """Comando /broadcast - Enviar mensaje a todos los usuarios"""
    try:
        if message.from_user.id not in OWNER_ID:
            return
        
        if not message.reply_to_message:
            await message.reply_text(
                "❌ **Debes responder a un mensaje para enviar broadcast.**\n\n"
                "**Uso:** Responde a un mensaje con /broadcast"
            )
            return
        
        broadcast_msg = message.reply_to_message
        
        status_msg = await message.reply_text(
            "📢 **Iniciando broadcast...**\n"
            "Obteniendo lista de usuarios..."
        )
        
        # Obtener todos los usuarios únicos
        all_users = set()
        for key in file_service.metadata.keys():
            if "_downloads" in key or "_packed" in key:
                user_id = key.split("_")[0]
                try:
                    all_users.add(int(user_id))
                except:
                    continue
        
        total_users = len(all_users)
        success = 0
        failed = 0
        current = 0
        
        await status_msg.edit_text(
            f"📢 **Broadcast en progreso...**\n"
            f"Enviando a {total_users} usuarios...\n"
            f"✅ {success} • ❌ {failed} • 📊 {current}/{total_users}"
        )
        
        for user_id in all_users:
            try:
                await broadcast_msg.copy(chat_id=user_id)
                success += 1
                
                # Actualizar actividad del usuario
                await db.update_user_activity(user_id)
                
            except Exception as e:
                failed += 1
                logger.warning(f"Error enviando a {user_id}: {e}")
            
            current += 1
            
            # Actualizar progreso cada 10 usuarios
            if current % 10 == 0 or current == total_users:
                try:
                    await status_msg.edit_text(
                        f"📢 **Broadcast en progreso...**\n"
                        f"Enviando a {total_users} usuarios...\n"
                        f"✅ {success} • ❌ {failed} • 📊 {current}/{total_users}"
                    )
                except:
                    pass
        
        # Resultado final
        result_text = f"""✅ **BROADCAST COMPLETADO**

📊 **Estadísticas:**
• Total usuarios: {total_users}
• Mensajes enviados: {success}
• Fallos: {failed}
• Tasa de éxito: {(success/total_users*100 if total_users > 0 else 0):.1f}%

{'⚠️ **ADVERTENCIA:** ' + str(failed) + ' usuarios no recibieron el mensaje.' if failed > 0 else '🎉 ¡Todos los usuarios recibieron el mensaje!'}"""
        
        await status_msg.edit_text(result_text)
        
        # Guardar log del broadcast
        log_text = f"""📢 BROADCAST LOG - {time.strftime('%Y-%m-%d %H:%M:%S')}
Admin: {message.from_user.id} ({message.from_user.first_name})
Total: {total_users}, Éxitos: {success}, Fallos: {failed}
Mensaje: {broadcast_msg.text[:100] if broadcast_msg.text else 'Media message'}"""
        
        logger.info(log_text)
        
    except Exception as e:
        logger.error(f"Error en broadcast: {e}")
        await message.reply_text(f"❌ Error en broadcast: {str(e)}")

async def system_info_command(client, message):
    """Comando /sysinfo - Información detallada del sistema"""
    try:
        if message.from_user.id not in OWNER_ID:
            return
        
        import platform
        import datetime
        
        # Información del sistema
        system = platform.system()
        release = platform.release()
        architecture = platform.machine()
        python_version = platform.python_version()
        
        # Tiempo de actividad
        boot_time = psutil.boot_time()
        uptime = datetime.datetime.now() - datetime.datetime.fromtimestamp(boot_time)
        
        # Procesos
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except:
                pass
        
        # Ordenar por uso de CPU
        processes.sort(key=lambda x: x['cpu_percent'], reverse=True)
        top_processes = processes[:5]
        
        # Red
        net_io = psutil.net_io_counters()
        
        # Crear mensaje
        info_text = f"""🖥️ **INFORMACIÓN DETALLADA DEL SISTEMA**

📡 **SISTEMA OPERATIVO:**
• Sistema: {system} {release}
• Arquitectura: {architecture}
• Python: {python_version}
• Uptime: {str(uptime).split('.')[0]}

💻 **HARDWARE:**
• CPU: {psutil.cpu_count()} núcleos ({psutil.cpu_percent()}%)
• RAM: {psutil.virtual_memory().percent}% usado
• Disco: {psutil.disk_usage('/').percent}% usado

📊 **PROCESOS (Top 5):**"""
        
        for i, proc in enumerate(top_processes, 1):
            info_text += f"\n  {i}. {proc['name'][:20]:20} CPU:{proc['cpu_percent']:5.1f}% RAM:{proc['memory_percent']:5.1f}%"
        
        info_text += f"""

🌐 **RED:**
• Enviado: {net_io.bytes_sent/(1024**2):.1f} MB
• Recibido: {net_io.bytes_recv/(1024**2):.1f} MB

📁 **ALMACENAMIENTO:**
• Directorio base: {os.path.abspath('storage')}
• Existe: {'✅' if os.path.exists('storage') else '❌'}
• Archivos en metadata: {len(file_service.metadata)}"""

        await message.reply_text(info_text)
        
    except Exception as e:
        logger.error(f"Error en sysinfo: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

async def user_info_command(client, message):
    """Comando /userinfo <user_id> - Información de usuario específico"""
    try:
        if message.from_user.id not in OWNER_ID:
            return
        
        args = message.text.split()
        if len(args) < 2:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/userinfo <user_id>`\n"
                "**Ejemplo:** `/userinfo 123456789`"
            )
            return
        
        try:
            target_user_id = int(args[1])
        except ValueError:
            await message.reply_text("❌ El ID de usuario debe ser numérico.")
            return
        
        # Obtener información del usuario
        user_exists = await db.is_user_exist(target_user_id)
        
        # Estadísticas de archivos del usuario
        downloads = file_service.list_user_files(target_user_id, "downloads")
        packed = file_service.list_user_files(target_user_id, "packed")
        
        total_files = len(downloads) + len(packed)
        total_size = file_service.get_user_storage_usage(target_user_id)
        size_mb = total_size / (1024 * 1024)
        
        # Intentar obtener info de Telegram
        try:
            user_info = await client.get_users(target_user_id)
            user_name = f"{user_info.first_name} {user_info.last_name or ''}".strip()
            username = f"@{user_info.username}" if user_info.username else "Sin username"
        except:
            user_name = "Desconocido"
            username = "No disponible"
        
        info_text = f"""👤 **INFORMACIÓN DE USUARIO**

📝 **DATOS TELEGRAM:**
• ID: `{target_user_id}`
• Nombre: {user_name}
• Username: {username}
• En BD: {'✅ Sí' if user_exists else '❌ No'}

📁 **ARCHIVOS:**
• Total: {total_files} archivos
• Descargas: {len(downloads)}
• Empaquetados: {len(packed)}
• Espacio usado: {size_mb:.2f} MB

📊 **ÚLTIMOS ARCHIVOS:**"""
        
        # Mostrar últimos 5 archivos
        all_files = downloads[-5:] + packed[-5:]
        for file_info in all_files[-5:]:
            folder = "📥" if file_info['file_type'] == "downloads" else "📦"
            info_text += f"\n{folder} #{file_info['number']} - {file_info['name'][:30]} ({file_info['size_mb']:.1f}MB)"
        
        if total_files == 0:
            info_text += "\n\n📭 **El usuario no tiene archivos.**"
        
        await message.reply_text(info_text, disable_web_page_preview=True)
        
    except Exception as e:
        logger.error(f"Error en userinfo: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

async def cleanup_system_command(client, message):
    """Comando /cleanupsystem - Limpieza del sistema"""
    try:
        if message.from_user.id not in OWNER_ID:
            return
        
        status_msg = await message.reply_text("🧹 **Iniciando limpieza del sistema...**")
        
        # Estadísticas antes
        if os.path.exists("storage"):
            import shutil
            total_size_before = 0
            for root, dirs, files in os.walk("storage"):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size_before += os.path.getsize(file_path)
        
        # Limpiar metadata de usuarios sin archivos
        cleaned_users = 0
        users_to_remove = []
        
        for user_key in list(file_service.metadata.keys()):
            if "_downloads" in user_key or "_packed" in user_key:
                user_id = user_key.split("_")[0]
                user_dir = file_service.get_user_directory(user_id, "downloads")
                packed_dir = file_service.get_user_directory(user_id, "packed")
                
                has_files = False
                if os.path.exists(user_dir) and os.listdir(user_dir):
                    has_files = True
                if os.path.exists(packed_dir) and os.listdir(packed_dir):
                    has_files = True
                
                if not has_files:
                    users_to_remove.append(user_key)
                    cleaned_users += 1
        
        for user_key in users_to_remove:
            del file_service.metadata[user_key]
        
        if users_to_remove:
            file_service.save_metadata()
        
        # Limpiar archivos temporales
        temp_files = 0
        for root, dirs, files in os.walk("."):
            for file in files:
                if file.endswith('.tmp') or file.endswith('.temp'):
                    try:
                        os.remove(os.path.join(root, file))
                        temp_files += 1
                    except:
                        pass
        
        # Estadísticas después
        total_size_after = 0
        if os.path.exists("storage"):
            for root, dirs, files in os.walk("storage"):
                for file in files:
                    file_path = os.path.join(root, file)
                    total_size_after += os.path.getsize(file_path)
        
        saved_space = total_size_before - total_size_after
        saved_mb = saved_space / (1024 * 1024)
        
        result_text = f"""✅ **LIMPIEZA DEL SISTEMA COMPLETADA**

🗑️ **Resultados:**
• Usuarios sin archivos eliminados: {cleaned_users}
• Archivos temporales eliminados: {temp_files}
• Espacio liberado: {saved_mb:.2f} MB
• Espacio actual usado: {total_size_after/(1024**3):.2f} GB

🔄 **Metadata actualizada y optimizada.**"""
        
        await status_msg.edit_text(result_text)
        
    except Exception as e:
        logger.error(f"Error en cleanupsystem: {e}")
        await message.reply_text(f"❌ Error en limpieza: {str(e)}")

async def broadcast_with_button_command(client, message):
    """Comando /broadcastbtn - Broadcast con botones"""
    try:
        if message.from_user.id not in OWNER_ID:
            return
        
        args = message.text.split(maxsplit=2)
        if len(args) < 3:
            await message.reply_text(
                "❌ **Formato incorrecto.**\n\n"
                "**Uso:** `/broadcastbtn <texto_botón> <url> <mensaje>`\n"
                "**Ejemplo:** `/broadcastbtn Visitar https://ejemplo.com ¡Nueva actualización!`"
            )
            return
        
        button_text = args[1]
        button_url = args[2]
        broadcast_text = ' '.join(args[3:]) if len(args) > 3 else "📢 Mensaje importante"
        
        # Crear teclado inline
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(button_text, url=button_url)]
        ])
        
        # Obtener usuarios
        all_users = set()
        for key in file_service.metadata.keys():
            if "_downloads" in key or "_packed" in key:
                user_id = key.split("_")[0]
                try:
                    all_users.add(int(user_id))
                except:
                    continue
        
        total_users = len(all_users)
        status_msg = await message.reply_text(
            f"📢 **Preparando broadcast con botón...**\n"
            f"Usuarios a notificar: {total_users}"
        )
        
        success = 0
        failed = 0
        
        for user_id in all_users:
            try:
                await client.send_message(
                    chat_id=user_id,
                    text=broadcast_text,
                    reply_markup=keyboard
                )
                success += 1
                await db.update_user_activity(user_id)
            except Exception as e:
                failed += 1
                logger.warning(f"Error enviando a {user_id}: {e}")
            
            # Pequeña pausa para evitar flood
            await asyncio.sleep(0.1)
        
        result_text = f"""✅ **BROADCAST CON BOTÓN COMPLETADO**

📊 **Estadísticas:**
• Total usuarios: {total_users}
• Enviados: {success}
• Fallos: {failed}
• Botón: [{button_text}]({button_url})

🎯 **Mensaje enviado a {success} usuarios exitosamente.**"""
        
        await status_msg.edit_text(
            result_text,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error en broadcastbtn: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")

def setup_admin_handlers(client):
    """Configura todos los handlers administrativos"""
    client.on_message(filters.command("adminstats") & filters.private)(admin_stats_command)
    client.on_message(filters.command("broadcast") & filters.private)(broadcast_command)
    client.on_message(filters.command("sysinfo") & filters.private)(system_info_command)
    client.on_message(filters.command("userinfo") & filters.private)(user_info_command)
    client.on_message(filters.command("cleanupsystem") & filters.private)(cleanup_system_command)
    client.on_message(filters.command("broadcastbtn") & filters.private)(broadcast_with_button_command)