import os
import time
import hashlib
import hmac
from functools import wraps
from flask import Flask, send_from_directory, jsonify, render_template_string, request, abort

from config import BASE_DIR, RENDER_DOMAIN, MAX_FILE_SIZE_MB, SECRET_KEY, ALLOWED_REFERERS, DOWNLOAD_LINK_EXPIRY_HOURS
from load_manager import load_manager
from file_service import async_file_service

app = Flask(__name__)
app.secret_key = SECRET_KEY

# ==================== DECORADORES DE SEGURIDAD ====================

def require_telegram_referer(f):
    """Solo permite acceso desde Telegram"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        referer = request.headers.get('Referer', '')
        if not any(domain in referer for domain in ALLOWED_REFERERS):
            if request.path.startswith('/storage/'):
                pass
            else:
                abort(403)
        return f(*args, **kwargs)
    return decorated_function

def validate_download_token(user_id, filename, expiry_timestamp):
    """Valida token de descarga"""
    if time.time() > expiry_timestamp:
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

# ==================== RUTAS SEGURAS ====================

@app.route('/')
@require_telegram_referer
def home():
    """Página principal solo accesible desde Telegram"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>File2Link Bot</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, sans-serif;
                margin: 0;
                padding: 20px;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                align-items: center;
                justify-content: center;
            }
            .container {
                background: white;
                padding: 40px;
                border-radius: 20px;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
                max-width: 400px;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
            }
            .status {
                background: #4CAF50;
                color: white;
                padding: 8px 16px;
                border-radius: 20px;
                display: inline-block;
                margin: 10px 0;
                font-weight: bold;
            }
            .telegram-btn {
                display: inline-block;
                background: #0088cc;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 25px;
                margin-top: 20px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🤖 File2Link Bot</h1>
            <div class="status">✅ ACTIVO</div>
            <p>Servicio de almacenamiento y enlaces directos</p>
            <p><strong>Límite: {MAX_FILE_SIZE_MB} MB por archivo</strong></p>
            <a href="https://t.me/nelson_file2link_bot" class="telegram-btn">
                📲 Usar en Telegram
            </a>
        </div>
    </body>
    </html>
    """.format(MAX_FILE_SIZE_MB=MAX_FILE_SIZE_MB)

@app.route('/health')
def health():
    """Health check público pero minimalista"""
    return jsonify({
        "status": "online",
        "timestamp": time.time()
    })

# ==================== RUTAS DE DESCARGA CON TOKEN ====================

@app.route('/storage/<user_id>/downloads/<filename>')
def serve_download(user_id, filename):
    """Sirve archivos con validación de token"""
    try:
        expiry = request.args.get('expiry', '0')
        token = request.args.get('token', '')
        
        if not validate_download_token(user_id, filename, int(expiry)):
            return jsonify({"error": "Enlace inválido o expirado"}), 403
        
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
        response.headers["Cache-Control"] = "no-store"
        
        return response
        
    except Exception as e:
        return jsonify({"error": "Error interno"}), 500

@app.route('/storage/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados con token"""
    try:
        expiry = request.args.get('expiry', '0')
        token = request.args.get('token', '')
        
        if not validate_download_token(user_id, filename, int(expiry)):
            return jsonify({"error": "Enlace inválido o expirado"}), 403
        
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
        
    except:
        return jsonify({"error": "Error interno"}), 500

# ==================== BLOQUEO DE RUTAS PELIGROSAS ====================

@app.route('/files')
@app.route('/system-status')
@app.route('/storage')
def blocked():
    """Bloquea rutas sensibles"""
    return jsonify({"error": "Acceso no permitido"}), 403

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "No encontrado"}), 404

@app.errorhandler(403)
def forbidden(error):
    return jsonify({"error": "Acceso denegado"}), 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)