import os
import time
import hashlib
import hmac
import logging
from functools import wraps
from flask import Flask, send_from_directory, jsonify, render_template_string, request, abort

from config import BASE_DIR, RENDER_DOMAIN, MAX_FILE_SIZE_MB, SECRET_KEY, DOWNLOAD_LINK_EXPIRY_HOURS, ALLOWED_WEB_USERNAMES
from load_manager import load_manager
from file_service import async_file_service

app = Flask(__name__)
app.secret_key = SECRET_KEY

logger = logging.getLogger(__name__)

# ==================== FUNCIONES AUXILIARES ====================

def extract_telegram_username():
    """Extrae el username de Telegram de los headers o parámetros"""
    # 1. Intentar obtener de headers personalizados
    telegram_username = request.headers.get('X-Telegram-Username', '')
    
    # 2. También buscar en parámetros de query string
    if not telegram_username:
        telegram_username = request.args.get('telegram_username', '')
    
    # 3. Buscar en Referer (cuando se accede desde Telegram)
    if not telegram_username:
        referer = request.headers.get('Referer', '')
        if 't.me/' in referer:
            # Extraer username de t.me/username
            import re
            match = re.search(r't\.me/([a-zA-Z0-9_]+)', referer)
            if match:
                telegram_username = match.group(1)
    
    # 4. Buscar en User-Agent como fallback
    if not telegram_username:
        user_agent = request.headers.get('User-Agent', '')
        if 'TelegramBot' in user_agent or 'Telegram' in user_agent:
            # Intentar extraer username del User-Agent
            import re
            match = re.search(r'@([a-zA-Z0-9_]+)', user_agent)
            if match:
                telegram_username = match.group(1)
    
    return telegram_username.lower().replace('@', '') if telegram_username else ''

def validate_download_token(user_id, filename, expiry_timestamp):
    """Valida token de descarga"""
    if time.time() > expiry_timestamp:
        logger.warning(f"Token expirado para {user_id}/{filename}")
        return False
    
    secret = SECRET_KEY.encode()
    message = f"{user_id}:{filename}:{expiry_timestamp}".encode()
    expected_token = hmac.new(secret, message, hashlib.sha256).hexdigest()
    
    provided_token = request.args.get('token', '')
    
    return hmac.compare_digest(expected_token, provided_token)

def generate_download_token(user_id, filename):
    """Genera token temporal para descarga"""
    expiry = int(time.time()) + (DOWNLOAD_LINK_EXPIRY_HOURS * 3600)
    secret = SECRET_KEY.encode()
    message = f"{user_id}:{filename}:{expiry}".encode()
    token = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return token, expiry

