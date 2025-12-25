import logging
import time
import math
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AdvancedProgressService:
    """Servicio de progreso avanzado con visualizaciones mejoradas"""
    
    def __init__(self):
        self.unicode_bars = {
            'solid': '█',
            'medium': '▓',
            'light': '▒',
            'very_light': '░',
            'empty': ' '
        }
        
        self.speed_units = ['B/s', 'KB/s', 'MB/s', 'GB/s']
        self.time_units = ['s', 'm', 'h', 'd']
    
    def create_progress_bar(self, current: int, total: int, bar_length: int = 15, 
                           style: str = 'solid') -> str:
        """
        Crea una barra de progreso visual avanzada
        
        Args:
            current: Valor actual
            total: Valor total
            bar_length: Longitud de la barra en caracteres
            style: Estilo de la barra ('solid', 'gradient', 'blocks')
        
        Returns:
            String de la barra de progreso
        """
        if total <= 0:
            return f"[{self.unicode_bars['empty'] * bar_length}] 0.0%"
        
        percent = min(100.0, float(current) * 100 / float(total))
        filled_length = int(round(bar_length * current / float(total)))
        
        if style == 'gradient':
            # Barra con gradiente visual
            bar = ''
            for i in range(bar_length):
                if i < filled_length:
                    if i < filled_length * 0.3:
                        bar += self.unicode_bars['very_light']
                    elif i < filled_length * 0.6:
                        bar += self.unicode_bars['light']
                    elif i < filled_length * 0.9:
                        bar += self.unicode_bars['medium']
                    else:
                        bar += self.unicode_bars['solid']
                else:
                    bar += self.unicode_bars['empty']
        elif style == 'blocks':
            # Barra con bloques completos
            block_chars = '▏▎▍▌▋▊▉█'
            block_size = total / (bar_length * len(block_chars))
            
            bar = ''
            for i in range(bar_length):
                block_start = i * block_size * len(block_chars)
                block_end = (i + 1) * block_size * len(block_chars)
                
                if current >= block_end:
                    bar += block_chars[-1]
                elif current > block_start:
                    block_progress = (current - block_start) / block_size
                    char_index = min(int(block_progress), len(block_chars) - 1)
                    bar += block_chars[char_index]
                else:
                    bar += self.unicode_bars['empty']
        else:
            # Barra sólida simple
            bar = self.unicode_bars['solid'] * filled_length + \
                  self.unicode_bars['empty'] * (bar_length - filled_length)
        
        return f"[{bar}] {percent:.1f}%"
    
    def calculate_eta(self, current: int, total: int, speed: float, 
                     current_time: Optional[float] = None) -> str:
        """
        Calcula el tiempo estimado de finalización con precisión
        
        Args:
            current: Bytes descargados
            total: Bytes totales
            speed: Velocidad en bytes/segundo
            current_time: Timestamp actual (opcional)
        
        Returns:
            String formateado de ETA
        """
        if speed <= 0 or current <= 0 or current >= total:
            return "Calculando..."
        
        remaining_bytes = total - current
        eta_seconds = remaining_bytes / speed
        
        # Suavizar ETA usando promedio móvil
        if not hasattr(self, '_eta_history'):
            self._eta_history = []
        
        self._eta_history.append(eta_seconds)
        if len(self._eta_history) > 10:
            self._eta_history.pop(0)
        
        # Usar promedio de los últimos valores
        smoothed_eta = sum(self._eta_history) / len(self._eta_history)
        
        # Formatear tiempo
        if smoothed_eta < 60:
            return f"{int(smoothed_eta)} segundos"
        elif smoothed_eta < 3600:
            minutes = int(smoothed_eta // 60)
            seconds = int(smoothed_eta % 60)
            return f"{minutes}m {seconds}s"
        elif smoothed_eta < 86400:
            hours = int(smoothed_eta // 3600)
            minutes = int((smoothed_eta % 3600) // 60)
            return f"{hours}h {minutes}m"
        else:
            days = int(smoothed_eta // 86400)
            hours = int((smoothed_eta % 86400) // 3600)
            return f"{days}d {hours}h"
    
    def format_speed(self, speed_bytes: float, precision: int = 1) -> str:
        """
        Formatea la velocidad de forma legible y precisa
        
        Args:
            speed_bytes: Velocidad en bytes/segundo
            precision: Número de decimales
        
        Returns:
            String formateado de velocidad
        """
        if speed_bytes <= 0:
            return "0.0 B/s"
        
        unit_index = 0
        speed = speed_bytes
        
        while speed >= 1024 and unit_index < len(self.speed_units) - 1:
            speed /= 1024.0
            unit_index += 1
        
        # Formato dinámico basado en magnitud
        if unit_index == 0:  # Bytes
            return f"{speed:.0f} {self.speed_units[unit_index]}"
        elif speed < 10:  # Números pequeños
            return f"{speed:.{precision}f} {self.speed_units[unit_index]}"
        elif speed < 100:  # Números medianos
            return f"{speed:.{max(1, precision-1)}f} {self.speed_units[unit_index]}"
        else:  # Números grandes
            return f"{speed:.0f} {self.speed_units[unit_index]}"
    
    def format_file_size(self, size_bytes: int) -> str:
        """Formatea tamaño de archivo de forma legible"""
        if size_bytes < 0:
            return "0 B"
        
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        unit_index = 0
        
        while size_bytes >= 1024 and unit_index < len(units) - 1:
            size_bytes /= 1024.0
            unit_index += 1
        
        if unit_index == 0:
            return f"{size_bytes:.0f} {units[unit_index]}"
        elif size_bytes < 10:
            return f"{size_bytes:.1f} {units[unit_index]}"
        else:
            return f"{size_bytes:.0f} {units[unit_index]}"
    
    def create_progress_message(self, filename: str, current: int, total: int, 
                               speed: float = 0, user_first_name: Optional[str] = None,
                               process_type: str = "Subiendo", current_file: int = 1, 
                               total_files: int = 1, additional_info: Optional[Dict] = None) -> str:
        """
        Crea mensaje de progreso profesional con múltiples opciones
        
        Args:
            filename: Nombre del archivo
            current: Bytes procesados
            total: Bytes totales
            speed: Velocidad en bytes/segundo
            user_first_name: Nombre del usuario
            process_type: Tipo de proceso (Subiendo/Descargando/Procesando)
            current_file: Archivo actual en lote
            total_files: Total de archivos en lote
            additional_info: Información adicional opcional
        
        Returns:
            String del mensaje de progreso
        """
        # Acortar nombre de archivo si es muy largo
        if len(filename) > 30:
            display_name = filename[:27] + "..."
        else:
            display_name = filename
        
        # Crear barra de progreso
        progress_bar = self.create_progress_bar(current, total, style='gradient')
        
        # Formatear valores
        processed_str = self.format_file_size(current)
        total_str = self.format_file_size(total)
        speed_str = self.format_speed(speed)
        
        # Calcular ETA
        eta_str = self.calculate_eta(current, total, speed)
        
        # Calcular porcentaje
        percent = (current / total * 100) if total > 0 else 0
        
        # Construir mensaje
        message = f"**{process_type.upper()}:** `{display_name}`\n"
        message += f"`{progress_bar}`\n"
        message += f"**📊 Progreso:** {processed_str} / {total_str} ({percent:.1f}%)\n"
        message += f"**⚡ Velocidad:** {speed_str}\n"
        message += f"**🕐 Tiempo restante:** {eta_str}\n"
        
        # Agregar información de lote si hay múltiples archivos
        if total_files > 1:
            message += f"**📋 En lote:** {current_file}/{total_files} "
            message += f"({current_file/total_files*100:.0f}% del lote)\n"
        
        # Agregar información adicional si se proporciona
        if additional_info:
            for key, value in additional_info.items():
                if value:
                    message += f"**{key}:** {value}\n"
        
        # Agregar información del usuario si está disponible
        if user_first_name:
            message += f"**👤 Usuario:** {user_first_name}"
        
        return message
    
    def create_completion_message(self, filename: str, total_size: int, 
                                 duration: float, speed: float,
                                 success: bool = True, 
                                 message: Optional[str] = None) -> str:
        """
        Crea mensaje de finalización de proceso
        
        Args:
            filename: Nombre del archivo
            total_size: Tamaño total procesado
            duration: Duración del proceso en segundos
            speed: Velocidad promedio
            success: Si el proceso fue exitoso
            message: Mensaje adicional
        
        Returns:
            String del mensaje de finalización
        """
        icon = "✅" if success else "❌"
        status = "COMPLETADO" if success else "FALLADO"
        
        result = f"{icon} **PROCESO {status}**\n\n"
        
        if success:
            result += f"**📄 Archivo:** `{filename}`\n"
            result += f"**📏 Tamaño:** {self.format_file_size(total_size)}\n"
            result += f"**⏱️ Duración:** {duration:.1f} segundos\n"
            result += f"**⚡ Velocidad promedio:** {self.format_speed(speed)}\n"
            
            if duration > 0 and total_size > 0:
                efficiency = total_size / duration / (1024 * 1024)  # MB/s
                result += f"**🎯 Eficiencia:** {efficiency:.1f} MB/s\n"
        else:
            result += f"**📄 Archivo:** `{filename}`\n"
        
        if message:
            result += f"\n**📝 Nota:** {message}"
        
        return result
    
    def create_batch_summary(self, total_files: int, successful: int, 
                            failed: int, total_size: int, 
                            total_duration: float) -> str:
        """
        Crea resumen de procesamiento por lotes
        
        Args:
            total_files: Total de archivos procesados
            successful: Archivos exitosos
            failed: Archivos fallidos
            total_size: Tamaño total procesado
            total_duration: Duración total
        
        Returns:
            String del resumen
        """
        success_rate = (successful / total_files * 100) if total_files > 0 else 0
        
        summary = f"📊 **RESUMEN DE PROCESAMIENTO POR LOTES**\n\n"
        summary += f"**📁 Total de archivos:** {total_files}\n"
        summary += f"**✅ Exitosos:** {successful}\n"
        summary += f"**❌ Fallidos:** {failed}\n"
        summary += f"**📈 Tasa de éxito:** {success_rate:.1f}%\n"
        summary += f"**📏 Tamaño total:** {self.format_file_size(total_size)}\n"
        summary += f"**⏱️ Tiempo total:** {total_duration:.1f}s\n"
        
        if total_duration > 0:
            avg_speed = total_size / total_duration
            summary += f"**⚡ Velocidad promedio:** {self.format_speed(avg_speed)}\n"
        
        if successful > 0:
            avg_time_per_file = total_duration / successful
            summary += f"**⏳ Tiempo por archivo:** {avg_time_per_file:.1f}s\n"
        
        return summary
    
    def estimate_remaining_time(self, start_time: float, current: int, 
                               total: int, total_files: int, 
                               current_file: int) -> str:
        """
        Estima tiempo restante total para lotes de archivos
        
        Args:
            start_time: Timestamp de inicio
            current: Bytes procesados del archivo actual
            total: Bytes totales del archivo actual
            total_files: Total de archivos
            current_file: Archivo actual
        
        Returns:
            String con tiempo estimado restante
        """
        if current_file > total_files or total <= 0:
            return "Calculando..."
        
        # Tiempo transcurrido
        elapsed = time.time() - start_time
        
        # Estimar tiempo para archivo actual
        if current > 0:
            file_progress = current / total
            if file_progress > 0:
                estimated_file_time = elapsed / file_progress
                remaining_file_time = estimated_file_time - elapsed
            else:
                remaining_file_time = 0
        else:
            remaining_file_time = 0
        
        # Estimar tiempo para archivos restantes
        remaining_files = total_files - current_file
        avg_file_time = elapsed / current_file if current_file > 0 else 0
        
        total_remaining_time = remaining_file_time + (remaining_files * avg_file_time)
        
        # Formatear tiempo
        if total_remaining_time < 60:
            return f"{int(total_remaining_time)}s"
        elif total_remaining_time < 3600:
            minutes = int(total_remaining_time // 60)
            seconds = int(total_remaining_time % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(total_remaining_time // 3600)
            minutes = int((total_remaining_time % 3600) // 60)
            return f"{hours}h {minutes}m"


# Instancia global
progress_service = AdvancedProgressService()