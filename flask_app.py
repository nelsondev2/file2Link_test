import os
import time
import hashlib
import hmac
import logging
from flask import Flask, send_from_directory, jsonify, request

from config import BASE_DIR, RENDER_DOMAIN, SECRET_KEY, DOWNLOAD_LINK_EXPIRY_HOURS
from load_manager import load_manager
from file_service import async_file_service

app = Flask(__name__)
app.secret_key = SECRET_KEY

logger = logging.getLogger(__name__)

# ==================== FUNCIONES BÁSICAS ====================

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

# ==================== RUTAS PÚBLICAS ====================

@app.route('/')
def home():
    """Página principal - siempre accesible"""
    return "✅ File2Link Bot está activo"

@app.route('/health')
def health():
    """Health check - siempre accesible"""
    return jsonify({
        "status": "online",
        "timestamp": time.time(),
        "service": "file2link-bot"
    })

@app.route('/status')
def status():
    """Status check para watchbot"""
    return jsonify({
        "status": "online",
        "timestamp": time.time()
    })

# ==================== RUTAS DE DESCARGA ====================

@app.route('/storage/<user_id>/downloads/<filename>')
def serve_download(user_id, filename):
    """Sirve archivos con validación de token"""
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
        
        return response
        
    except Exception as e:
        logger.error(f"Error sirviendo descarga: {e}")
        return jsonify({"error": "Error interno"}), 500

@app.route('/storage/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados con token"""
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
        
        return response
        
    except Exception as e:
        logger.error(f"Error sirviendo archivo empaquetado: {e}")
        return jsonify({"error": "Error interno"}), 500

# ==================== MANEJO DE ERRORES ====================

@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "No encontrado"}), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)