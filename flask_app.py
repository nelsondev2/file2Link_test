"""
Servidor web básico para File2Link
"""
from flask import Flask, jsonify, redirect
import logging
from datetime import datetime
import requests

from config import RENDER_DOMAIN, BOT_USERNAME, MAX_FILE_SIZE_MB, BOT_TOKEN, TELEGRAM_API_URL

logger = logging.getLogger(__name__)
app = Flask(__name__)

@app.route('/')
def home():
    """Página principal simple"""
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>File2Link - Servicio de Enlaces</title>
        <style>
            body {{ font-family: Arial, sans-serif; text-align: center; padding: 50px; }}
            .container {{ max-width: 800px; margin: 0 auto; }}
            .header {{ background: #0088cc; color: white; padding: 20px; border-radius: 10px; }}
            .btn {{ display: inline-block; background: #27ae60; color: white; padding: 10px 20px; 
                    text-decoration: none; border-radius: 5px; margin: 10px; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 File2Link Service</h1>
                <p>Servicio de enlaces permanentes a archivos en Telegram</p>
            </div>
            
            <p><strong>Bot de Telegram:</strong> @{BOT_USERNAME}</p>
            <p><strong>Límite por archivo:</strong> {MAX_FILE_SIZE_MB} MB</p>
            
            <div>
                <a href="https://t.me/{BOT_USERNAME.replace('@', '')}" class="btn" target="_blank">
                    🚀 Usar el Bot
                </a>
                <a href="/health" class="btn">❤️ Health Check</a>
            </div>
            
            <p style="margin-top: 30px; color: #666;">
                Este servicio permite generar enlaces permanentes a archivos almacenados en Telegram.
            </p>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        "status": "online",
        "service": "file2link",
        "timestamp": datetime.now().isoformat(),
        "bot": BOT_USERNAME,
        "max_file_size_mb": MAX_FILE_SIZE_MB
    })

@app.route('/download/<file_id>')
def download_file(file_id):
    """Descarga directa desde Telegram"""
    try:
        # Obtener información del archivo
        api_url = f"{TELEGRAM_API_URL}/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            return jsonify({
                "error": "Archivo no encontrado",
                "file_id": file_id
            }), 404
        
        file_info = response.json()
        if not file_info.get('ok'):
            return jsonify({
                "error": "Archivo no disponible",
                "details": file_info
            }), 404
        
        # Redirigir a Telegram para descarga
        file_path = file_info['result']['file_path']
        download_url = f"{TELEGRAM_API_URL}/file/bot{BOT_TOKEN}/{file_path}"
        
        return redirect(download_url, code=302)
        
    except Exception as e:
        logger.error(f"Error en descarga: {e}")
        return jsonify({
            "error": "Error en descarga",
            "message": str(e)
        }), 500

@app.route('/file/<file_id>/<user_id>')
def proxy_file(file_id, user_id):
    """Proxy para archivos"""
    try:
        # Redirigir al bot
        deep_link = f"https://t.me/{BOT_USERNAME.replace('@', '')}?start=file_{file_id}_{user_id}"
        return redirect(deep_link, code=302)
        
    except Exception as e:
        return jsonify({
            "error": "Error en proxy",
            "message": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)