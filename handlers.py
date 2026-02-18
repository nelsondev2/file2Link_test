"""
Manejadores del bot de Telegram.

Implementa todos los comandos y la recepción de archivos.
Mensajes diseñados para ser claros, amigables y sin jerga técnica.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict, deque
from typing import Optional

from pyrogram import Client, filters
from pyrogram.types import Message

from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB
from downloader import downloader
from packer import PackingError, packer
from progress import build_progress_message
from storage import storage
from system_monitor import monitor

logger = logging.getLogger(__name__)

# ── Estado por usuario (en memoria) ───────────────────────────────────────────

# Carpeta activa: "downloads" (predeterminado) o "packed"
_active_folder: dict[int, str] = defaultdict(lambda: "downloads")

# Cola de mensajes con archivos pendientes de procesar
_queues: dict[int, deque[Message]] = defaultdict(deque)

# Semáforos para procesar cola de cada usuario secuencialmente
_processing: set[int] = set()


# ── Helpers ────────────────────────────────────────────────────────────────────

FOLDER_LABELS = {
    "downloads": "📥 Recibidos",
    "packed":    "📦 Empaquetados",
}


def _folder_label(folder: str) -> str:
    return FOLDER_LABELS.get(folder, folder)


def _file_type_label(message: Message) -> str:
    if message.document: return "Documento"
    if message.video:    return "Video"
    if message.audio:    return "Audio"
    if message.photo:    return "Foto"
    return "Archivo"


def _file_obj(message: Message):
    return (
        message.document
        or message.video
        or message.audio
        or (message.photo and message.photo[-1])
    )


def _file_size(message: Message) -> int:
    obj = _file_obj(message)
    return getattr(obj, "file_size", 0) or 0


def _original_name(message: Message) -> str:
    if message.document and message.document.file_name:
        return message.document.file_name
    if message.video and message.video.file_name:
        return message.video.file_name
    if message.audio and message.audio.file_name:
        return message.audio.file_name
    if message.photo:
        return f"foto_{message.id}.jpg"
    return "archivo"


async def _safe_edit(msg: Message, text: str, **kwargs) -> None:
    """Edita un mensaje ignorando errores de 'mensaje no modificado'."""
    try:
        await msg.edit_text(text, **kwargs)
    except Exception:
        pass


async def _send_long(message: Message, text: str, **kwargs) -> None:
    """Envía texto partiéndolo si supera el límite de Telegram (4096 chars)."""
    limit = 4000
    if len(text) <= limit:
        await message.reply_text(text, **kwargs)
        return
    parts = []
    while text:
        parts.append(text[:limit])
        text = text[limit:]
    for part in parts:
        await message.reply_text(part, **kwargs)


# ── /start ─────────────────────────────────────────────────────────────────────

async def cmd_start(client: Client, message: Message) -> None:
    name = message.from_user.first_name
    await message.reply_text(
        f"👋 ¡Hola, {name}! Soy tu asistente de archivos.\n\n"
        "**¿Qué puedo hacer por ti?**\n"
        "• Guarda cualquier archivo que me envíes y te doy un enlace de descarga directo.\n"
        "• Organiza tus archivos en carpetas, renómbralos o elimínalos.\n"
        "• Empaqueta todo en un ZIP listo para descargar.\n\n"
        "**Comandos principales**\n"
        "📂 `/carpeta` — Ver en qué carpeta estás\n"
        "📋 `/lista` — Ver tus archivos\n"
        "📦 `/empaquetar` — Crear un ZIP con tus archivos\n"
        "ℹ️ `/ayuda` — Guía completa de comandos\n\n"
        "¡Empieza enviándome un archivo! 🚀"
    )


# ── /ayuda ─────────────────────────────────────────────────────────────────────

async def cmd_help(client: Client, message: Message) -> None:
    await message.reply_text(
        "📖 **Guía de uso**\n\n"

        "**📂 Carpetas**\n"
        "`/carpeta recibidos` — Cambiar a carpeta de archivos recibidos\n"
        "`/carpeta empaquetados` — Cambiar a carpeta de ZIPs\n"
        "`/carpeta` — Ver en cuál estás ahora\n\n"

        "**📋 Gestión de archivos**\n"
        "`/lista` — Ver todos tus archivos con sus enlaces\n"
        "`/lista 2` — Ver la página 2\n"
        "`/renombrar 3 nuevo nombre` — Cambiar el nombre del archivo #3\n"
        "`/eliminar 5` — Eliminar el archivo #5\n"
        "`/vaciar` — Eliminar todos los archivos de la carpeta actual\n\n"

        "**📦 Empaquetado**\n"
        "`/empaquetar` — Crear un ZIP con todos tus archivos\n"
        "`/empaquetar 200` — Crear ZIP partido en partes de 200 MB\n\n"

        "**🔄 Cola de subida**\n"
        "`/cola` — Ver qué archivos están esperando procesarse\n"
        "`/cancelar` — Cancelar los archivos que están en espera\n\n"

        "**📊 Información**\n"
        "`/estado` — Ver tu espacio usado y el estado del servidor\n\n"

        "💡 **Consejo:** Puedes enviar varios archivos a la vez, "
        "los procesaré en orden uno por uno."
    )


# ── /carpeta ───────────────────────────────────────────────────────────────────

FOLDER_MAP = {
    "recibidos":     "downloads",
    "downloads":     "downloads",
    "empaquetados":  "packed",
    "packed":        "packed",
}

async def cmd_folder(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    args = message.text.split(maxsplit=1)

    if len(args) == 1:
        current = _active_folder[user_id]
        await message.reply_text(
            f"📂 Estás en la carpeta **{_folder_label(current)}**.\n\n"
            "Para cambiar:\n"
            "`/carpeta recibidos` — Archivos que recibiste\n"
            "`/carpeta empaquetados` — Tus ZIPs"
        )
        return

    target = args[1].strip().lower()
    folder = FOLDER_MAP.get(target)
    if folder is None:
        await message.reply_text(
            "❓ No reconozco esa carpeta.\n\n"
            "Carpetas disponibles:\n"
            "• `/carpeta recibidos`\n"
            "• `/carpeta empaquetados`"
        )
        return

    _active_folder[user_id] = folder
    await message.reply_text(
        f"✅ Ahora estás en la carpeta **{_folder_label(folder)}**.\n"
        "Usa `/lista` para ver tus archivos."
    )


# ── /lista ─────────────────────────────────────────────────────────────────────

PAGE_SIZE = 8

async def cmd_list(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    folder = _active_folder[user_id]
    args = message.text.split()
    page = int(args[1]) if len(args) > 1 and args[1].isdigit() else 1

    files = storage.list_files(user_id, folder)

    if not files:
        tip = (
            "Envíame cualquier archivo para guardarlo aquí."
            if folder == "downloads"
            else "Usa `/empaquetar` para crear un ZIP."
        )
        await message.reply_text(
            f"📭 Tu carpeta **{_folder_label(folder)}** está vacía.\n\n{tip}"
        )
        return

    total_pages = max(1, (len(files) + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(1, min(page, total_pages))
    start = (page - 1) * PAGE_SIZE
    page_files = files[start : start + PAGE_SIZE]

    lines = [
        f"📂 **{_folder_label(folder)}** • {len(files)} archivo{'s' if len(files) != 1 else ''}  "
        f"(página {page}/{total_pages})\n"
    ]

    for f in page_files:
        lines.append(f"**#{f.number}** `{f.name}`")
        lines.append(f"  📏 {f.size_mb:.1f} MB  •  🔗 [Descargar]({f.url})\n")

    nav = []
    if page > 1:
        nav.append(f"`/lista {page - 1}` ← anterior")
    if page < total_pages:
        nav.append(f"siguiente → `/lista {page + 1}`")
    if nav:
        lines.append("  ".join(nav) + "\n")

    lines.append(
        "**Acciones:** `/eliminar <nº>` · `/renombrar <nº> <nombre>` · `/vaciar`"
    )

    await _send_long(message, "\n".join(lines), disable_web_page_preview=True)


# ── /eliminar ──────────────────────────────────────────────────────────────────

async def cmd_delete(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    folder = _active_folder[user_id]
    args = message.text.split()

    if len(args) < 2 or not args[1].isdigit():
        await message.reply_text(
            "Para eliminar un archivo escribe:\n"
            "`/eliminar <número>`\n\n"
            "Ejemplo: `/eliminar 3`\n"
            "Usa `/lista` para ver los números."
        )
        return

    ok, msg = storage.delete_file(user_id, int(args[1]), folder)
    icon = "✅" if ok else "❌"
    await message.reply_text(f"{icon} {msg}")


# ── /vaciar ────────────────────────────────────────────────────────────────────

async def cmd_clear(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    folder = _active_folder[user_id]
    ok, msg = storage.delete_all_files(user_id, folder)
    icon = "✅" if ok else "❌"
    await message.reply_text(f"{icon} {msg}")


# ── /renombrar ─────────────────────────────────────────────────────────────────

async def cmd_rename(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    folder = _active_folder[user_id]
    parts = message.text.split(maxsplit=2)

    if len(parts) < 3 or not parts[1].isdigit():
        await message.reply_text(
            "Para renombrar un archivo escribe:\n"
            "`/renombrar <número> <nuevo nombre>`\n\n"
            "Ejemplo: `/renombrar 2 mi_proyecto_final`\n"
            "Usa `/lista` para ver los números."
        )
        return

    number = int(parts[1])
    new_name = parts[2].strip()
    if not new_name:
        await message.reply_text("El nuevo nombre no puede estar vacío.")
        return

    ok, msg, url = storage.rename_file(user_id, number, new_name, folder)
    if ok:
        await message.reply_text(
            f"✅ {msg}\n\n🔗 [Nuevo enlace]({url})",
            disable_web_page_preview=True,
        )
    else:
        await message.reply_text(f"❌ {msg}")


# ── /estado ────────────────────────────────────────────────────────────────────

async def cmd_status(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    used = storage.storage_used(user_id)
    downloads = storage.list_files(user_id, "downloads")
    packed = storage.list_files(user_id, "packed")
    sys = monitor.status()

    server_icon = "✅" if sys["available"] else "⚠️"
    server_txt = "Disponible" if sys["available"] else "Ocupado"

    await message.reply_text(
        f"📊 **Tu espacio**\n"
        f"• Archivos recibidos: **{len(downloads)}**\n"
        f"• Archivos empaquetados: **{len(packed)}**\n"
        f"• Espacio usado: **{storage.format_size(used)}**\n\n"
        f"🖥️ **Servidor**\n"
        f"• Estado: {server_icon} {server_txt}\n"
        f"• CPU: {sys['cpu_percent']}%  •  Memoria: {sys['memory_percent']}%\n\n"
        f"📏 Límite por archivo: {MAX_FILE_SIZE_MB} MB"
    )


# ── /empaquetar ────────────────────────────────────────────────────────────────

async def cmd_pack(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    parts = message.text.split()
    split_mb: Optional[int] = None

    if len(parts) > 1:
        if not parts[1].isdigit():
            await message.reply_text(
                "Formato incorrecto.\n\n"
                "Ejemplos:\n"
                "`/empaquetar` — Un solo ZIP\n"
                "`/empaquetar 200` — ZIP partido en partes de 200 MB"
            )
            return
        split_mb = int(parts[1])
        if split_mb <= 0:
            await message.reply_text("El tamaño de cada parte debe ser mayor a 0 MB.")
            return
        if split_mb > 500:
            await message.reply_text("El tamaño máximo por parte es 500 MB.")
            return

    status_msg = await message.reply_text(
        "⏳ Empaquetando tus archivos, un momento…"
    )

    try:
        loop = asyncio.get_event_loop()
        results, summary = await loop.run_in_executor(
            None, packer.pack, user_id, split_mb
        )
    except PackingError as exc:
        await _safe_edit(status_msg, f"❌ {exc}")
        return
    except Exception as exc:
        logger.error("Error inesperado en /empaquetar: %s", exc, exc_info=True)
        await _safe_edit(status_msg, "❌ Ocurrió un problema al empaquetar. Inténtalo de nuevo.")
        return

    # ── Construir respuesta ──────────────────────────────────────────────────
    if len(results) == 1:
        r = results[0]
        text = (
            f"✅ **¡Listo!** {r.total_source_files} archivos empaquetados\n\n"
            f"📄 `{r.filename}`\n"
            f"📏 {r.size_mb:.1f} MB\n\n"
            f"🔗 [Descargar ZIP]({r.url})\n\n"
            "Encuéntralo también en `/carpeta empaquetados` → `/lista`"
        )
        await _safe_edit(status_msg, text, disable_web_page_preview=True)
    else:
        total_mb = sum(r.size_mb for r in results)
        header = (
            f"✅ **¡Listo!** {results[0].total_source_files} archivos → "
            f"{len(results)} partes ({total_mb:.1f} MB en total)\n\n"
            "**Para unir y extraer (Linux/Mac):**\n"
            f"`cat *.zip.* > archivo.zip && unzip archivo.zip`\n\n"
            "🔗 **Enlace de descarga de cada parte:**\n"
        )

        # Construir lista de enlaces
        links = "\n".join(
            f"**Parte {i+1}** ({r.size_mb:.0f} MB)\n{r.url}"
            for i, r in enumerate(results)
        )
        full = header + links + "\n\nEncuéntralos en `/carpeta empaquetados` → `/lista`"

        if len(full) <= 4000:
            await _safe_edit(status_msg, full, disable_web_page_preview=True)
        else:
            await _safe_edit(
                status_msg,
                f"✅ **¡Listo!** Se crearon {len(results)} partes ({total_mb:.1f} MB). "
                "Los enlaces se envían a continuación.",
            )
            for i in range(0, len(results), 8):
                chunk = results[i : i + 8]
                chunk_text = "\n\n".join(
                    f"**Parte {i+j+1}** ({r.size_mb:.0f} MB)\n{r.url}"
                    for j, r in enumerate(chunk)
                )
                await message.reply_text(chunk_text, disable_web_page_preview=True)


# ── /cola ──────────────────────────────────────────────────────────────────────

async def cmd_queue(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    q = _queues[user_id]

    if not q:
        await message.reply_text("✅ No hay archivos esperando, todo está al día.")
        return

    items = "\n".join(
        f"• {_file_type_label(m)}: `{_original_name(m)}`" for m in q
    )
    processing = "🔄 Procesando ahora…\n\n" if user_id in _processing else ""
    await message.reply_text(
        f"{processing}⏳ **En espera ({len(q)} archivo{'s' if len(q) != 1 else ''}):**\n{items}"
    )


# ── /cancelar ──────────────────────────────────────────────────────────────────

async def cmd_cancel(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    q = _queues[user_id]
    count = len(q)
    q.clear()

    if count == 0:
        await message.reply_text("No había archivos en espera.")
    else:
        await message.reply_text(
            f"🗑️ Se cancelaron {count} archivo{'s' if count != 1 else ''} en espera.\n"
            "El que se estaba procesando terminará normalmente."
        )


# ── Recepción de archivos ──────────────────────────────────────────────────────

async def handle_file(client: Client, message: Message) -> None:
    user_id = message.from_user.id
    size = _file_size(message)

    if size > MAX_FILE_SIZE:
        await message.reply_text(
            f"⚠️ Ese archivo es demasiado grande.\n\n"
            f"• Tu archivo: **{storage.format_size(size)}**\n"
            f"• Límite permitido: **{MAX_FILE_SIZE_MB} MB**\n\n"
            "Divídelo en partes más pequeñas e inténtalo de nuevo."
        )
        return

    queue = _queues[user_id]
    queue.append(message)

    if user_id not in _processing:
        asyncio.create_task(_process_queue(client, user_id))


async def _process_queue(client: Client, user_id: int) -> None:
    """Procesa la cola de un usuario de forma secuencial."""
    _processing.add(user_id)
    try:
        while _queues[user_id]:
            msg = _queues[user_id][0]
            total = len(_queues[user_id])
            position = 1  # siempre es el primero de la cola
            await _process_one(client, msg, user_id, position, total)
            if _queues[user_id]:
                _queues[user_id].popleft()
            await asyncio.sleep(0.5)
    except Exception as exc:
        logger.error("Error en cola de usuario %d: %s", user_id, exc, exc_info=True)
        _queues[user_id].clear()
    finally:
        _processing.discard(user_id)


async def _process_one(
    client: Client,
    message: Message,
    user_id: int,
    position: int,
    total_in_queue: int,
) -> None:
    """Descarga y registra un único archivo."""
    original = _original_name(message)
    size = _file_size(message)
    file_type = _file_type_label(message)

    user_dir = storage.user_directory(user_id, "downloads")
    safe_name = storage.sanitize_filename(original)
    stored_name = storage.unique_stored_name(user_dir, safe_name)
    dest_path = os.path.join(user_dir, stored_name)

    # Mensaje de progreso inicial
    prog_msg = await message.reply_text(
        build_progress_message(
            filename=original,
            current=0,
            total=size,
            position=position,
            total_files=total_in_queue,
        )
    )

    start = time.monotonic()

    async def on_progress(current: int, total: int) -> None:
        elapsed = time.monotonic() - start
        speed = current / max(elapsed, 0.001)
        await _safe_edit(
            prog_msg,
            build_progress_message(
                filename=original,
                current=current,
                total=total,
                speed=speed,
                position=position,
                total_files=total_in_queue,
            ),
        )

    ok = await downloader.download_with_retry(
        client=client,
        message=message,
        dest_path=dest_path,
        on_progress=on_progress,
    )

    if not ok or not os.path.exists(dest_path):
        await _safe_edit(
            prog_msg,
            "❌ No pude guardar ese archivo. Inténtalo de nuevo más tarde.",
        )
        return

    final_size = os.path.getsize(dest_path)
    num = storage.register_file(user_id, original, stored_name, "downloads")
    url = storage._build_url(user_id, "downloads", stored_name)

    more = len(_queues[user_id]) - 1
    footer = f"\n⏭️ Siguiente en cola: {more} archivo{'s' if more != 1 else ''}" if more > 0 else ""

    await _safe_edit(
        prog_msg,
        f"✅ **Guardado correctamente**\n\n"
        f"📄 `{original}`\n"
        f"📏 {storage.format_size(final_size)}\n\n"
        f"🔗 [Descargar]({url})"
        f"{footer}",
        disable_web_page_preview=True,
    )

    logger.info("Archivo guardado: #%d %s (usuario %d)", num, stored_name, user_id)


# ── Registro de handlers ───────────────────────────────────────────────────────

def register(client: Client) -> None:
    """Registra todos los handlers en el cliente de Pyrogram."""
    prv = filters.private

    client.on_message(filters.command("start")        & prv)(cmd_start)
    client.on_message(filters.command("ayuda")        & prv)(cmd_help)
    client.on_message(filters.command("help")         & prv)(cmd_help)

    client.on_message(filters.command("carpeta")      & prv)(cmd_folder)
    client.on_message(filters.command("lista")        & prv)(cmd_list)
    client.on_message(filters.command("eliminar")     & prv)(cmd_delete)
    client.on_message(filters.command("vaciar")       & prv)(cmd_clear)
    client.on_message(filters.command("renombrar")    & prv)(cmd_rename)

    client.on_message(filters.command("empaquetar")   & prv)(cmd_pack)

    client.on_message(filters.command("cola")         & prv)(cmd_queue)
    client.on_message(filters.command("cancelar")     & prv)(cmd_cancel)
    client.on_message(filters.command("estado")       & prv)(cmd_status)

    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) & prv
    )(handle_file)