def require_monitoring_access(f):
    """Solo permite acceso a rutas de monitoreo desde usernames específicos"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Solo aplicar esta restricción a rutas de monitoreo
        monitoring_paths = ['/', '/health']
        
        if request.path in monitoring_paths:
            telegram_username = extract_telegram_username()
            
            if not telegram_username:
                logger.warning(f"Intento de acceso sin username a {request.path} desde {request.remote_addr}")
                return jsonify({
                    "error": "Acceso restringido",
                    "message": "Esta ruta solo es accesible desde bots de Telegram autorizados.",
                    "hint": "Incluye tu username de Telegram en los headers (X-Telegram-Username) o parámetros (?telegram_username=)"
                }), 403
            
            allowed_usernames_lower = [u.lower() for u in ALLOWED_WEB_USERNAMES]
            
            if telegram_username not in allowed_usernames_lower:
                logger.warning(f"Username no autorizado: @{telegram_username} intentó acceder a {request.path}")
                return jsonify({
                    "error": "Acceso denegado",
                    "message": f"El username @{telegram_username} no está autorizado para acceder a esta ruta.",
                    "authorized_usernames": ALLOWED_WEB_USERNAMES
                }), 403
            
            logger.info(f"Acceso autorizado a {request.path} por @{telegram_username}")
        
        return f(*args, **kwargs)
    return decorated_function

# ==================== RUTAS SEGURAS ====================

@app.route('/')
@require_monitoring_access
def home():
    """Página principal solo accesible desde bots autorizados"""
    telegram_username = extract_telegram_username()
    
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>File2Link Bot - Monitoreo</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }}
            .container {{
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 500px;
            }}
            h1 {{
                color: #333;
                margin-bottom: 10px;
            }}
            .status {{
                background: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                display: inline-block;
                margin: 10px 0;
                font-weight: bold;
            }}
            .info {{
                background: #f8f9fa;
                padding: 15px;
                border-radius: 10px;
                margin: 20px 0;
                text-align: left;
                font-size: 14px;
            }}
            .access-info {{
                background: #e3f2fd;
                padding: 10px;
                border-radius: 5px;
                margin: 10px 0;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 File2Link Bot</h1>
            <div class="status">🔐 ACCESO AUTORIZADO</div>
            <div class="access-info">
                <strong>Acceso concedido a:</strong><br>
                @{telegram_username}
            </div>
            <p>Sistema de almacenamiento y enlaces directos vía Telegram</p>
            
            <div class="info">
                <strong>Información del servicio:</strong>
                <ul>
                    <li><strong>Estado:</strong> ✅ OPERATIVO</li>
                    <li><strong>Límite por archivo:</strong> {MAX_FILE_SIZE_MB} MB</li>
                    <li><strong>Almacenamiento por usuario:</strong> {MAX_USER_STORAGE_MB} MB</li>
                    <li><strong>Tokens de descarga:</strong> {DOWNLOAD_LINK_EXPIRY_HOURS} horas</li>
                </ul>
            </div>
            
            <div class="info">
                <strong>Rutas disponibles:</strong>
                <ul>
                    <li><code>/health</code> - Estado del servicio</li>
                    <li><code>/storage/{'{user_id}'}/downloads/{'{filename}'}</code> - Descargas</li>
                    <li><code>/storage/{'{user_id}'}/packed/{'{filename}'}</code> - Archivos empaquetados</li>
                </ul>
            </div>
            
            <p><small>Este panel solo es accesible desde bots autorizados</small></p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
@require_monitoring_access
def health():
    """Health check solo para bots autorizados"""
    telegram_username = extract_telegram_username()
    
    # Obtener estadísticas del sistema
    system_status = load_manager.get_status()
    
    # Calcular tamaño de almacenamiento
    total_size = 0
    total_files = 0
    if os.path.exists(BASE_DIR):
        for root, dirs, files in os.walk(BASE_DIR):
            total_files += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
    
    total_size_mb = total_size / (1024 * 1024)
    
    return jsonify({
        "status": "online",
        "service": "file2link-bot",
        "timestamp": time.time(),
        "authorized_user": f"@{telegram_username}",
        "security": {
            "monitoring_access": "restricted_to_authorized_bots",
            "authorized_bots": ALLOWED_WEB_USERNAMES
        },
        "system": {
            "cpu_percent": system_status.get('cpu_percent', 0),
            "memory_percent": system_status.get('memory_percent', 0),
            "active_processes": system_status.get('active_processes', 0),
            "max_processes": system_status.get('max_processes', 0),
            "can_accept_work": system_status.get('can_accept_work', False)
        },
        "storage": {
            "total_files": total_files,
            "total_size_mb": round(total_size_mb, 2),
            "base_directory": BASE_DIR,
            "exists": os.path.exists(BASE_DIR)
        },
        "configuration": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "max_user_storage_mb": MAX_USER_STORAGE_MB,
            "download_link_expiry_hours": DOWNLOAD_LINK_EXPIRY_HOURS,
            "max_concurrent_processes": system_status.get('max_processes', 0)
        }
    })

# ==================== RUTAS PÚBLICAS (DESCARGAS) ====================

@app.route('/storage/<user_id>/downloads/<filename>')
def serve_download(user_id, filename):
    """Sirve archivos - PÚBLICO (solo necesita token válido)"""
    try:
        # Validar token
        expiry = request.args.get('expiry', '0')
        token = request.args.get('token', '')
        
        if not validate_download_token(user_id, filename, int(expiry)):
            return jsonify({
                "error": "Acceso denegado",
                "message": "Enlace inválido o expirado."
            }), 403
        
        user_download_dir = os.path.join(BASE_DIR, user_id, "downloads")
        
        if not os.path.exists(user_download_dir):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        file_path = os.path.join(user_download_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        original_filename = async_file_service.get_original_filename(user_id, filename, "downloads")
        response = send_from_directory(user_download_dir, filename)
        response.headers["Content-Disposition"] = f"attachment; filename=\"{original_filename}\""
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
        
    except Exception as e:
        logger.error(f"Error sirviendo descarga: {e}")
        return jsonify({"error": "Error interno del servidor"}), 500

@app.route('/storage/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados - PÚBLICO (solo necesita token válido)"""
    try:
        # Validar token
        expiry = request.args.get('expiry', '0')
        token = request.args.get('token', '')
        
        if not validate_download_token(user_id, filename, int(expiry)):
            return jsonify({
                "error": "Acceso denegado",
                "message": "Enlace inválido o expirado."
            }), 403
        
        user_packed_dir = os.path.join(BASE_DIR, user_id, "packed")
        
        if not os.path.exists(user_packed_dir):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        file_path = os.path.join(user_packed_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        original_filename = async_file_service.get_original_filename(user_id, filename, "packed")
        response = send_from_directory(user_packed_dir, filename)
        response.headers["Content-Disposition"] = f"attachment; filename=\"{original_filename}\""
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["Cache-Control"] = "no-store"
        
        return response
        
    except Exception as e:
        logger.error(f"Error sirviendo archivo empaquetado: {e}")
        return jsonify({"error": "Error interno"}), 500

# ==================== BLOQUEO DE RUTAS SENSIBLES ====================

@app.route('/files')
@app.route('/system-status')
@app.route('/admin')
@app.route('/config')
@app.route('/logs')
@app.route('/metadata')
def blocked_routes():
    """Bloquea rutas sensibles completamente"""
    logger.warning(f"Intento de acceso a ruta bloqueada: {request.path} desde {request.remote_addr}")
    
    return jsonify({
        "error": "Acceso denegado",
        "message": "Esta ruta no está disponible."
    }), 403

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(403)
def forbidden(error):
    """Manejo personalizado de error 403"""
    return jsonify({
        "error": "Acceso denegado",
        "message": "No tienes permiso para acceder a este recurso.",
        "hint": "Para acceder a las rutas de monitoreo (/ y /health), debes ser un bot autorizado."
    }), 403

@app.errorhandler(404)
def not_found(error):
    """Manejo personalizado de error 404"""
    return jsonify({
        "error": "No encontrado",
        "message": "La ruta solicitada no existe."
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Manejo personalizado de error 500"""
    logger.error(f"Error interno: {error}")
    return jsonify({
        "error": "Error interno",
        "message": "Ha ocurrido un error en el servidor."
    }), 500

# ==================== MIDDLEWARE ====================

@app.before_request
def before_request():
    """Middleware ejecutado antes de cada solicitud"""
    # Solo loguear acceso a rutas no-descarga
    if not request.path.startswith('/storage/'):
        logger.info(f"Solicitud: {request.method} {request.path} desde {request.remote_addr}")

@app.after_request
def after_request(response):
    """Middleware ejecutado después de cada solicitud"""
    # Añadir headers de seguridad
    response.headers['Server'] = 'File2Link'
    response.headers['X-Powered-By'] = 'Python/Flask'
    
    # Prevenir clickjacking
    response.headers['X-Frame-Options'] = 'DENY'
    
    # Prevenir MIME type sniffing
    response.headers['X-Content-Type-Options'] = 'nosniff'
    
    return response

if __name__ == '__main__':
    # Configurar logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("="*60)
    logger.info("🤖 File2Link Bot - Servidor Web")
    logger.info("="*60)
    logger.info(f"🔐 Monitoreo restringido a: {ALLOWED_WEB_USERNAMES}")
    logger.info(f"🌐 Dominio: {RENDER_DOMAIN}")
    logger.info(f"📁 Storage: {BASE_DIR}")
    logger.info(f"🚀 Puerto: {PORT}")
    logger.info("="*60)
    
    app.run(host='0.0.0.0', port=8080, debug=False)