"""
Generador de mensajes de progreso para el bot.

Produce mensajes visualmente claros y amigables que el usuario
pueda entender sin conocimientos técnicos.
"""


def _progress_bar(current: int, total: int, length: int = 16) -> str:
    if total <= 0:
        return "░" * length + " 0%"
    pct = min(1.0, current / total)
    filled = round(pct * length)
    bar = "█" * filled + "░" * (length - filled)
    return f"{bar} {pct * 100:.0f}%"


def _format_size(size: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def _format_speed(bps: float) -> str:
    if bps <= 0:
        return "—"
    return _format_size(int(bps)) + "/s"


def _format_eta(current: int, total: int, speed: float) -> str:
    if speed <= 0 or current <= 0 or current >= total:
        return "calculando…"
    secs = (total - current) / speed
    if secs < 60:
        return f"{int(secs)}s"
    if secs < 3600:
        return f"{int(secs // 60)}m {int(secs % 60)}s"
    return f"{int(secs // 3600)}h {int((secs % 3600) // 60)}m"


def build_progress_message(
    *,
    filename: str,
    current: int,
    total: int,
    speed: float = 0,
    position: int = 1,
    total_files: int = 1,
) -> str:
    """
    Construye el mensaje de progreso mostrado al usuario durante la subida.

    Parámetros
    ----------
    filename    : nombre del archivo
    current     : bytes procesados
    total       : bytes totales
    speed       : velocidad en bytes/s
    position    : posición en la cola (1-based)
    total_files : total de archivos en la cola
    """
    short = filename if len(filename) <= 28 else filename[:25] + "…"
    bar = _progress_bar(current, total)
    done = _format_size(current)
    full = _format_size(total)
    spd = _format_speed(speed)
    eta = _format_eta(current, total, speed)

    queue_line = (
        f"📋 Archivo {position} de {total_files}\n" if total_files > 1 else ""
    )

    return (
        f"📥 **Guardando** `{short}`\n"
        f"`{bar}`\n"
        f"**Progreso:** {done} / {full}\n"
        f"**Velocidad:** {spd}   •   **Tiempo restante:** {eta}\n"
        f"{queue_line}"
    )
