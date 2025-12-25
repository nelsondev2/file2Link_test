import os
import logging
import sys
import time
import asyncio
import concurrent.futures
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import MessageMediaType, ParseMode
from pyrogram.errors import FloodWait, FileIdInvalid, FileReferenceExpired

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import fast_download_service
from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB

logger = logging.getLogger(__name__)

# ===== SISTEMA DE SESIÓN MEJORADO =====
user_sessions: Dict[int, dict] = {}
user_queues: Dict[int, List[Message]] = {}
user_progress_msgs: Dict[int, int] = {}
user_current_processing: Dict[int, bool] = {}
user_batch_totals: Dict[int, int] = {}

def get_user_session(user_id: int) -> dict:
    """Obtiene o crea la sesión del usuario con valores por defecto"""
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'current_folder': 'downloads',
            'notifications': True,
            'auto_download': True,
            'created_at': time.time(),
            'last_activity': time.time()
        }
    
    # Actualizar última actividad
    user_sessions[user_id]['last_activity'] = time.time()
    return user_sessions[user_id]

def update_user_activity(user_id: int):
    """Actualiza la actividad del usuario para limpieza automática"""
    if user_id in user_sessions:
        user_sessions[user_id]['last_activity'] = time.time()

# ===== DECORADORES PROFESIONALES =====
def rate_limit(seconds: int = 2):
    """Decorador para limitar frecuencia de comandos"""
    def decorator(func):
        last_called = {}
        
        async def wrapper(client, message, *args, **kwargs):
            user_id = message.from_user.id
            current_time = time.time()
            
            if user_id in last_called:
                time_since = current_time - last_called[user_id]
                if time_since < seconds:
                    wait_time = seconds - time_since
                    await message.reply_text(
                        f"⏳ Por favor espera {wait_time:.1f} segundos antes de otro comando."
                    )
                    return
            
            last_called[user_id] = current_time
            return await func(client, message, *args, **kwargs)
        
        return wrapper
    return decorator

# ===== COMANDOS MEJORADOS =====

@rate_limit(1)
async def start_command(client: Client, message: Message):
    """Comando /start con diseño profesional y teclado inline"""
    try:
        user = message.from_user
        
        # Teclado inline para primer uso
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📁 Ver mis archivos", callback_data="quick_list"),
                InlineKeyboardButton("📦 Empaquetar", callback_data="quick_pack")
            ],
            [
                InlineKeyboardButton("🆘 Ayuda rápida", callback_data="quick_help"),
                InlineKeyboardButton("⚙️ Configuración", callback_data="quick_settings")
            ],
            [
                InlineKeyboardButton("🌐 Panel Web", url="https://nelson-file2link.onrender.com"),
                InlineKeyboardButton("👨‍💻 Soporte", url="https://t.me/nelson_support")
            ]
        ])
        
        welcome_text = f"""👋 **¡Bienvenido/a {user.first_name}!**

🤖 **Nelson File2Link** - Sistema Profesional de Gestión de Archivos

⭐ **Características principales:**
• 📁 **Sistema de carpetas** organizado (downloads/packed)
• 📦 **Empaquetado inteligente** con división automática
• 🚀 **Descargas ultra rápidas** optimizadas
• 🔄 **Cola de procesamiento** inteligente
• 📊 **Monitoreo en tiempo real** del sistema

📏 **Límites actuales:**
• Tamaño máximo: **{MAX_FILE_SIZE_MB} MB** por archivo
• Procesos simultáneos: **1** (optimizado para estabilidad)
• Formato: **Todos los tipos** soportados

🎯 **Para comenzar:**
1. Envía cualquier archivo al bot
2. Usa `/cd downloads` para ver tus archivos
3. Usa `/pack` para crear ZIPs

📌 **Comando rápido:** `/help` para ver todos los comandos

💡 **Consejo profesional:** Los archivos grandes se dividen automáticamente para mejor manejo."""

        await message.reply_text(
            welcome_text,
            reply_markup=keyboard,
            disable_web_page_preview=True,
            parse_mode=ParseMode.MARKDOWN
        )
        
        logger.info(f"👤 Nuevo usuario: {user.id} - {user.first_name} (@{user.username})")
        update_user_activity(user.id)

    except Exception as e:
        logger.error(f"Error en /start: {e}", exc_info=True)
        await message.reply_text("❌ Error al mostrar la bienvenida. Por favor intenta nuevamente.")

