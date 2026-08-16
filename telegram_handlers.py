import os
import logging
import time
import asyncio
import concurrent.futures

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from load_manager import load_manager
from file_service import file_service
from progress_service import progress_service
from packing_service import packing_service
from download_service import download_service
from config import MAX_FILE_SIZE, MAX_FILE_SIZE_MB, MAX_QUEUE_PER_USER, QUEUE_PROCESSING_DELAY

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
#  SESIONES Y COLA POR USUARIO
# ─────────────────────────────────────────────

user_sessions: dict = {}
user_queues: dict = {}
user_queue_locks: dict = {}
user_processing: dict = {}


def get_session(user_id: int) -> dict:
    if user_id not in user_sessions:
        user_sessions[user_id] = {"current_folder": "downloads"}
    return user_sessions[user_id]


def get_queue_lock(user_id: int) -> asyncio.Lock:
    if user_id not in user_queue_locks:
        user_queue_locks[user_id] = asyncio.Lock()
    return user_queue_locks[user_id]


# ─────────────────────────────────────────────
#  UTILIDADES DE TEXTO
# ─────────────────────────────────────────────

def _esc(text: str) -> str:
    """Escapa caracteres especiales de Markdown v1."""
    for ch in ("_", "*", "`", "["):
        text = text.replace(ch, f"\\{ch}")
    return text


def _link(name: str, url: str) -> str:
    """Enlace Markdown seguro para Telegram."""
    safe = name.replace("]", "\\]")
    return f"[{safe}]({url})"


def _folder_label(folder: str) -> str:
    return "Descargas" if folder == "downloads" else "Empaquetados"


def _folder_icon(folder: str) -> str:
    return "📥" if folder == "downloads" else "📦"


# ─────────────────────────────────────────────
#  TECLADOS INLINE
# ─────────────────────────────────────────────

def kb_main() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📥 Descargas", callback_data="cd:downloads"),
            InlineKeyboardButton("📦 Empaquetados", callback_data="cd:packed"),
        ],
        [
            InlineKeyboardButton("📋 Ver archivos", callback_data="list:1"),
            InlineKeyboardButton("📊 Estado", callback_data="status"),
        ],
        [InlineKeyboardButton("❓ Ayuda", callback_data="help")],
    ])


def kb_folder(folder: str) -> InlineKeyboardMarkup:
    other = "packed" if folder == "downloads" else "downloads"
    other_lbl = "📦 Empaquetados" if folder == "downloads" else "📥 Descargas"
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Ver archivos", callback_data="list:1"),
            InlineKeyboardButton(other_lbl, callback_data=f"cd:{other}"),
        ],
        [
            InlineKeyboardButton("🗑 Vaciar", callback_data=f"clear_confirm:{folder}"),
            InlineKeyboardButton("📦 Empaquetar", callback_data="pack"),
        ],
        [InlineKeyboardButton("🏠 Menu", callback_data="main_menu")],
    ])


def kb_nav(page: int, total: int) -> InlineKeyboardMarkup:
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("« Anterior", callback_data=f"list:{page - 1}"))
    nav.append(InlineKeyboardButton(f"{page}/{total}", callback_data="noop"))
    if page < total:
        nav.append(InlineKeyboardButton("Siguiente »", callback_data=f"list:{page + 1}"))
    return InlineKeyboardMarkup([
        nav,
        [
            InlineKeyboardButton("🔄 Actualizar", callback_data=f"list:{page}"),
            InlineKeyboardButton("🏠 Menu", callback_data="main_menu"),
        ],
    ])


def kb_confirm_clear(folder: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Si, vaciar", callback_data=f"clear_do:{folder}"),
        InlineKeyboardButton("❌ Cancelar", callback_data=f"cd:{folder}"),
    ]])


def kb_confirm_delete(num: int, folder: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Si, eliminar", callback_data=f"delete_do:{num}:{folder}"),
        InlineKeyboardButton("❌ Cancelar", callback_data="list:1"),
    ]])


