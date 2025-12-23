import logging
import os
import time
from file_service import file_service

logger = logging.getLogger(__name__)

class ProgressService:
    def __init__(self):
        self.speed_history = {}
        self.last_update_times = {}
    
    def create_progress_bar(self, current, total, bar_length=15):
        """Crea una barra de progreso visual con caracteres Unicode"""
        if total == 0:
            return "▱" * bar_length + " 0.0%"
        
        percent = min(100.0, float(current) * 100 / float(total))
        filled_length = int(round(bar_length * current / float(total)))
        
        # Usar diferentes caracteres según el progreso
        if percent < 30:
            filled_char = '▱'
        elif percent < 70:
            filled_char = '▰'
        else:
            filled_char = '█'
        
        bar = filled_char * filled_length + '▱' * (bar_length - filled_length)
        return f"{bar} {percent:.1f}%"
    
    def calculate_eta(self, current, total, speed, user_id=None):
        """Calcula ETA con suavizado y persistencia por usuario"""
        if speed <= 0 or current <= 0:
            return "Calculando..."
        
        # Suavizar velocidad usando historial del usuario
        if user_id:
            if user_id not in self.speed_history:
                self.speed_history[user_id] = []
            
            self.speed_history[user_id].append(speed)
            if len(self.speed_history[user_id]) > 5:
                self.speed_history[user_id].pop(0)
            
            # Usar velocidad promedio
            smoothed_speed = sum(self.speed_history[user_id]) / len(self.speed_history[user_id])
        else:
            smoothed_speed = speed
        
        remaining_bytes = total - current
        if remaining_bytes <= 0:
            return "Completado"
        
        eta_seconds = remaining_bytes / smoothed_speed
        
        # Formatear ETA de manera más amigable
        if eta_seconds < 10:
            return f"{eta_seconds:.1f}s"
        elif eta_seconds < 60:
            return f"{int(eta_seconds)}s"
        elif eta_seconds < 3600:
            minutes = int(eta_seconds // 60)
            seconds = int(eta_seconds % 60)
            return f"{minutes}m {seconds}s"
        elif eta_seconds < 86400:
            hours = int(eta_seconds // 3600)
            minutes = int((eta_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(eta_seconds // 86400)
            hours = int((eta_seconds % 86400) // 3600)
            return f"{days}d {hours}h"
    
    def format_speed(self, speed_bytes):
        """Formatea velocidad con colores simbólicos"""
        if speed_bytes <= 0:
            return "0.0 B/s"
        
        speed_kb = speed_bytes / 1024
        if speed_kb < 100:
            # Lento
            symbol = "🐢"
            if speed_kb < 1024:
                return f"{symbol} {speed_kb:.1f} KB/s"
            else:
                speed_mb = speed_kb / 1024
                return f"{symbol} {speed_mb:.1f} MB/s"
        
        elif speed_kb < 1024:
            # Normal
            symbol = "⚡"
            return f"{symbol} {speed_kb:.1f} KB/s"
        
        elif speed_kb < 10240:
            # Rápido
            symbol = "🚀"
            speed_mb = speed_kb / 1024
            return f"{symbol} {speed_mb:.1f} MB/s"
        
        else:
            # Muy rápido
            symbol = "🔥"
            speed_mb = speed_kb / 1024
            return f"{symbol} {speed_mb:.1f} MB/s"
    
    def calculate_per_second(self, current, total, start_time):
        """Calcula bytes por segundo basado en tiempo real"""
        elapsed = time.time() - start_time
        if elapsed > 0:
            return current / elapsed
        return 0
    
    def create_progress_message(self, filename, current, total, speed=0, 
                               user_first_name=None, process_type="Subiendo", 
                               current_file=1, total_files=1, user_id=None, 
                               start_time=None):
        """Crea mensaje de progreso mejorado con más información"""
        
        # Acortar nombre de archivo si es muy largo
        if len(filename) > 30:
            name, ext = os.path.splitext(filename)
            display_name = name[:25] + "..." + ext
        else:
            display_name = filename
        
        # Barra de progreso con colores simbólicos
        progress_bar = self.create_progress_bar(current, total)
        
        # Formatear tamaños
        processed = file_service.format_bytes(current)
        total_size = file_service.format_bytes(total)
        
        # Calcular velocidad real si tenemos tiempo de inicio
        if start_time and current > 0:
            real_speed = self.calculate_per_second(current, total, start_time)
            speed_str = self.format_speed(real_speed)
        else:
            speed_str = self.format_speed(speed)
        
        # Calcular ETA con suavizado
        eta = self.calculate_eta(current, total, speed if start_time is None else real_speed, user_id)
        
        # Porcentaje exacto
        percent = (current / total * 100) if total > 0 else 0
        
        # Construir mensaje
        message = f"**📁 {process_type}:** `{display_name}`\n"
        message += f"`{progress_bar}`\n"
        message += f"**📊 Progreso:** {processed} / {total_size} ({percent:.1f}%)\n"
        message += f"**{speed_str}** | **🕐 {eta}**\n"
        
        # Información de cola (solo si hay múltiples archivos)
        if total_files > 1:
            message += f"**📋 En cola:** {current_file}/{total_files}\n"
            
            # Mostrar progreso de la cola completa
            queue_percent = (current_file - 1) / total_files * 100
            message += f"**📦 Progreso total:** {queue_percent:.1f}%\n"
        
        # Información adicional
        if process_type == "Subiendo" and total > 1048576:  # > 1MB
            remaining_mb = (total - current) / 1048576
            if remaining_mb > 10:
                message += f"**⏳ Restante:** {remaining_mb:.1f} MB\n"
        
        if user_first_name:
            message += f"**👤 {user_first_name}**"
        
        # Emoji según el tipo de proceso
        if process_type == "Subiendo":
            message = "⬆️ " + message
        elif process_type == "Descargando":
            message = "⬇️ " + message
        elif process_type == "Empaquetando":
            message = "📦 " + message
        
        return message
    
    def create_compact_progress(self, filename, current, total, user_id=None):
        """Versión compacta para updates frecuentes (cada 0.3s)"""
        if total == 0:
            return f"`{filename[:20]}...` ▱▱▱▱▱ 0.0%"
        
        percent = (current / total * 100)
        bar_length = 8
        filled = int(bar_length * percent / 100)
        bar = '█' * filled + '░' * (bar_length - filled)
        
        # Velocidad estimada basada en historial
        speed_str = ""
        if user_id and user_id in self.speed_history and len(self.speed_history[user_id]) > 0:
            avg_speed = sum(self.speed_history[user_id][-3:]) / min(3, len(self.speed_history[user_id]))
            if avg_speed > 1024:
                speed_str = f" {avg_speed/1024/1024:.1f}MB/s"
            else:
                speed_str = f" {avg_speed/1024:.0f}KB/s"
        
        return f"`{filename[:15]}...` {bar} {percent:.1f}%{speed_str}"
    
    def create_completion_message(self, filename, total_size, time_taken, user_first_name):
        """Mensaje especial cuando se completa una transferencia"""
        size_mb = total_size / (1024 * 1024)
        
        # Calcular velocidad promedio
        avg_speed_mb = size_mb / time_taken if time_taken > 0 else 0
        
        # Emoji según velocidad
        if avg_speed_mb > 10:
            speed_emoji = "🚀"
        elif avg_speed_mb > 1:
            speed_emoji = "⚡"
        else:
            speed_emoji = "🐢"
        
        message = f"✅ **Transferencia completada!**\n\n"
        message += f"**📄 Archivo:** `{filename}`\n"
        message += f"**📏 Tamaño:** {size_mb:.2f} MB\n"
        message += f"**⏱️ Tiempo:** {time_taken:.1f}s\n"
        message += f"**{speed_emoji} Velocidad:** {avg_speed_mb:.1f} MB/s\n"
        
        if user_first_name:
            message += f"**👤 {user_first_name}**"
        
        return message
    
    def cleanup_user_history(self, user_id):
        """Limpia el historial de un usuario para liberar memoria"""
        if user_id in self.speed_history:
            del self.speed_history[user_id]
        if user_id in self.last_update_times:
            del self.last_update_times[user_id]

progress_service = ProgressService()