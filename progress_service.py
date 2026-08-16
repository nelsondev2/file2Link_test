import logging
from file_service import file_service

logger = logging.getLogger(__name__)


class ProgressService:
    def create_progress_bar(self, current, total, bar_length=15):
        if total == 0:
            return "[            ] 0.0%"
        percent = min(100.0, float(current) * 100 / float(total))
        filled = int(round(bar_length * current / float(total)))
        bar = "|" * filled + "." * (bar_length - filled)
        return f"[{bar}] {percent:.1f}%"

    def calculate_eta(self, current, total, speed):
        if speed <= 0 or current <= 0:
            return "calculando..."
        remaining = total - current
        eta = remaining / speed
        if eta < 60:
            return f"{int(eta)}s"
        if eta < 3600:
            return f"{int(eta // 60)}m {int(eta % 60)}s"
        return f"{int(eta // 3600)}h {int((eta % 3600) // 60)}m"

    def format_speed(self, speed_bytes):
        if speed_bytes <= 0:
            return "0.0 B/s"
        kb = speed_bytes / 1024
        if kb < 1024:
            return f"{kb:.1f} KB/s"
        mb = kb / 1024
        if mb < 1024:
            return f"{mb:.1f} MB/s"
        return f"{mb / 1024:.2f} GB/s"

    def create_progress_message(
        self, filename, current, total, speed=0,
        user_first_name=None, process_type="Descargando",
        current_file=1, total_files=1
    ):
        display = filename[:22] + "..." if len(filename) > 25 else filename
        bar = self.create_progress_bar(current, total)
        processed = file_service.format_bytes(current)
        total_str = file_service.format_bytes(total)
        speed_str = self.format_speed(speed)
        eta = self.calculate_eta(current, total, speed)

        msg = (
            f"**{process_type}:** `{display}`\n"
            f"`{bar}`\n"
            f"**Progreso:** {processed} / {total_str}\n"
            f"**Velocidad:** {speed_str}\n"
            f"**ETA:** {eta}\n"
            f"**En cola:** {current_file}/{total_files}"
        )
        if user_first_name:
            msg += f"\n**Usuario:** {user_first_name}"
        return msg


progress_service = ProgressService()
