import re
import os
import urllib.parse

logger = None
try:
    import logging
    logger = logging.getLogger(__name__)
except:
    pass

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
    Maneja caracteres como apóstrofes, comillas, etc.
    """
    if not filename:
        return "archivo"
    
    # Caracteres problemáticos para URLs
    # Los caracteres # % & { } $ ! ' ` = + < > : " / \ | ? * pueden causar problemas en URLs
    # Pero mantenemos algunos como apóstrofes para nombres naturales
    
    # Primero, caracteres que realmente rompen URLs
    dangerous_chars = r'[#%&{}<>:"/\\|?*]'
    cleaned = re.sub(dangerous_chars, '_', filename)
    
    # Caracteres que pueden causar problemas pero son comunes en nombres
    # Los mantenemos pero con manejo especial
    common_chars_to_keep = ["'", "`", "=", "+", "!", "$"]
    
    # Para estos caracteres comunes, reemplazamos con versiones seguras
    char_replacements = {
        "'": "",        # Eliminar apóstrofes completamente
        "`": "",        # Eliminar backticks
        '"': "",        # Eliminar comillas
        "´": "",        # Eliminar acento agudo
        "!": "",        # Eliminar exclamación
        "$": "",        # Eliminar signo dólar
        "=": "_",       # Reemplazar igual con guión bajo
        "+": "_",       # Reemplazar más con guión bajo
        "&": "y",       # Reemplazar & con 'y'
        "@": "en",      # Reemplazar @ con 'en'
    }
    
    for char, replacement in char_replacements.items():
        cleaned = cleaned.replace(char, replacement)
    
    # Eliminar múltiples espacios o guiones bajos consecutivos
    cleaned = re.sub(r'_{2,}', '_', cleaned)
    cleaned = re.sub(r'\s{2,}', ' ', cleaned)
    
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
    
    # Si el nombre es muy genérico o tiene caracteres problemáticos, añadir identificador
    generic_names = ['archivo', 'file', 'documento', 'document', 'imagen', 'image', 
                    'video', 'audio', 'foto', 'photo', 'picture', 'img']
    
    # Si el nombre original tiene caracteres problemáticos comunes, usar nombre más seguro
    problem_chars_in_name = any(char in original_name for char in ["'", '"', "`", "!", "@", "#", "$", "%", "&", "*", "+", "="])
    
    if name_part.lower() in generic_names or problem_chars_in_name:
        import time
        import random
        # Crear nombre más seguro con timestamp
        timestamp = int(time.time()) % 10000
        random_num = random.randint(100, 999)
        name_part = f"file_{timestamp}_{random_num}"
    
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
    """Obtiene nombre seguro para URL y lo codifica CORRECTAMENTE"""
    # Primero limpiar el nombre
    safe_name = clean_for_url(filename)
    
    # Codificar SOLO los caracteres necesarios
    # No codificar todo el string, solo caracteres especiales específicos
    encoded_name = urllib.parse.quote(safe_name, safe='')
    
    return encoded_name

def compare_filenames(disk_name, url_name):
    """Compara si dos nombres (disco vs URL) son equivalentes"""
    try:
        # Decodificar el nombre de la URL
        decoded_url_name = urllib.parse.unquote(url_name)
        
        # Normalizar ambos nombres
        disk_clean = clean_for_filesystem(disk_name)
        url_clean = clean_for_url(decoded_url_name)
        
        # Comparar sin extensiones
        disk_base, disk_ext = os.path.splitext(disk_clean)
        url_base, url_ext = os.path.splitext(url_clean)
        
        # Las extensiones deben coincidir (case insensitive)
        if disk_ext.lower() != url_ext.lower():
            return False
        
        # Para las bases, comparar después de limpiar caracteres problemáticos
        # Eliminar caracteres problemáticos de ambos para comparación
        disk_base_clean = re.sub(r'[\'"`!@#$%^&*()+=]', '', disk_base.lower())
        url_base_clean = re.sub(r'[\'"`!@#$%^&*()+=]', '', url_base.lower())
        
        return disk_base_clean == url_base_clean
        
    except Exception as e:
        if logger:
            logger.error(f"Error comparando nombres: {e}")
        return False