@rate_limit(1)
async def help_command(client: Client, message: Message):
    """Comando /help mejorado con secciones organizadas"""
    try:
        help_text = f"""📚 **AYUDA COMPLETA - Nelson File2Link**

**📁 SISTEMA DE CARPETAS:**
`/cd downloads` - Acceder a archivos descargados
`/cd packed` - Acceder a archivos empaquetados  
`/cd` - Mostrar carpeta actual

**📄 GESTIÓN DE ARCHIVOS:**
`/list [página]` - Listar archivos (10 por página)
`/rename <número> <nuevo_nombre>` - Renombrar archivo
`/delete <número>` - Eliminar archivo específico
`/clear` - Vaciar carpeta actual completamente

**📦 EMPAQUETADO AVANZADO:**
`/pack` - Crear ZIP simple (sin compresión)
`/pack <MB>` - Dividir en partes (ej: `/pack 100` para partes de 100MB)
`/pack 0` - ZIP con compresión máxima

**🔄 GESTIÓN DE COLA:**
`/queue` - Ver archivos pendientes en cola
`/clearqueue` - Limpiar cola de descargas
`/status` - Estado del sistema y recursos

**🔍 INFORMACIÓN Y UTILIDADES:**
`/status` - Estado del sistema en tiempo real
`/cleanup` - Limpiar archivos temporales
`/help` - Mostrar este mensaje

**📏 LÍMITES DEL SISTEMA:**
• Tamaño máximo: {MAX_FILE_SIZE_MB} MB por archivo
• Formatos soportados: Documentos, Videos, Audio, Fotos
• Compresión: ZIP sin compresión por defecto (más rápido)
• Partición: Máximo 200MB por parte

**🎯 EJEMPLOS PRÁCTICOS:**
```

/cd downloads
/list
/delete 3
/rename 5"Mi Documento Final.pdf"
/pack 50# Partes de 50MB
/queue# Ver qué se está procesando

```

**⚠️ CONSEJOS:**
• Los archivos se numeran automáticamente (#1, #2, etc.)
• Puedes usar `/list 2` para ver página 2
• Los ZIP grandes se dividen automáticamente
• Usa `/clearqueue` si un archivo se atasca

**🆘 SOPORTE:**
[Panel Web](https://nelson-file2link.onrender.com) | [Soporte](https://t.me/nelson_support)"""

        await message.reply_text(
            help_text,
            disable_web_page_preview=True,
            parse_mode=ParseMode.MARKDOWN
        )
        
        update_user_activity(message.from_user.id)

    except Exception as e:
        logger.error(f"Error en /help: {e}")
        await message.reply_text("❌ Error al mostrar ayuda.")