def kb_after_upload() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📋 Ver archivos", callback_data="list:1"),
            InlineKeyboardButton("📦 Empaquetar", callback_data="pack"),
        ],
        [InlineKeyboardButton("🏠 Menu", callback_data="main_menu")],
    ])


def kb_after_pack() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📦 Empaquetados", callback_data="cd:packed"),
            InlineKeyboardButton("📥 Descargas", callback_data="cd:downloads"),
        ],
        [InlineKeyboardButton("🏠 Menu", callback_data="main_menu")],
    ])


def kb_back() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("📋 Ver archivos", callback_data="list:1"),
        InlineKeyboardButton("🏠 Menu", callback_data="main_menu"),
    ]])


# ─────────────────────────────────────────────
#  TEXTOS DE MENSAJES
# ─────────────────────────────────────────────

ITEMS_PER_PAGE = 10

WELCOME = (
    "👋 **Hola, {name}!** Bienvenido a **File2Link**.\n\n"
    "Guardo tus archivos y genero enlaces de descarga directa.\n\n"
    "**Carpetas:**\n"
    "  📥 downloads — archivos recibidos\n"
    "  📦 packed — archivos comprimidos (ZIP)\n\n"
    "**Limite por archivo:** {limit} MB\n\n"
    "Elige una opcion:"
)

HELP = (
    "📚 **File2Link — Guia de uso**\n\n"
    "**NAVEGACION:**\n"
    "/start — Menu principal\n"
    "/cd downloads | /cd packed — Cambiar carpeta\n"
    "/list [pagina] — Ver archivos\n\n"
    "**GESTION DE ARCHIVOS:**\n"
    "/delete N — Eliminar archivo #N\n"
    "/rename N nombre — Renombrar archivo #N\n"
    "/clear — Vaciar carpeta actual\n\n"
    "**EMPAQUETADO:**\n"
    "/pack — Comprimir en ZIP\n"
    "/pack MB — ZIP dividido en partes de N MB\n\n"
    "**COLA:**\n"
    "/queue — Ver archivos en cola\n"
    "/clearqueue — Cancelar cola\n\n"
    "**INFO:**\n"
    "/status — Estado del sistema\n"
    "/cleanup — Analizar almacenamiento\n\n"
    f"**Limite por archivo:** {MAX_FILE_SIZE_MB} MB"
)


def _build_status(user_id: int, session: dict) -> str:
    dl = len(file_service.list_user_files(user_id, "downloads"))
    pk = len(file_service.list_user_files(user_id, "packed"))
    mb = file_service.get_user_storage_usage(user_id) / (1024 * 1024)
    s = load_manager.get_status()
    icon = "🟢" if s["can_accept_work"] else "🔴"
    status = "Operativo" if s["can_accept_work"] else "Sobrecargado"
    queue_len = len(user_queues.get(user_id, []))
    return (
        f"📊 **Estado del sistema**\n\n"
        f"**Tu cuenta:**\n"
        f"  ID: `{user_id}`\n"
        f"  Carpeta: {_folder_icon(session['current_folder'])} {session['current_folder']}\n"
        f"  Archivos en downloads: {dl}\n"
        f"  Archivos en packed: {pk}\n"
        f"  Espacio usado: {mb:.2f} MB\n"
        f"  En cola: {queue_len}\n\n"
        f"**Servidor:**\n"
        f"  CPU: {s['cpu_percent']:.1f}%\n"
        f"  Memoria: {s['memory_percent']:.1f}%\n"
        f"  Procesos: {s['active_processes']}/{s['max_processes']}\n"
        f"  Estado: {icon} {status}"
    )


