import re
import os
import urllib.parse

def clean_for_filesystem(filename):
    """
    Limpia nombres para sistema de archivos.
    Mantiene: acentos, espacios, (), [], {}, ., ,, -, _, ñ, ¿, ¡, etc.
    Solo elimina caracteres realmente peligrosos para filesystem.
    """
    if not filename:
        return "archivo"
    
    # Caracteres peligrosos para Windows/Linux/Mac
    # < > : " / \ | ? * y también NULL character
    problem_chars = r'[<>:"/\\|?*\x00]'
    
    # Reemplazar con _
    cleaned = re.sub(problem_chars, '_', filename)
    
    # Eliminar puntos al inicio (archivos ocultos en Unix)
    cleaned = cleaned.lstrip('.')
    
    # Limitar longitud (255 es seguro para la mayoría de sistemas)
    if len(cleaned) > 200:
        name, ext = os.path.splitext(cleaned)
        # Preservar extensión
        if ext:
            cleaned = name[:200-len(ext)] + ext
        else:
            cleaned = cleaned[:200]
    
    # Si quedó vacío después de limpiar
    if not cleaned or cleaned.isspace():
        cleaned = "archivo"
    
    return cleaned

def clean_for_url(filename):
    """
    Limpia nombres para URLs.
    Más permisivo que para filesystem.
    Mantiene la mayoría de caracteres, solo elimina los que rompen URLs.
    """
    if not filename:
        return "archivo"
    
    # Solo caracteres que realmente rompen URLs
    # Los caracteres # % & { } $ ! ' ` = + pueden causar problemas en URLs
    problem_chars = r'[#%&{}$!\'`=+<>:"/\\|?*]'
    cleaned = re.sub(problem_chars, '_', filename)
    
    # Limitar longitud para URLs
    if len(cleaned) > 150:
        name, ext = os.path.splitext(cleaned)
        if ext:
            cleaned = name[:150-len(ext)] + ext
        else:
            cleaned = cleaned[:150]
    
    return cleaned

def safe_filename(original_name, user_id=None):
    """
    Crea un nombre seguro y único.
    Preserva la extensión original.
    """
    if not original_name:
        return "archivo"
    
    # Limpiar para filesystem
    safe_name = clean_for_filesystem(original_name)
    
    # Asegurar extensión
    name_part, ext = os.path.splitext(safe_name)
    if not ext and '.' in original_name:
        # Recuperar extensión original si se perdió
        _, original_ext = os.path.splitext(original_name)
        ext = original_ext
    
    # Si el nombre es muy genérico, añadir identificador
    generic_names = ['archivo', 'file', 'documento', 'document', 'imagen', 'image', 
                    'video', 'audio', 'foto', 'photo', 'picture', 'img']
    
    if name_part.lower() in generic_names:
        import time
        name_part = f"{name_part}_{int(time.time()) % 10000}"
    
    # Combinar
    final_name = name_part + (ext if ext else '')
    
    return final_name

def is_filename_safe(filename):
    """Verifica si un nombre es seguro para filesystem"""
    if not filename:
        return False
    
    unsafe_pattern = r'[<>:"/\\|?*\x00]'
    if re.search(unsafe_pattern, filename):
        return False
    
    # No puede estar vacío
    if filename.isspace():
        return False
    
    # No puede empezar con punto (archivos ocultos)
    if filename.startswith('.'):
        return False
    
    # No puede terminar con espacio o punto en Windows
    if filename.endswith(' ') or filename.endswith('.'):
        return False
    
    # Nombres reservados en Windows
    reserved_names = [
        'CON', 'PRN', 'AUX', 'NUL',
        'COM1', 'COM2', 'COM3', 'COM4', 'COM5', 'COM6', 'COM7', 'COM8', 'COM9',
        'LPT1', 'LPT2', 'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9'
    ]
    name_without_ext = os.path.splitext(filename.upper())[0]
    if name_without_ext in reserved_names:
        return False
    
    # Longitud máxima razonable
    if len(filename) > 255:
        return False
    
    return True

def get_url_safe_name(filename):
    """Obtiene nombre seguro para URL y lo codifica"""
    safe_name = clean_for_url(filename)
    return urllib.parse.quote(safe_name)

def compare_filenames(disk_name, url_name):
    """Compara si dos nombres (disco vs URL) son equivalentes"""
    # Normalizar ambos nombres
    disk_clean = clean_for_filesystem(disk_name)
    url_clean = clean_for_url(url_name)
    
    # Comparar sin extensiones
    disk_base, disk_ext = os.path.splitext(disk_clean)
    url_base, url_ext = os.path.splitext(url_clean)
    
    # Las extensiones deben coincidir (case insensitive)
    if disk_ext.lower() != url_ext.lower():
        return False
    
    # Las bases deben ser similares (pero pueden diferir por limpieza)
    # Para propósitos prácticos, si uno está contenido en el otro
    return disk_base in url_base or url_base in disk_base