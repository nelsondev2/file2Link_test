import logging
import sys
import time
from file_service import file_service

logger = logging.getLogger(__name__)

class ProgressService:
    def create_progress_bar(self, current, total, bar_length=15):
        """Crea una barra de progreso visual en una sola línea"""
        if total == 0:
            return "[░░░░░░░░░░░░░░░] 0.0%"
        
        percent = min(100.0, float(current) * 100 / float(total))
        filled_length = int(round(bar_length * current / float(total)))
        
        bar = '█' * filled_length + '░' * (bar_length - filled_length)
        return f"[{bar}] {percent:.1f}%"

    def calculate_eta(self, current, total, speed):
        """Calcula el tiempo estimado de finalización"""
        if speed <= 0 or current <= 0:
            return "Calculando..."
        
        remaining_bytes = total - current
        eta_seconds = remaining_bytes / speed
        
        if eta_seconds < 60:
            return f"{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            return f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
        else:
            hours = int(eta_seconds // 3600)
            minutes = int((eta_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def format_speed(self, speed_bytes):
        """Formatea la velocidad de descarga de forma legible"""
        if speed_bytes <= 0:
            return "0.0 B/s"
        
        speed_kb = speed_bytes / 1024
        if speed_kb < 1024:
            return f"{speed_kb:.1f} KB/s"
        
        speed_mb = speed_kb / 1024
        if speed_mb < 1024:
            return f"{speed_mb:.1f} MB/s"
        
        speed_gb = speed_mb / 1024
        return f"{speed_gb:.2f} GB/s"

    def create_progress_message(self, filename, current, total, speed=0, user_first_name=None, process_type="Subiendo", current_file=1, total_files=1):
        """Crea el mensaje de progreso con ETA, nombre y posición en cola CORREGIDO"""
        if len(filename) > 25:
            display_name = filename[:22] + "..."
        else:
            display_name = filename
        
        progress_bar = self.create_progress_bar(current, total)
        processed = file_service.format_bytes(current)
        total_size = file_service.format_bytes(total)
        speed_str = self.format_speed(speed)
        
        # Calcular ETA
        eta = self.calculate_eta(current, total, speed)

        message = f"**📁 {process_type}:** `{display_name}`\n"
        message += f"`{progress_bar}`\n"
        message += f"**📊 Progreso:** {processed} / {total_size}\n"
        message += f"**⚡ Velocidad:** {speed_str}\n"
        message += f"**🕐 ETA:** {eta}\n"
        message += f"**📋 En cola:** {current_file}/{total_files}\n"
        if user_first_name:
            message += f"**👤 Usuario:** {user_first_name}"

        return message

progress_service = ProgressService()