def _build_list(files: list, folder: str, page: int, total_pages: int) -> str:
    label = _folder_label(folder)
    lines = [
        f"{_folder_icon(folder)} **{label}** — pagina {page}/{total_pages}",
        f"Total: {len(files)} archivo(s)\n",
    ]
    start = (page - 1) * ITEMS_PER_PAGE
    for f in files[start : start + ITEMS_PER_PAGE]:
        lines.append(f"**#{f['number']}** {_link(f['name'], f['url'])}")
        lines.append(f"   {f['size_mb']:.1f} MB")
        lines.append("")

    lines.append("Comandos: /delete N  |  /rename N nombre")
    return "\n".join(lines)


def _split_text(text: str, limit: int = 4000) -> list:
    chunks, current = [], ""
    for line in text.splitlines(keepends=True):
        if len(current) + len(line) > limit:
            chunks.append(current)
            current = line
        else:
            current += line
    if current:
        chunks.append(current)
    return chunks or [text]


# ─────────────────────────────────────────────
#  COMANDOS
# ─────────────────────────────────────────────

async def cmd_start(client: Client, message: Message):
    user = message.from_user
    await message.reply_text(
        WELCOME.format(name=user.first_name, limit=MAX_FILE_SIZE_MB),
        reply_markup=kb_main(),
    )
    logger.info(f"/start — {user.id}")


async def cmd_help(client: Client, message: Message):
    await message.reply_text(HELP, reply_markup=kb_back())


async def cmd_cd(client: Client, message: Message):
    user_id = message.from_user.id
    session = get_session(user_id)
    args = message.text.split()

    if len(args) == 1:
        folder = session["current_folder"]
        count = len(file_service.list_user_files(user_id, folder))
        await message.reply_text(
            f"{_folder_icon(folder)} **{_folder_label(folder)}**\n"
            f"Tienes **{count}** archivo(s).",
            reply_markup=kb_folder(folder),
        )
        return

    folder = args[1].lower()
    if folder not in ("downloads", "packed"):
        await message.reply_text(
            "❌ **Carpeta invalida.**\n\n"
            "Opciones: `downloads` | `packed`\n"
            "Ejemplo: `/cd downloads`",
            reply_markup=kb_main(),
        )
        return

    session["current_folder"] = folder
    count = len(file_service.list_user_files(user_id, folder))
    await message.reply_text(
        f"{_folder_icon(folder)} **{_folder_label(folder)}**\n"
        f"Tienes **{count}** archivo(s).",
        reply_markup=kb_folder(folder),
    )


