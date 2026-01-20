import urllib.parse
import re

def encode_filename_for_url(filename):
    """Codifica un nombre de archivo para URL de manera segura"""
    if not filename:
        return "file"
    
    # Primero limpiar caracteres problemáticos
    # Eliminar caracteres que causan problemas en URLs
    problem_chars = r'[#%&{}<>:"/\\|?*\'"`!@$+=]'
    cleaned = re.sub(problem_chars, '', filename)
    
    # Si quedó muy corto, usar nombre genérico
    if len(cleaned) < 3:
        cleaned = "file"
    
    # Codificar caracteres restantes
    encoded = urllib.parse.quote(cleaned, safe='')
    
    return encoded

def decode_filename_from_url(filename):
    """Decodifica un nombre de archivo de URL"""
    try:
        return urllib.parse.unquote(filename, errors='replace')
    except:
        return filename

def is_url_safe(filename):
    """Verifica si un nombre es seguro para URL"""
    if not filename:
        return False
    
    # Caracteres que definitivamente rompen URLs
    dangerous_chars = r'[#%&{}<>:"/\\|?*]'
    if re.search(dangerous_chars, filename):
        return False
    
    # Caracteres que pueden causar problemas
    problematic_chars = r'[\'"`]'
    if re.search(problematic_chars, filename):
        return False
    
    return True

def fix_problematic_filename(filename):
    """Arregla nombres de archivo problemáticos"""
    if not filename:
        return "archivo"
    
    # Reemplazar caracteres problemáticos
    replacements = {
        "'": "",
        '"': "",
        "`": "",
        "´": "",
        "!": "",
        "@": "at",
        "#": "num",
        "$": "dol",
        "%": "por",
        "&": "y",
        "*": "ast",
        "+": "mas",
        "=": "igual",
        "?": "",
        "|": "",
        "\\": "",
        "/": "",
        ":": "",
        "<": "",
        ">": "",
        "{": "",
        "}": "",
        "[": "",
        "]": "",
    }
    
    fixed = filename
    for char, replacement in replacements.items():
        fixed = fixed.replace(char, replacement)
    
    # Si después de limpiar queda muy corto o vacío
    if not fixed or len(fixed) < 3:
        import time
        fixed = f"archivo_{int(time.time()) % 10000}"
    
    return fixed