@rate_limit(1)
async def cd_command(client: Client, message: Message):
    """Comando /cd mejorado con validaciones"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        args = message.text.split()
        
        if len(args) == 1:
            # Mostrar carpeta actual con estadísticas
            current = session['current_folder']
            files = file_service.list_user_files(user_id, current)
            total_size = sum(f['size'] for f in files)
            
            response = (
                f"📂 **Carpeta actual:** `{current}`\n"
                f"📊 **Estadísticas:** {len(files)} archivos, "
                f"{file_service.format_bytes(total_size)}\n\n"
            )
            
            if len(files) > 0:
                response += "**Archivos recientes:**\n"
                for file_info in files[:3]:  # Mostrar primeros 3
                    response += f"• `{file_info['name'][:30]}{'...' if len(file_info['name']) > 30 else ''}`\n"
                response += "\nUsa `/list` para ver todos."
            else:
                response += "📭 **Carpeta vacía**\nEnvía archivos o usa `/pack` para crear algunos."
            
            await message.reply_text(response)
        else:
            folder = args[1].lower()
            valid_folders = ['downloads', 'packed']
            
            if folder in valid_folders:
                old_folder = session['current_folder']
                session['current_folder'] = folder
                
                # Obtener estadísticas de la nueva carpeta
                files = file_service.list_user_files(user_id, folder)
                total_size = sum(f['size'] for f in files)
                
                response = (
                    f"✅ **Carpeta cambiada exitosamente**\n\n"
                    f"**De:** `{old_folder}`\n"
                    f"**A:** `{folder}`\n\n"
                    f"📊 **Contenido:** {len(files)} archivos, "
                    f"{file_service.format_bytes(total_size)}"
                )
                
                if len(files) > 0:
                    response += "\n\nUsa `/list` para ver los archivos."
                
                await message.reply_text(response)
                
            else:
                await message.reply_text(
                    "❌ **Carpeta no válida.**\n\n"
                    "**Carpetas disponibles:**\n"
                    "• `downloads` - Tus archivos de descarga\n"  
                    "• `packed` - Archivos empaquetados (ZIP)\n\n"
                    "**Ejemplo:** `/cd downloads` o `/cd packed`"
                )
        
        update_user_activity(user_id)

    except Exception as e:
        logger.error(f"Error en /cd: {e}")
        await message.reply_text("❌ Error al cambiar carpeta.")

@rate_limit(1)
async def list_command(client: Client, message: Message):
    """Comando /list mejorado con paginación inteligente y cache"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        args = message.text.split()
        page = 1
        if len(args) > 1:
            try:
                page = int(args[1])
                if page < 1:
                    page = 1
            except ValueError:
                page = 1
        
        # Obtener archivos
        files = file_service.list_user_files(user_id, current_folder)
        
        if not files:
            folder_names = {
                'downloads': 'descargas 📥',
                'packed': 'empaquetados 📦'
            }
            folder_display = folder_names.get(current_folder, current_folder)
            
            await message.reply_text(
                f"📭 **Carpeta {folder_display} está vacía.**\n\n"
                f"**Para agregar archivos:**\n"
                f"• 📤 Envía archivos al bot (van a 'downloads')\n"
                f"• 📦 Usa `/pack` para crear archivos en 'packed'\n"
                f"• 🔄 Usa `/cd downloads` para cambiar de carpeta"
            )
            return
        
        # Configurar paginación
        items_per_page = 8  # Reducido para mejor legibilidad
        total_pages = max(1, (len(files) + items_per_page - 1) // items_per_page)
        page = max(1, min(page, total_pages))
        
        start_idx = (page - 1) * items_per_page
        end_idx = start_idx + items_per_page
        page_files = files[start_idx:end_idx]
        
        # Preparar encabezado
        folder_icons = {'downloads': '📥', 'packed': '📦'}
        folder_icon = folder_icons.get(current_folder, '📁')
        
        # Calcular estadísticas
        total_size = sum(f['size'] for f in files)
        avg_size = total_size / len(files) if len(files) > 0 else 0
        
        files_text = (
            f"{folder_icon} **{current_folder.upper()}** "
            f"- Página {page}/{total_pages}\n"
            f"📊 **Total:** {len(files)} archivos | "
            f"{file_service.format_bytes(total_size)}\n"
            f"📏 **Promedio:** {file_service.format_bytes(avg_size)}\n"
            f"⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n"
        )
        
        # Listar archivos de la página
        for file_info in page_files:
            # Acortar nombre si es muy largo
            display_name = file_info['name']
            if len(display_name) > 35:
                display_name = display_name[:32] + "..."
            
            file_line = (
                f"**#{file_info['number']:02d}** - `{display_name}`\n"
                f"    📏 {file_info['size_mb']:.1f} MB | "
                f"[🔗 Descargar]({file_info['url']})\n"
            )
            
            # Agregar información adicional para ciertos tipos
            if current_folder == 'packed' and '.zip' in file_info['name']:
                file_line += "    📦 Archivo comprimido\n"
            
            files_text += file_line + "\n"
        
        # Agregar navegación si hay múltiples páginas
        if total_pages > 1:
            files_text += "\n**📄 Navegación:**\n"
            if page > 1:
                files_text += f"• `/list {page-1}` - Página anterior\n"
            if page < total_pages:
                files_text += f"• `/list {page+1}` - Página siguiente\n"
            files_text += f"• `/list <n>` - Ir a página específica\n"
        
        # Agregar comandos disponibles
        files_text += "\n**🔧 Comandos disponibles:**\n"
        files_text += f"• `/delete <número>` - Eliminar archivo\n"
        files_text += f"• `/rename <número> <nuevo_nombre>` - Renombrar\n"
        files_text += f"• `/clear` - Vaciar carpeta completa\n"
        
        if current_folder == 'downloads' and len(files) > 1:
            files_text += f"• `/pack` - Empaquetar todos en ZIP\n"
        
        # Enviar mensaje (dividir si es muy largo)
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
            
            # Enviar primera parte
            await message.reply_text(parts[0], disable_web_page_preview=True)
            
            # Enviar partes restantes
            for part in parts[1:]:
                await message.reply_text(part, disable_web_page_preview=True)
        else:
            await message.reply_text(files_text, disable_web_page_preview=True)
        
        update_user_activity(user_id)

    except Exception as e:
        logger.error(f"Error en /list: {e}", exc_info=True)
        await message.reply_text("❌ Error al listar archivos.")

@rate_limit(1)
async def delete_command(client: Client, message: Message):
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
            
        update_user_activity(user_id)
            
    except Exception as e:
        logger.error(f"Error en /delete: {e}")
        await message.reply_text("❌ Error al eliminar archivo.")

@rate_limit(1)
async def clear_command(client: Client, message: Message):
    """Maneja el comando /clear - Vaciar carpeta actual"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        current_folder = session['current_folder']
        
        # Confirmación antes de vaciar
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Sí, vaciar todo", callback_data=f"confirm_clear_{current_folder}"),
                InlineKeyboardButton("❌ Cancelar", callback_data="cancel_clear")
            ]
        ])
        
        await message.reply_text(
            f"⚠️ **¿Estás seguro de que quieres vaciar la carpeta `{current_folder}`?**\n\n"
            f"Esta acción eliminará **todos** los archivos de esta carpeta y no se puede deshacer.\n\n"
            f"Archivos afectados: {len(file_service.list_user_files(user_id, current_folder))}",
            reply_markup=keyboard
        )
        
        update_user_activity(user_id)
            
    except Exception as e:
        logger.error(f"Error en /clear: {e}")
        await message.reply_text("❌ Error al vaciar carpeta.")

@rate_limit(2)
async def rename_command(client: Client, message: Message):
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
        
        update_user_activity(user_id)
            
    except Exception as e:
        logger.error(f"Error en comando /rename: {e}")
        await message.reply_text("❌ Error al renombrar archivo.")

@rate_limit(1)
async def status_command(client: Client, message: Message):
    """Comando /status mejorado con más información"""
    try:
        user_id = message.from_user.id
        session = get_user_session(user_id)
        
        # Obtener estadísticas del usuario
        downloads_count = len(file_service.list_user_files(user_id, "downloads"))
        packed_count = len(file_service.list_user_files(user_id, "packed"))
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        # Obtener estado del sistema
        system_status = load_manager.get_status()
        
        # Calcular tiempo de actividad del usuario
        session_age = time.time() - session.get('created_at', time.time())
        hours, remainder = divmod(session_age, 3600)
        minutes, _ = divmod(remainder, 60)
        
        # Preparar texto de estado
        status_text = f"📊 **ESTADO DEL SISTEMA - {message.from_user.first_name}**\n"
        status_text += "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯\n\n"
        
        # Sección USUARIO
        status_text += "👤 **INFORMACIÓN DEL USUARIO**\n"
        status_text += f"• **ID:** `{user_id}`\n"
        status_text += f"• **📂 Carpeta actual:** `{session['current_folder']}`\n"
        status_text += f"• **⏱️ Sesión activa:** {int(hours)}h {int(minutes)}m\n\n"
        
        # Sección ALMACENAMIENTO
        status_text += "💾 **ALMACENAMIENTO**\n"
        status_text += f"• 📥 **Descargas:** {downloads_count} archivos\n"
        status_text += f"• 📦 **Empaquetados:** {packed_count} archivos\n"
        status_text += f"• 📏 **Total usado:** {size_mb:.2f} MB\n\n"
        
        # Sección SISTEMA
        status_text += "🖥️ **ESTADO DEL SERVIDOR**\n"
        status_text += f"• ⚙️ **Procesos activos:** {system_status['active_processes']}/{system_status['max_processes']}\n"
        status_text += f"• 🖥️ **Uso de CPU:** {system_status['cpu_percent']:.1f}%\n"
        status_text += f"• 💾 **Uso de memoria:** {system_status['memory_percent']:.1f}%\n"
        
        # Indicador de estado
        if system_status['can_accept_work']:
            status_text += "• ✅ **Estado:** ACEPTANDO NUEVOS ARCHIVOS\n"
        else:
            status_text += "• ⚠️ **Estado:** SOBRECARGADO - Espera unos minutos\n"
        
        status_text += "\n"
        
        # Sección CONFIGURACIÓN
        status_text += "⚙️ **CONFIGURACIÓN ACTUAL**\n"
        status_text += f"• 📏 **Tamaño máximo:** {MAX_FILE_SIZE_MB} MB por archivo\n"
        status_text += f"• 📦 **Tamaño máximo por parte:** 200 MB\n"
        status_text += f"• ⚡ **Descargas concurrentes:** 1 (optimizado)\n"
        
        # Agregar consejo basado en estado
        if system_status['cpu_percent'] > 70:
            status_text += "\n⚠️ **Consejo:** El sistema está cargado. Considera esperar antes de enviar archivos grandes."
        elif downloads_count == 0:
            status_text += "\n💡 **Consejo:** ¡Envía tu primer archivo para comenzar!"
        elif downloads_count > 5 and packed_count == 0:
            status_text += "\n💡 **Consejo:** Tienes varios archivos. Usa `/pack` para crear un ZIP."
        
        await message.reply_text(status_text)
        
        update_user_activity(user_id)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Error al obtener estado del sistema.")

@rate_limit(2)
async def pack_command(client: Client, message: Message):
    """Comando /pack mejorado con más opciones y mejor feedback"""
    try:
        user_id = message.from_user.id
        command_parts = message.text.split()
        
        # Verificar estado del sistema
        system_status = load_manager.get_status()
        if not system_status['can_accept_work']:
            cpu = system_status['cpu_percent']
            memory = system_status['memory_percent']
            active = system_status['active_processes']
            
            await message.reply_text(
                f"⚠️ **Sistema sobrecargado**\n\n"
                f"**Estado actual:**\n"
                f"• 🖥️ CPU: {cpu:.1f}% (límite: 80%)\n"
                f"• 💾 Memoria: {memory:.1f}%\n"
                f"• 🔄 Procesos activos: {active}/{system_status['max_processes']}\n\n"
                f"Por favor intenta nuevamente en unos minutos.\n"
                f"Puedes usar `/status` para ver cuando esté disponible."
            )
            return
        
        # Parsear argumentos
        split_size = None
        compression = False
        
        if len(command_parts) > 1:
            arg = command_parts[1].lower()
            
            if arg == 'compress' or arg == '0':
                compression = True
            else:
                try:
                    split_size = int(arg)
                    if split_size <= 0:
                        await message.reply_text(
                            "❌ **Tamaño inválido.**\n"
                            "El tamaño debe ser mayor a 0 MB.\n"
                            "Ejemplo: `/pack 100` para partes de 100MB"
                        )
                        return
                    if split_size > 200:
                        await message.reply_text(
                            "❌ **Tamaño máximo excedido.**\n"
                            "El tamaño máximo por parte es 200 MB.\n"
                            "Usa un valor entre 1 y 200."
                        )
                        return
                except ValueError:
                    await message.reply_text(
                        "❌ **Formato incorrecto.**\n\n"
                        "**Usos válidos:**\n"
                        "• `/pack` - ZIP simple (sin compresión)\n"
                        "• `/pack 100` - Partes de 100MB\n"
                        "• `/pack compress` - ZIP con compresión\n"
                        "• `/pack 0` - Igual que 'compress'"
                    )
                    return
        
        # Enviar mensaje de estado inicial
        status_text = "📦 **Preparando empaquetado...**\n\n"
        
        if split_size:
            status_text += f"• 🔢 **Modo:** División en partes de {split_size}MB\n"
        elif compression:
            status_text += "• 💎 **Modo:** Compresión máxima\n"
        else:
            status_text += "• ⚡ **Modo:** ZIP rápido (sin compresión)\n"
        
        status_text += "• 📁 **Origen:** Carpeta 'downloads'\n"
        status_text += "• 🎯 **Destino:** Carpeta 'packed'\n"
        status_text += "\n⏳ Preparando archivos..."
        
        status_msg = await message.reply_text(status_text)
        
        # Ejecutar empaquetado en thread separado
        def run_packing():
            try:
                # Modificar split_size si es compresión
                actual_split_size = None if compression else split_size
                
                files, status_message = packing_service.pack_folder(
                    user_id, 
                    actual_split_size
                )
                return files, status_message, compression
            except Exception as e:
                logger.error(f"Error en empaquetado: {e}", exc_info=True)
                return None, f"Error crítico: {str(e)}", compression
        
        # Usar ThreadPoolExecutor con timeout
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(run_packing)
            
            try:
                files, status_message, used_compression = future.result(timeout=300)  # 5 minutos timeout
                
            except concurrent.futures.TimeoutError:
                await status_msg.edit_text(
                    "❌ **Tiempo de empaquetado excedido.**\n\n"
                    "El proceso tardó más de 5 minutos.\n"
                    "Posibles causas:\n"
                    "• 📁 Demasiados archivos\n"
                    "• 📏 Archivos muy grandes\n"
                    "• 🖥️ Sistema sobrecargado\n\n"
                    "**Sugerencias:**\n"
                    "• Divide en lotes más pequeños\n"
                    "• Usa `/pack 100` para dividir\n"
                    "• Intenta más tarde"
                )
                return
        
        # Procesar resultados
        if not files:
            await status_msg.edit_text(f"❌ {status_message}")
            return
        
        # Preparar respuesta según el tipo de resultado
        if len(files) == 1:
            file_info = files[0]
            total_files = file_info.get('total_files', 1)
            
            # Icono según compresión
            icon = "💎" if used_compression else "📦"
            compression_note = " (comprimido)" if used_compression else ""
            
            response_text = (
                f"{icon} **Empaquetado Completado{compression_note}**\n\n"
                f"**📊 Estadísticas:**\n"
                f"• 📁 Archivos originales: {total_files}\n"
                f"• 📦 Archivo generado: 1\n"
                f"• 📏 Tamaño total: {file_info['size_mb']:.1f} MB\n"
                f"• ⚡ Método: {'Compresión máxima' if used_compression else 'Sin compresión'}\n\n"
                f"**📄 Archivo:**\n"
                f"`{file_info['filename']}`\n\n"
                f"**🔗 Enlace de Descarga:**\n"
                f"[{file_info['filename']}]({file_info['url']})\n\n"
                f"**💡 Nota:** Usa `/cd packed` y `/list` para ver tus archivos empaquetados"
            )
            
            await status_msg.edit_text(
                response_text, 
                disable_web_page_preview=True
            )
            
        else:
            # Múltiples partes
            total_files = 0
            total_size = 0
            
            for file_info in files:
                if 'total_files' in file_info and total_files == 0:
                    total_files = file_info['total_files']
                total_size += file_info['size_mb']
            
            response_text = (
                f"📦 **Empaquetado Completado con División**\n\n"
                f"**📊 Estadísticas:**\n"
                f"• 📁 Archivos originales: {total_files}\n"
                f"• 🔢 Partes generadas: {len(files)}\n"
                f"• 📏 Tamaño total: {total_size:.1f} MB\n"
                f"• 📐 Tamaño por parte: {split_size} MB\n\n"
                f"**🔗 Enlaces de Descarga:**\n"
            )
            
            # Agregar cada parte (máximo 5 para no saturar)
            for i, file_info in enumerate(files[:5], 1):
                response_text += f"\n**Parte {i}:** [{file_info['filename']}]({file_info['url']})"
            
            if len(files) > 5:
                response_text += f"\n\n... y {len(files) - 5} partes más."
            
            response_text += (
                f"\n\n**💡 Notas:**\n"
                f"• Usa `/cd packed` y `/list` para ver todas las partes\n"
                f"• Para unir: `cat archivo.zip.001 archivo.zip.002 ... > archivo.zip`\n"
                f"• O usa 7-Zip/ WinRAR para unir automáticamente"
            )
            
            if len(response_text) > 4000:
                await status_msg.edit_text(
                    "✅ **Empaquetado completado con división**\n\n"
                    f"**📊 {len(files)} partes generadas, {total_files} archivos originales**\n"
                    "Los enlaces se enviarán en varios mensajes..."
                )
                
                # Enviar partes en mensajes separados
                for i, file_info in enumerate(files, 1):
                    part_text = (
                        f"**Parte {i}/{len(files)}:**\n"
                        f"📦 `{file_info['filename']}`\n"
                        f"📏 {file_info['size_mb']:.1f} MB\n"
                        f"🔗 [Descargar]({file_info['url']})"
                    )
                    await message.reply_text(part_text, disable_web_page_preview=True)
            else:
                await status_msg.edit_text(
                    response_text, 
                    disable_web_page_preview=True
                )
        
        logger.info(f"✅ Empaquetado completado para usuario {user_id}: {len(files)} archivos")
        
        update_user_activity(user_id)

    except Exception as e:
        logger.error(f"Error en comando /pack: {e}", exc_info=True)
        await message.reply_text(
            "❌ **Error en el proceso de empaquetado.**\n\n"
            "Detalles técnicos:\n"
            f"`{str(e)[:100]}{'...' if len(str(e)) > 100 else ''}`\n\n"
            "**Sugerencias:**\n"
            "• Verifica que tengas archivos en 'downloads'\n"
            "• Usa `/status` para ver estado del sistema\n"
            "• Intenta con menos archivos"
        )

@rate_limit(1)
async def queue_command(client: Client, message: Message):
    """Maneja el comando /queue - Ver estado de la cola de descargas"""
    try:
        user_id = message.from_user.id
        
        if user_id not in user_queues or not user_queues[user_id]:
            await message.reply_text("📭 **Cola vacía**\n\nNo hay archivos en cola de descarga.")
            return
        
        queue_size = len(user_queues[user_id])
        current_processing = "Sí" if user_id in user_current_processing else "No"
        
        queue_text = f"📋 **Estado de la Cola - {queue_size} archivo(s)**\n\n"
        
        for i, msg in enumerate(user_queues[user_id]):
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
        
        update_user_activity(user_id)
        
    except Exception as e:
        logger.error(f"Error en /queue: {e}")
        await message.reply_text("❌ Error al obtener estado de la cola.")

@rate_limit(1)
async def clear_queue_command(client: Client, message: Message):
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
        
        await message.reply_text(f"🗑️ **Cola limpiada**\n\nSe removieron {queue_size} archivos de la cola.")
        
        update_user_activity(user_id)
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Error al limpiar la cola.")

@rate_limit(1)
async def cleanup_command(client: Client, message: Message):
    """Limpia archivos temporales y optimiza el sistema"""
    try:
        user_id = message.from_user.id
        status_msg = await message.reply_text("🧹 **Limpiando archivos temporales...**")
        
        # Limpiar caché del servicio de archivos
        file_service._clean_cache()
        
        # Obtener estadísticas de almacenamiento
        total_size = file_service.get_user_storage_usage(user_id)
        size_mb = total_size / (1024 * 1024)
        
        # Limpiar directorios temporales del sistema
        import shutil
        temp_dirs = ['temp', '__pycache__']
        cleaned_count = 0
        
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    os.makedirs(temp_dir, exist_ok=True)
                    cleaned_count += 1
                except:
                    pass
        
        await status_msg.edit_text(
            f"✅ **Limpieza completada**\n\n"
            f"• 🧹 Directorios temporales limpiados: {cleaned_count}\n"
            f"• 💾 Espacio usado actual: {size_mb:.2f} MB\n"
            f"• 🚀 Sistema optimizado para mejor rendimiento"
        )
        
        update_user_activity(user_id)
        
    except Exception as e:
        logger.error(f"Error en comando cleanup: {e}")
        await message.reply_text("❌ Error durante la limpieza.")

# ===== MANEJO DE ARCHIVOS MEJORADO =====

async def handle_file(client: Client, message: Message):
    """Manejo profesional de archivos con todas las optimizaciones de Pyrogram"""
    try:
        user = message.from_user
        user_id = user.id
        
        logger.info(f"📥 Archivo recibido de {user_id} (@{user.username})")
        
        # Extraer información del archivo
        file_info = await _extract_file_info(message)
        if not file_info:
            await message.reply_text("❌ No se pudo procesar el archivo. Formato no soportado.")
            return
        
        file_size = file_info['size']
        
        # Verificar límite de tamaño
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            await message.reply_text(
                f"❌ **Archivo demasiado grande**\n\n"
                f"**📏 Tamaño del archivo:** {size_mb:.1f} MB\n"
                f"**📏 Límite permitido:** {MAX_FILE_SIZE_MB} MB\n\n"
                f"**💡 Sugerencias:**\n"
                f"• Comprime el archivo antes de enviarlo\n"
                f"• Divide en partes más pequeñas\n"
                f"• Usa un servicio de almacenamiento en la nube\n"
                f"• Contacta soporte para límites especiales"
            )
            return
        
        # Inicializar cola si no existe
        if user_id not in user_queues:
            user_queues[user_id] = []
        
        # Agregar a cola
        user_queues[user_id].append(message)
        
        # Enviar confirmación con información detallada
        queue_position = len(user_queues[user_id])
        
        confirmation_text = (
            f"✅ **Archivo recibido y agregado a la cola**\n\n"
            f"**📄 Archivo:** `{file_info['name'][:50]}{'...' if len(file_info['name']) > 50 else ''}`\n"
            f"**📏 Tamaño:** {file_service.format_bytes(file_size)}\n"
            f"**📋 Posición en cola:** #{queue_position}\n\n"
        )
        
        if queue_position == 1:
            confirmation_text += "⚡ **Será procesado inmediatamente...**"
        else:
            confirmation_text += "⏳ **Será procesado en cuanto termine el archivo actual.**"
        
        confirmation_text += "\n\n📊 Usa `/queue` para ver el estado de la cola."
        
        await message.reply_text(confirmation_text)
        
        # Si es el primer archivo en cola, procesar inmediatamente
        if queue_position == 1:
            await process_file_queue(client, user_id)
        
        update_user_activity(user_id)
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text(
                f"❌ **Error al procesar archivo**\n\n"
                f"Detalle: `{str(e)[:100]}`\n\n"
                f"Por favor intenta nuevamente o contacta soporte."
            )
        except:
            pass

async def _extract_file_info(message: Message) -> Optional[dict]:
    """Extrae información detallada del archivo usando Pyrogram"""
    try:
        file_info = {
            'name': 'archivo',
            'size': 0,
            'type': 'desconocido',
            'unique_id': None,
            'file_id': None
        }
        
        if message.document:
            doc = message.document
            file_info.update({
                'name': doc.file_name or 'documento',
                'size': doc.file_size or 0,
                'type': 'documento',
                'unique_id': doc.file_unique_id,
                'file_id': doc.file_id,
                'mime_type': doc.mime_type
            })
            
        elif message.video:
            video = message.video
            file_info.update({
                'name': video.file_name or 'video.mp4',
                'size': video.file_size or 0,
                'type': 'video',
                'unique_id': video.file_unique_id,
                'file_id': video.file_id,
                'duration': video.duration,
                'width': video.width,
                'height': video.height
            })
            
        elif message.audio:
            audio = message.audio
            title = audio.title or "Audio"
            performer = audio.performer or "Desconocido"
            file_info.update({
                'name': f"{performer} - {title}.mp3",
                'size': audio.file_size or 0,
                'type': 'audio',
                'unique_id': audio.file_unique_id,
                'file_id': audio.file_id,
                'duration': audio.duration,
                'performer': performer,
                'title': title
            })
            
        elif message.photo:
            # Usar la foto de mayor calidad (última en la lista)
            photo = message.photo[-1]
            file_info.update({
                'name': f"foto_{message.id}.jpg",
                'size': photo.file_size or 0,
                'type': 'foto',
                'unique_id': photo.file_unique_id,
                'file_id': photo.file_id,
                'width': photo.width,
                'height': photo.height
            })
            
        elif message.sticker:
            sticker = message.sticker
            file_info.update({
                'name': f"sticker_{sticker.file_unique_id}.webp",
                'size': sticker.file_size or 0,
                'type': 'sticker',
                'unique_id': sticker.file_unique_id,
                'file_id': sticker.file_id,
                'emoji': sticker.emoji or "🎭",
                'is_animated': sticker.is_animated,
                'is_video': sticker.is_video
            })
            
        else:
            return None
        
        return file_info
        
    except Exception as e:
        logger.error(f"Error extrayendo info de archivo: {e}")
        return None

async def process_file_queue(client: Client, user_id: int):
    """Procesa la cola de archivos de manera optimizada"""
    try:
        if user_id not in user_queues or not user_queues[user_id]:
            return
        
        total_files = len(user_queues[user_id])
        user_batch_totals[user_id] = total_files
        
        logger.info(f"🔄 Procesando lote de {total_files} archivos para usuario {user_id}")
        
        current_position = 0
        
        while user_queues.get(user_id) and user_queues[user_id]:
            message = user_queues[user_id][0]
            current_position += 1
            
            logger.info(f"📁 Procesando archivo {current_position}/{total_files}")
            
            await process_single_file(client, message, user_id, current_position, total_files)
            
            # Pequeña pausa entre archivos para no saturar
            await asyncio.sleep(1)
        
        # Limpiar después de procesar todo
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]
            
        logger.info(f"✅ Lote completado para usuario {user_id}")
                
    except Exception as e:
        logger.error(f"Error en process_file_queue: {e}", exc_info=True)
        # Limpiar cola en caso de error
        if user_id in user_queues:
            user_queues[user_id] = []
        if user_id in user_batch_totals:
            del user_batch_totals[user_id]

async def process_single_file(client: Client, message: Message, user_id: int, 
                             current_position: int, total_files: int):
    """Procesa un solo archivo con todas las optimizaciones"""
    start_time = time.time()
    
    try:
        # Extraer información del archivo
        file_info = await _extract_file_info(message)
        if not file_info:
            logger.warning(f"No se pudo extraer info del mensaje {message.id}")
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            return
        
        # Crear directorio de usuario
        user_dir = file_service.get_user_directory(user_id, "downloads")
        
        # Sanitizar y generar nombre único
        sanitized_name = file_service.sanitize_filename(file_info['name'])
        stored_filename = sanitized_name
        
        # Verificar si ya existe y generar nombre único
        counter = 1
        base_name, ext = os.path.splitext(sanitized_name)
        file_path = os.path.join(user_dir, stored_filename)
        
        while os.path.exists(file_path):
            stored_filename = f"{base_name}_{counter}{ext}"
            file_path = os.path.join(user_dir, stored_filename)
            counter += 1
        
        # Registrar archivo
        file_number = file_service.register_file(user_id, file_info['name'], stored_filename, "downloads")
        logger.info(f"📝 Archivo registrado: #{file_number} - {file_info['name']}")
        
        # Crear mensaje de progreso inicial
        initial_message = progress_service.create_progress_message(
            filename=file_info['name'],
            current=0,
            total=file_info['size'],
            speed=0,
            user_first_name=message.from_user.first_name,
            process_type="Subiendo",
            current_file=current_position,
            total_files=total_files
        )
        
        progress_msg = await message.reply_text(initial_message)
        
        # Marcar como procesando
        user_current_processing[user_id] = True
        
        # Configurar callback de progreso
        progress_data = {
            'last_update': 0,
            'last_speed': 0,
            'start_time': start_time
        }
        
        async def progress_callback(current: int, total: int):
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
                
                # Actualizar cada 0.5 segundos o al finalizar
                if current_time - last_update >= 0.5 or current == total:
                    progress_message = progress_service.create_progress_message(
                        filename=file_info['name'],
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
        
        # Descargar archivo
        logger.info(f"⚡ Iniciando descarga: {file_info['name']}")
        
        success, downloaded = await fast_download_service.download_with_retry(
            client=client,
            message=message,
            file_path=file_path,
            progress_callback=progress_callback
        )
        
        if not success or not os.path.exists(file_path):
            await progress_msg.edit_text(
                "❌ **Error en la descarga**\n\n"
                "El archivo no se pudo descargar correctamente.\n"
                "Posibles causas:\n"
                "• Problemas de conexión\n"
                "• Archivo corrupto\n"
                "• Tiempo de espera excedido\n\n"
                "Por favor intenta enviarlo nuevamente."
            )
            
            # Limpiar archivo incompleto
            if os.path.exists(file_path):
                os.remove(file_path)
            
            if user_id in user_queues and user_queues[user_id]:
                user_queues[user_id].pop(0)
            return
        
        # Verificar integridad
        final_size = os.path.getsize(file_path)
        if file_info['size'] > 0 and final_size < file_info['size'] * 0.95:
            logger.warning(f"⚠️ Posible descarga incompleta: esperado {file_info['size']}, obtenido {final_size}")
        
        # Generar URL
        download_url = file_service.create_download_url(user_id, stored_filename)
        size_mb = final_size / (1024 * 1024)
        
        # Información de siguiente archivo en cola
        queue_info = ""
        next_files_count = len(user_queues[user_id]) - 1 if user_id in user_queues and user_queues[user_id] else 0
        
        if next_files_count > 0:
            queue_info = f"\n\n⏭️ **Siguiente archivo en cola...** ({next_files_count} restantes)"
        
        # Mensaje de éxito
        success_text = (
            f"✅ **Archivo #{file_number} Almacenado!**\n\n"
            f"**📄 Nombre:** `{file_info['name']}`\n"
            f"**📏 Tamaño:** {size_mb:.2f} MB\n"
            f"**⏱️ Tiempo:** {time.time() - start_time:.1f}s\n\n"
            f"**🔗 Enlace de Descarga:**\n"
            f"[{file_info['name']}]({download_url})\n\n"
            f"**📁 Ubicación:** Carpeta `downloads`{queue_info}"
        )
        
        # Teclado rápido para acciones
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("📥 Descargar ahora", url=download_url),
                InlineKeyboardButton("📁 Ver en carpeta", callback_data="folder_downloads")
            ],
            [
                InlineKeyboardButton("🔄 Renombrar", callback_data=f"rename_{file_number}"),
                InlineKeyboardButton("📦 Agregar a ZIP", callback_data=f"add_zip_{file_number}")
            ]
        ])
        
        await progress_msg.edit_text(
            success_text,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
        
        logger.info(f"✅ Archivo guardado: {stored_filename} para usuario {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Error procesando archivo individual: {e}", exc_info=True)
        
        try:
            await message.reply_text(
                f"❌ **Error procesando archivo**\n\n"
                f"Detalle: `{str(e)[:150]}`\n\n"
                f"El archivo se ha removido de la cola.\n"
                f"Por favor intenta enviarlo nuevamente."
            )
        except:
            pass
        
    finally:
        # Limpiar de la cola
        if user_id in user_queues and user_queues[user_id]:
            user_queues[user_id].pop(0)
            
        # Quitar marca de procesamiento
        if user_id in user_current_processing:
            del user_current_processing[user_id]

# ===== HANDLER DE CALLBACKS =====
async def handle_callback_query(client: Client, callback_query):
    """Maneja las respuestas de los botones inline"""
    try:
        user_id = callback_query.from_user.id
        data = callback_query.data
        
        if data == "quick_list":
            # Simular comando /list
            await list_command(client, callback_query.message)
            
        elif data == "quick_pack":
            # Simular comando /pack
            await pack_command(client, callback_query.message)
            
        elif data == "quick_help":
            # Simular comando /help
            await help_command(client, callback_query.message)
            
        elif data == "folder_downloads":
            # Cambiar a carpeta downloads
            session = get_user_session(user_id)
            session['current_folder'] = 'downloads'
            await callback_query.message.edit_text(
                "📂 **Cambiado a carpeta:** `downloads`\n\n"
                "Usa `/list` para ver tus archivos."
            )
        
        elif data.startswith("rename_"):
            # Solicitar nuevo nombre para renombrar
            file_number = data.replace("rename_", "")
            await callback_query.message.reply_text(
                f"✏️ **Renombrar archivo #{file_number}**\n\n"
                f"Envía el nuevo nombre para el archivo #{file_number}.\n"
                f"Ejemplo: `mi_documento.pdf`"
            )
        
        elif data.startswith("confirm_clear_"):
            # Confirmar vaciado de carpeta
            folder = data.replace("confirm_clear_", "")
            success, message = file_service.delete_all_files(user_id, folder)
            
            if success:
                await callback_query.message.edit_text(f"✅ **{message}**")
            else:
                await callback_query.message.edit_text(f"❌ **{message}**")
        
        elif data == "cancel_clear":
            # Cancelar vaciado
            await callback_query.message.edit_text("❌ **Operación cancelada.**")
        
        # Responder al callback para quitar el "reloj de carga"
        await callback_query.answer()
        
        update_user_activity(user_id)
        
    except Exception as e:
        logger.error(f"Error en callback handler: {e}")
        await callback_query.answer("❌ Error procesando la solicitud", show_alert=True)

# ===== SETUP DE HANDLERS =====
def setup_handlers(client: Client):
    """Configura todos los handlers del bot"""
    
    # Comandos básicos
    client.on_message(filters.command("start") & filters.private)(start_command)
    client.on_message(filters.command("help") & filters.private)(help_command)
    client.on_message(filters.command("status") & filters.private)(status_command)
    
    # Navegación y gestión
    client.on_message(filters.command("cd") & filters.private)(cd_command)
    client.on_message(filters.command("list") & filters.private)(list_command)
    client.on_message(filters.command("delete") & filters.private)(delete_command)
    client.on_message(filters.command("clear") & filters.private)(clear_command)
    client.on_message(filters.command("rename") & filters.private)(rename_command)
    
    # Empaquetado
    client.on_message(filters.command("pack") & filters.private)(pack_command)
    
    # Gestión de cola
    client.on_message(filters.command("queue") & filters.private)(queue_command)
    client.on_message(filters.command("clearqueue") & filters.private)(clear_queue_command)
    
    # Utilidades
    client.on_message(filters.command("cleanup") & filters.private)(cleanup_command)
    
    # Manejo de archivos (todos los tipos soportados)
    client.on_message(
        (filters.document | filters.video | filters.audio | 
         filters.photo | filters.sticker) & filters.private
    )(handle_file)
    
    # Handler para callback queries (botones inline)
    client.on_callback_query()(handle_callback_query)
    
    # Handler para mensajes de texto no comandos
    @client.on_message(filters.text & filters.private & ~filters.command)
    async def handle_text(client, message):
        """Maneja mensajes de texto que no son comandos"""
        await message.reply_text(
            "🤖 **Comando no reconocido**\n\n"
            "Usa `/help` para ver todos los comandos disponibles.\n"
            "O simplemente envía un archivo para comenzar."
        )
        update_user_activity(message.from_user.id)
    
    logger.info("✅ Handlers configurados profesionalmente")