async def cmd_list(client: Client, message: Message):
    user_id = message.from_user.id
    folder = get_session(user_id)["current_folder"]
    args = message.text.split()
    try:
        page = max(1, int(args[1])) if len(args) > 1 else 1
    except ValueError:
        page = 1

    files = file_service.list_user_files(user_id, folder)
    if not files:
        await message.reply_text(
            f"📭 **{_folder_label(folder)}** esta vacia.\n\n"
            "Envia archivos al bot para guardarlos.",
            reply_markup=kb_main(),
        )
        return

    total_pages = max(1, (len(files) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
    page = min(page, total_pages)
    text = _build_list(files, folder, page, total_pages)

    for i, chunk in enumerate(_split_text(text)):
        kb = kb_nav(page, total_pages) if i == len(_split_text(text)) - 1 else None
        await message.reply_text(chunk, reply_markup=kb, disable_web_page_preview=True)


async def cmd_delete(client: Client, message: Message):
    user_id = message.from_user.id
    folder = get_session(user_id)["current_folder"]
    args = message.text.split()

    if len(args) < 2:
        await message.reply_text(
            "❌ **Uso:** `/delete N`\n"
            "**Ejemplo:** `/delete 5`\n\n"
            "Usa /list para ver los numeros.",
            reply_markup=kb_back(),
        )
        return

    try:
        num = int(args[1])
    except ValueError:
        await message.reply_text("❌ El numero debe ser un entero valido.")
        return

    target = next(
        (f for f in file_service.list_user_files(user_id, folder) if f["number"] == num),
        None,
    )
    if not target:
        await message.reply_text(
            f"❌ No existe el archivo **#{num}** en {folder}.",
            reply_markup=kb_back(),
        )
        return

    safe = target["name"].replace("*", "").replace("_", " ")
    await message.reply_text(
        f"⚠️ **Eliminar este archivo?**\n\n"
        f"**#{target['number']}** — {safe}\n"
        f"Tamaño: {target['size_mb']:.1f} MB\n\n"
        "Esta accion no se puede deshacer.",
        reply_markup=kb_confirm_delete(num, folder),
    )


async def cmd_clear(client: Client, message: Message):
    user_id = message.from_user.id
    folder = get_session(user_id)["current_folder"]
    count = len(file_service.list_user_files(user_id, folder))

    if count == 0:
        await message.reply_text(
            f"📭 **{_folder_label(folder)}** ya esta vacia.",
            reply_markup=kb_main(),
        )
        return

    await message.reply_text(
        f"⚠️ **Vaciar {_folder_label(folder)}?**\n\n"
        f"Se eliminaran **{count}** archivo(s) de forma permanente.\n"
        "Esta accion no se puede deshacer.",
        reply_markup=kb_confirm_clear(folder),
    )


async def cmd_rename(client: Client, message: Message):
    user_id = message.from_user.id
    folder = get_session(user_id)["current_folder"]
    args = message.text.split(maxsplit=2)

    if len(args) < 3:
        await message.reply_text(
            "❌ **Uso:** `/rename N nuevo_nombre`\n"
            "**Ejemplo:** `/rename 3 informe_final`",
            reply_markup=kb_back(),
        )
        return

    try:
        num = int(args[1])
    except ValueError:
        await message.reply_text("❌ El numero debe ser un entero valido.")
        return

    new_name = args[2].strip()
    if not new_name:
        await message.reply_text("❌ El nuevo nombre no puede estar vacio.")
        return

    success, msg, new_url = file_service.rename_file(user_id, num, new_name, folder)
    if success:
        await message.reply_text(
            f"✅ **Archivo renombrado.**\n\n{_link(new_name, new_url)}",
            reply_markup=kb_back(),
            disable_web_page_preview=False,
        )
    else:
        await message.reply_text(f"❌ {msg}", reply_markup=kb_back())


async def cmd_status(client: Client, message: Message):
    user_id = message.from_user.id
    await message.reply_text(
        _build_status(user_id, get_session(user_id)),
        reply_markup=kb_main(),
    )


async def cmd_pack(client: Client, message: Message):
    user_id = message.from_user.id
    parts = message.text.split()

    st = load_manager.get_status()
    if not st["can_accept_work"]:
        await message.reply_text(
            "⚠️ **Servidor sobrecargado.**\n\n"
            f"CPU: {st['cpu_percent']:.1f}%  |  Procesos: {st['active_processes']}\n\n"
            "Intenta de nuevo en unos minutos.",
            reply_markup=kb_main(),
        )
        return

    split_size = None
    if len(parts) > 1:
        try:
            split_size = int(parts[1])
            if not 1 <= split_size <= 500:
                await message.reply_text(
                    "❌ El tamaño de parte debe estar entre 1 y 500 MB.\n"
                    "Ejemplo: `/pack 100`"
                )
                return
        except ValueError:
            await message.reply_text("❌ Valor invalido.\nUso: `/pack`  o  `/pack MB`")
            return

    detail = f"Dividiendo en partes de {split_size} MB..." if split_size else "Creando archivo ZIP..."
    status_msg = await message.reply_text(f"⏳ **Empaquetando...**\n{detail}")

    result_text, result_kb = await _run_pack(user_id, split_size)
    await status_msg.edit_text(result_text, reply_markup=result_kb, disable_web_page_preview=True)


async def cmd_queue(client: Client, message: Message):
    user_id = message.from_user.id
    queue = user_queues.get(user_id, [])

    if not queue:
        await message.reply_text(
            "📭 **Cola vacia.** No hay archivos pendientes.",
            reply_markup=kb_main(),
        )
        return

    lines = [f"📋 **Cola — {len(queue)} archivo(s)**\n"]
    for i, msg in enumerate(queue, 1):
        if msg.document:
            lbl = f"📄 {msg.document.file_name or 'sin nombre'}"
        elif msg.video:
            lbl = f"🎬 {msg.video.file_name or 'sin nombre'}"
        elif msg.audio:
            lbl = f"🎵 {msg.audio.file_name or 'sin nombre'}"
        elif msg.photo:
            lbl = "🖼 Foto"
        else:
            lbl = "📎 Archivo"
        lines.append(f"#{i} — {lbl}")

    if user_id in user_processing:
        lines.append("\n⏳ Procesando el primero ahora...")
    else:
        lines.append("\n⏸ En espera.")

    await message.reply_text("\n".join(lines), reply_markup=kb_main())


async def cmd_clearqueue(client: Client, message: Message):
    user_id = message.from_user.id
    lock = get_queue_lock(user_id)

    async with lock:
        queue = user_queues.get(user_id, [])
        if not queue:
            await message.reply_text(
                "📭 La cola ya esta vacia.",
                reply_markup=kb_main(),
            )
            return

        count = len(queue)
        user_queues[user_id] = []
        user_processing.pop(user_id, None)

    await message.reply_text(
        f"🗑 **Cola limpiada.** Se cancelaron **{count}** archivo(s).",
        reply_markup=kb_main(),
    )


async def cmd_cleanup(client: Client, message: Message):
    status_msg = await message.reply_text("🧹 Analizando almacenamiento...")
    try:
        mb = file_service.get_user_storage_usage(message.from_user.id) / (1024 * 1024)
        await status_msg.edit_text(
            f"✅ **Analisis completado.**\n\n"
            f"Espacio ocupado: **{mb:.2f} MB**\n"
            f"Sistema: operativo"
        )
    except Exception as e:
        logger.error(f"Error en /cleanup: {e}")
        await status_msg.edit_text("❌ Error durante el analisis.")


# ─────────────────────────────────────────────
#  LOGICA DE EMPAQUETADO
# ─────────────────────────────────────────────

async def _run_pack(user_id: int, split_size) -> tuple:
    def _do():
        try:
            return packing_service.pack_folder(user_id, split_size)
        except Exception as e:
            return None, str(e)

    try:
        with concurrent.futures.ThreadPoolExecutor() as ex:
            files, err_msg = ex.submit(_do).result(timeout=300)
    except concurrent.futures.TimeoutError:
        return (
            "❌ **Tiempo agotado.**\n\n"
            "El empaquetado tardó demasiado. Intenta con menos archivos.",
            kb_main(),
        )

    if not files:
        return f"❌ {err_msg}", kb_main()

    total_mb = sum(f["size_mb"] for f in files)
    orig = f" ({files[0]['total_files']} archivos)" if files[0].get("total_files") else ""

    if len(files) == 1:
        f = files[0]
        text = (
            f"✅ **Empaquetado completado{orig}**\n\n"
            f"{_link(f['filename'], f['url'])}\n"
            f"{f['size_mb']:.1f} MB"
        )
        return text, kb_after_pack()

    # Buscar .txt de lista de partes
    user_dir = file_service.get_user_directory(user_id, "packed")
    base = next(
        (f["filename"].rsplit(".", 2)[0] for f in files if ".001" in f["filename"]),
        None,
    )
    list_url = None
    if base:
        txt_path = os.path.join(user_dir, f"{base}.txt")
        if os.path.exists(txt_path):
            list_url = file_service.create_packed_url(user_id, f"{base}.txt")

    lines = [
        f"✅ **Empaquetado completado{orig}**\n",
        f"Partes: {len(files)}  |  Total: {total_mb:.1f} MB\n",
    ]
    if list_url:
        lines.append(f"\n{_link('Lista de partes (.txt)', list_url)}")
    lines.append("\n**Enlaces de descarga:**")
    for f in files:
        lines.append(f"\n{_link(f['filename'], f['url'])} — {f['size_mb']:.1f} MB")

    text = "\n".join(lines)

    if len(text) > 4000:
        short = (
            f"✅ **{len(files)} partes generadas{orig}**\n"
            f"Total: {total_mb:.1f} MB\n\n"
            "Usa el boton para ver los enlaces en tu carpeta packed."
            + (f"\n\n{_link('Lista de partes (.txt)', list_url)}" if list_url else "")
        )
        return short, kb_after_pack()

    return text, kb_after_pack()


# ─────────────────────────────────────────────
#  CALLBACKS
# ─────────────────────────────────────────────

async def callback_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    session = get_session(user_id)

    try:
        if data == "noop":
            await query.answer()
            return

        if data == "main_menu":
            await query.message.edit_text(
                WELCOME.format(name=query.from_user.first_name, limit=MAX_FILE_SIZE_MB),
                reply_markup=kb_main(),
            )

        elif data == "help":
            await query.message.edit_text(HELP, reply_markup=kb_back())

        elif data.startswith("cd:"):
            folder = data[3:]
            session["current_folder"] = folder
            count = len(file_service.list_user_files(user_id, folder))
            await query.message.edit_text(
                f"{_folder_icon(folder)} **{_folder_label(folder)}**\n"
                f"Tienes {count} archivo(s).",
                reply_markup=kb_folder(folder),
            )

        elif data.startswith("list:"):
            page = int(data[5:])
            folder = session["current_folder"]
            files = file_service.list_user_files(user_id, folder)

            if not files:
                await query.message.edit_text(
                    f"📭 **{_folder_label(folder)}** esta vacia.",
                    reply_markup=kb_main(),
                )
                await query.answer()
                return

            total_pages = max(1, (len(files) + ITEMS_PER_PAGE - 1) // ITEMS_PER_PAGE)
            page = max(1, min(page, total_pages))
            text = _build_list(files, folder, page, total_pages)
            await query.message.edit_text(
                text,
                reply_markup=kb_nav(page, total_pages),
                disable_web_page_preview=True,
            )

        elif data == "status":
            await query.message.edit_text(
                _build_status(user_id, session),
                reply_markup=kb_main(),
            )

        elif data.startswith("clear_confirm:"):
            folder = data[14:]
            count = len(file_service.list_user_files(user_id, folder))
            if count == 0:
                await query.message.edit_text(
                    f"📭 **{_folder_label(folder)}** ya esta vacia.",
                    reply_markup=kb_main(),
                )
            else:
                await query.message.edit_text(
                    f"⚠️ **Vaciar {_folder_label(folder)}?**\n\n"
                    f"Se eliminaran {count} archivo(s) de forma permanente.\n"
                    "Esta accion no se puede deshacer.",
                    reply_markup=kb_confirm_clear(folder),
                )

        elif data.startswith("clear_do:"):
            folder = data[9:]
            success, msg = file_service.delete_all_files(user_id, folder)
            icon = "✅" if success else "❌"
            await query.message.edit_text(f"{icon} {msg}", reply_markup=kb_folder(folder))

        elif data.startswith("delete_do:"):
            _, num_str, folder = data.split(":", 2)
            success, msg = file_service.delete_file_by_number(user_id, int(num_str), folder)
            icon = "✅" if success else "❌"
            await query.message.edit_text(f"{icon} {msg}", reply_markup=kb_back())

        elif data == "pack":
            st = load_manager.get_status()
            if not st["can_accept_work"]:
                await query.answer("Servidor sobrecargado. Intenta mas tarde.", show_alert=True)
                return
            await query.answer("Iniciando empaquetado...")
            wait_msg = await query.message.reply_text("⏳ **Empaquetando...** Creando ZIP...")
            result_text, result_kb = await _run_pack(user_id, None)
            await wait_msg.edit_text(result_text, reply_markup=result_kb, disable_web_page_preview=True)
            await query.answer()
            return

        else:
            await query.answer("Accion no reconocida.", show_alert=True)
            return

        await query.answer()

    except Exception as e:
        logger.error(f"Callback error '{data}': {e}", exc_info=True)
        try:
            await query.answer("Ocurrio un error. Intenta de nuevo.", show_alert=True)
        except Exception:
            pass


# ─────────────────────────────────────────────
#  RECEPCION Y COLA DE ARCHIVOS
# ─────────────────────────────────────────────

def _get_file_info(message: Message):
    """Extrae tipo, nombre y tamaño del archivo del mensaje."""
    if message.document:
        return "Documento", message.document.file_name or "archivo", message.document.file_size or 0
    if message.video:
        return "Video", message.video.file_name or "video.mp4", message.video.file_size or 0
    if message.audio:
        return "Audio", message.audio.file_name or "audio.mp3", message.audio.file_size or 0
    if message.photo:
        return "Foto", f"foto_{message.id}.jpg", message.photo[-1].file_size or 0
    return None, None, 0


async def handle_file(client: Client, message: Message):
    """Recibe un archivo y lo encola para procesamiento."""
    user_id = message.from_user.id

    file_type, orig_name, file_size = _get_file_info(message)
    if not file_type:
        return

    # Validar tamaño
    if file_size > MAX_FILE_SIZE:
        await message.reply_text(
            f"❌ **Archivo demasiado grande.**\n\n"
            f"Tu archivo: {file_service.format_bytes(file_size)}\n"
            f"Limite: {MAX_FILE_SIZE_MB} MB\n\n"
            "Dividelo en partes mas pequenas."
        )
        return

    lock = get_queue_lock(user_id)

    async with lock:
        if user_id not in user_queues:
            user_queues[user_id] = []

        current_len = len(user_queues[user_id])

        # Limitar cola por usuario
        if current_len >= MAX_QUEUE_PER_USER:
            await message.reply_text(
                f"❌ **Cola llena.**\n\n"
                f"Maximo {MAX_QUEUE_PER_USER} archivos en cola.\n"
                "Usa /clearqueue para limpiar o espera."
            )
            return

        user_queues[user_id].append(message)
        pos = current_len + 1

    if pos == 1:
        asyncio.create_task(_process_queue(client, user_id))
    else:
        await message.reply_text(
            f"📬 **Archivo encolado.**\n"
            f"Posicion: #{pos} — espera tu turno."
        )


async def _process_queue(client: Client, user_id: int):
    """Procesa la cola de archivos de un usuario de forma secuencial."""
    lock = get_queue_lock(user_id)

    while True:
        async with lock:
            if not user_queues.get(user_id):
                user_processing.pop(user_id, None)
                return
            msg = user_queues[user_id][0]

        total_in_queue = len(user_queues[user_id])
        user_processing[user_id] = True

        await _process_single_file(client, msg, user_id, total_in_queue)

        async with lock:
            if user_queues.get(user_id):
                user_queues[user_id].pop(0)

        await asyncio.sleep(QUEUE_PROCESSING_DELAY)


async def _process_single_file(client, message, user_id, total):
    """Descarga y registra un unico archivo."""
    start = time.time()

    file_type, orig_name, file_size = _get_file_info(message)
    if not file_type:
        return

    # Preparar ruta de almacenamiento
    user_dir = file_service.get_user_directory(user_id, "downloads")
    sanitized = file_service.sanitize_filename(orig_name)
    stored = sanitized
    path = os.path.join(user_dir, stored)
    base, ext = os.path.splitext(sanitized)
    c = 1
    while os.path.exists(path):
        stored = f"{base}_{c}{ext}"
        path = os.path.join(user_dir, stored)
        c += 1

    # Registrar antes de descargar
    file_number = file_service.register_file(user_id, orig_name, stored, "downloads")

    # Mensaje de progreso
    position = 1  # Siempre es el primero de la cola actual
    prog_msg = await message.reply_text(
        progress_service.create_progress_message(
            filename=orig_name, current=0, total=file_size, speed=0,
            user_first_name=message.from_user.first_name,
            process_type="Descargando", current_file=position, total_files=total,
        )
    )

    pdata = {"last_update": 0.0, "last_speed": 0.0}

    async def on_progress(current, total_bytes):
        try:
            elapsed = time.time() - start
            speed = current / elapsed if elapsed > 0 else 0
            pdata["last_speed"] = 0.7 * pdata["last_speed"] + 0.3 * speed
            now = time.time()
            if now - pdata["last_update"] >= 0.6 or current == total_bytes:
                txt = progress_service.create_progress_message(
                    filename=orig_name, current=current, total=total_bytes,
                    speed=pdata["last_speed"],
                    user_first_name=message.from_user.first_name,
                    process_type="Descargando",
                    current_file=position, total_files=total,
                )
                try:
                    await prog_msg.edit_text(txt)
                    pdata["last_update"] = now
                except Exception:
                    pass
        except Exception:
            pass

    success, _ = await download_service.download_with_retry(
        client=client, message=message, file_path=path, progress_callback=on_progress,
    )

    if not success or not os.path.exists(path):
        await prog_msg.edit_text(
            "❌ **Error al descargar el archivo.**\n\n"
            "Intentalo de nuevo.",
            reply_markup=kb_main(),
        )
        return

    # Verificar integridad
    final_size = os.path.getsize(path)
    if file_size > 0 and final_size < file_size * 0.95:
        logger.warning(f"Descarga posiblemente incompleta: {file_size}B -> {final_size}B")

    size_mb = final_size / (1024 * 1024)
    url = file_service.create_download_url(user_id, stored)

    # Obtener numero final correcto
    files_list = file_service.list_user_files(user_id, "downloads")
    final_num = next(
        (f["number"] for f in files_list if f["stored_name"] == stored),
        file_number,
    )

    lock = get_queue_lock(user_id)
    async with lock:
        remaining = len(user_queues.get(user_id, [])) - 1

    queue_note = f"\n\n⏳ Proximo en cola: {remaining} restante(s)..." if remaining > 0 else ""

    await prog_msg.edit_text(
        f"✅ **Archivo guardado — #{final_num}**\n\n"
        f"{_link(orig_name, url)}\n"
        f"{file_type}  ·  {size_mb:.2f} MB  ·  downloads"
        f"{queue_note}",
        reply_markup=kb_after_upload(),
        disable_web_page_preview=False,
    )


# ─────────────────────────────────────────────
#  REGISTRO DE HANDLERS
# ─────────────────────────────────────────────

def setup_handlers(client: Client):
    client.on_message(filters.command("start") & filters.private)(cmd_start)
    client.on_message(filters.command("help") & filters.private)(cmd_help)
    client.on_message(filters.command("status") & filters.private)(cmd_status)
    client.on_message(filters.command("cd") & filters.private)(cmd_cd)
    client.on_message(filters.command("list") & filters.private)(cmd_list)
    client.on_message(filters.command("delete") & filters.private)(cmd_delete)
    client.on_message(filters.command("clear") & filters.private)(cmd_clear)
    client.on_message(filters.command("rename") & filters.private)(cmd_rename)
    client.on_message(filters.command("pack") & filters.private)(cmd_pack)
    client.on_message(filters.command("queue") & filters.private)(cmd_queue)
    client.on_message(filters.command("clearqueue") & filters.private)(cmd_clearqueue)
    client.on_message(filters.command("cleanup") & filters.private)(cmd_cleanup)

    client.on_callback_query()(callback_handler)

    client.on_message(
        (filters.document | filters.video | filters.audio | filters.photo) & filters.private
    )(handle_file)
