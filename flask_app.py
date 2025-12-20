"""
Servidor web que actúa como proxy ligero para Telegram
"""
from flask import Flask, jsonify, redirect, request, render_template_string, send_file
import logging
from datetime import datetime
import io
import requests

from config import RENDER_DOMAIN, BOT_USERNAME, MAX_FILE_SIZE_MB, BOT_TOKEN, TELEGRAM_API_URL

logger = logging.getLogger(__name__)
app = Flask(__name__)

@app.route('/')
def home():
    """Página principal informativa"""
    html_content = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>File2Link Proxy - Sistema Optimizado</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
                line-height: 1.6;
            }
            
            .container {
                max-width: 1000px;
                margin: 0 auto;
                padding: 20px;
            }
            
            .header {
                text-align: center;
                margin-bottom: 40px;
                padding: 40px 20px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                backdrop-filter: blur(10px);
            }
            
            .header h1 {
                font-size: 2.8rem;
                margin-bottom: 10px;
                color: #2c3e50;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            
            .header p {
                font-size: 1.2rem;
                color: #7f8c8d;
                margin-bottom: 20px;
            }
            
            .status-badge {
                display: inline-block;
                background: #27ae60;
                color: white;
                padding: 10px 25px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 1rem;
                margin: 10px 0;
            }
            
            .features {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin: 30px 0;
            }
            
            .feature-card {
                background: rgba(255, 255, 255, 0.95);
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
                transition: all 0.3s ease;
            }
            
            .feature-card:hover {
                transform: translateY(-5px);
                box-shadow: 0 15px 30px rgba(0, 0, 0, 0.15);
            }
            
            .feature-icon {
                font-size: 3rem;
                margin-bottom: 15px;
            }
            
            .feature-card h3 {
                color: #2c3e50;
                margin-bottom: 10px;
                font-size: 1.3rem;
            }
            
            .feature-card p {
                color: #5d6d7e;
                font-size: 0.95rem;
            }
            
            .info-section {
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 20px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            }
            
            .info-section h2 {
                color: #2c3e50;
                margin-bottom: 20px;
                font-size: 1.8rem;
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
            }
            
            .steps {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }
            
            .step {
                text-align: center;
                padding: 20px;
                background: #f8f9fa;
                border-radius: 10px;
            }
            
            .step-number {
                display: inline-block;
                width: 40px;
                height: 40px;
                background: #3498db;
                color: white;
                border-radius: 50%;
                line-height: 40px;
                font-weight: bold;
                margin-bottom: 10px;
            }
            
            .btn {
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 12px 30px;
                text-decoration: none;
                border-radius: 25px;
                margin: 10px;
                font-size: 1rem;
                transition: all 0.3s ease;
                border: none;
                cursor: pointer;
                font-weight: bold;
            }
            
            .btn:hover {
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }
            
            .btn-telegram {
                background: #0088cc;
            }
            
            .btn-telegram:hover {
                background: #0077b5;
            }
            
            .stats {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 30px 0;
            }
            
            .stat-card {
                background: rgba(255, 255, 255, 0.95);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
            }
            
            .stat-number {
                font-size: 2rem;
                font-weight: bold;
                color: #3498db;
                margin-bottom: 5px;
            }
            
            .stat-label {
                font-size: 0.9rem;
                color: #7f8c8d;
            }
            
            .code {
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                margin: 10px 0;
                overflow-x: auto;
                font-size: 0.9rem;
            }
            
            .footer {
                text-align: center;
                margin-top: 40px;
                padding: 20px;
                color: white;
                font-size: 0.9rem;
            }
            
            @media (max-width: 768px) {
                .header h1 {
                    font-size: 2rem;
                }
                
                .features {
                    grid-template-columns: 1fr;
                }
                
                .steps {
                    grid-template-columns: 1fr;
                }
                
                .stats {
                    grid-template-columns: 1fr;
                }
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 File2Link Proxy</h1>
                <div class="status-badge">✅ SISTEMA ACTIVO Y OPTIMIZADO</div>
                <p>Servicio profesional de enlaces permanentes a archivos en Telegram</p>
                <p><strong>📏 Tamaño máximo por archivo: """ + str(MAX_FILE_SIZE_MB) + """ MB</strong></p>
                
                <a href="https://t.me/""" + BOT_USERNAME + """" class="btn btn-telegram" target="_blank">
                    🚀 Usar el Bot en Telegram
                </a>
                <a href="/health" class="btn">❤️ Health Check</a>
                <a href="/system-status" class="btn">📊 Estado del Sistema</a>
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">0%</div>
                    <div class="stat-label">CPU en Render</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">0MB</div>
                    <div class="stat-label">Almacenamiento</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">☁️</div>
                    <div class="stat-label">Todo en Telegram</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">✅</div>
                    <div class="stat-label">Sobrevive reinicios</div>
                </div>
            </div>

            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <h3>Máxima Velocidad</h3>
                    <p>0% procesamiento en servidor. Todo se maneja directamente desde Telegram</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🛡️</div>
                    <h3>Persistencia Total</h3>
                    <p>Archivos y metadatos almacenados en Telegram. Sobreviven a reinicios</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🔗</div>
                    <h3>Enlaces Permanentes</h3>
                    <p>URLs que nunca expiran. Acceso directo a archivos en Telegram</p>
                </div>
            </div>

            <div class="info-section">
                <h2>🚀 ¿Cómo funciona?</h2>
                <div class="steps">
                    <div class="step">
                        <div class="step-number">1</div>
                        <h3>Envía Archivo</h3>
                        <p>Envía cualquier archivo al bot de Telegram</p>
                    </div>
                    <div class="step">
                        <div class="step-number">2</div>
                        <h3>Almacena en Nube</h3>
                        <p>El archivo se guarda en grupos privados de Telegram</p>
                    </div>
                    <div class="step">
                        <div class="step-number">3</div>
                        <h3>Obtén Enlace</h3>
                        <p>Recibe un enlace permanente al archivo</p>
                    </div>
                    <div class="step">
                        <div class="step-number">4</div>
                        <h3>Comparte</h3>
                        <p>Comparte el enlace, funcionará para siempre</p>
                    </div>
                </div>
            </div>

            <div class="info-section">
                <h2>🔗 Tipos de Enlaces Generados</h2>
                <p>Cada archivo genera múltiples URLs para diferentes usos:</p>
                
                <div class="code">
# Enlace de descarga directa (proxy)
""" + RENDER_DOMAIN + """/download/file_id

# Enlace Telegram directo
tg://file?id=file_id

# Deep link del bot
https://t.me/""" + BOT_USERNAME + """?start=file_file_id_userid

# API directa de Telegram
https://api.telegram.org/file/bot[BOT_TOKEN]/file_id
                </div>
                
                <p><strong>Todos estos enlaces apuntan directamente al archivo almacenado en Telegram.</strong></p>
            </div>

            <div class="info-section">
                <h2>⚙️ Arquitectura Técnica</h2>
                <div class="code">
┌─────────────────────────────────────────┐
│         TELEGRAM (Nube - 100%)          │
├─────────────────────────────────────────┤
│ 📁 Grupo DB → Metadatos (JSON/texto)    │
│ 📦 Grupo Storage → Referencias archivos │
│ 🤖 Bot → Gestión y respuestas           │
└─────────────────────────────────────────┘
                    ↑
┌─────────────────────────────────────────┐
│        RENDER (Proxy ligero - 0%)       │
├─────────────────────────────────────────┤
│ 🔗 Redirecciones HTTP                   │
│ 📊 Páginas web informativas             │
│ ❌ CERO descargas/almacenamiento        │
└─────────────────────────────────────────┘
                </div>
                
                <p><strong>Ventajas de esta arquitectura:</strong></p>
                <ul style="margin-left: 20px; color: #5d6d7e;">
                    <li>✅ Funciona en plan FREE de Render</li>
                    <li>✅ Sin límites de almacenamiento</li>
                    <li>✅ Máxima velocidad de acceso</li>
                    <li>✅ 100% confiable (Telegram como backend)</li>
                    <li>✅ Sin mantenimiento del servidor</li>
                </ul>
            </div>

            <div class="info-section">
                <h2>📞 Endpoints del Servicio</h2>
                <div class="code">
GET  /                    → Página principal (esta página)
GET  /health              → Health check del servicio
GET  /system-status       → Estado detallado del sistema
GET  /file/:file_id/:user_id → Proxy a archivo en Telegram
GET  /download/:file_id   → Descarga directa desde Telegram
GET  /list/:user_id       → Lista archivos (vía bot)
                </div>
            </div>

            <div style="text-align: center; margin: 40px 0;">
                <a href="https://t.me/""" + BOT_USERNAME + """" class="btn btn-telegram" target="_blank" style="font-size: 1.2rem; padding: 15px 40px;">
                    🚀 COMENZAR A USAR EL BOT
                </a>
            </div>
        </div>

        <div class="footer">
            <p>🤖 File2Link Proxy Service | Sistema optimizado para Render Free Tier</p>
            <p>© """ + str(datetime.now().year) + """ - Todos los derechos reservados</p>
        </div>
    </body>
    </html>
    """
    
    return html_content

@app.route('/health')
def health():
    """Health check mínimo"""
    return jsonify({
        "status": "online",
        "service": "telegram-file-proxy",
        "timestamp": datetime.now().isoformat(),
        "version": "2.0.0-optimized",
        "resources": {
            "storage_used": "0MB",
            "cpu_load": "0% (todo en Telegram)",
            "optimized_for": "render-free-tier",
            "backend": "telegram-cloud"
        }
    })

@app.route('/system-status')
def system_status():
    """Estado detallado del sistema"""
    return jsonify({
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
        "architecture": {
            "frontend": "render-proxy",
            "backend": "telegram-cloud",
            "database": "telegram-groups",
            "storage": "telegram-files"
        },
        "performance": {
            "cpu_usage": "0%",
            "memory_usage": "minimal",
            "storage_used": "0 bytes",
            "response_time": "instant"
        },
        "configuration": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "bot_username": BOT_USERNAME,
            "render_domain": RENDER_DOMAIN,
            "optimization_level": "maximum"
        },
        "endpoints": {
            "home": "/",
            "health": "/health",
            "system_status": "/system-status",
            "file_proxy": "/file/<file_id>/<user_id>",
            "download": "/download/<file_id>",
            "telegram_bot": f"https://t.me/{BOT_USERNAME}"
        }
    })

@app.route('/file/<file_id>/<user_id>')
def proxy_file(file_id, user_id):
    """Proxy que redirige directamente a Telegram"""
    try:
        # Redirigir a deep link de Telegram
        deep_link = f"https://t.me/{BOT_USERNAME}?start=file_{file_id}_{user_id}"
        
        # Opcional: Página intermedia con opciones
        if request.args.get('direct', '').lower() == 'true':
            # Redirección inmediata
            return redirect(deep_link, code=302)
        else:
            # Página con opciones
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head>
                <title>Descargar Archivo</title>
                <style>
                    body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
                    .btn { display: inline-block; margin: 10px; padding: 12px 24px; background: #0088cc; color: white; text-decoration: none; border-radius: 5px; }
                    .btn:hover { background: #0077b5; }
                </style>
            </head>
            <body>
                <h2>📥 Descargar Archivo</h2>
                <p>ID del archivo: <code>{{ file_id }}</code></p>
                
                <div style="margin: 30px 0;">
                    <a href="{{ telegram_url }}" class="btn" target="_blank">📱 Abrir en Telegram</a>
                    <a href="{{ download_url }}" class="btn">⬇️ Descarga Directa</a>
                </div>
                
                <p style="color: #666; font-size: 0.9em;">
                    <strong>Nota:</strong> El archivo está almacenado en Telegram y es accesible desde cualquier dispositivo.
                </p>
            </body>
            </html>
            ''', 
            file_id=file_id, 
            user_id=user_id,
            telegram_url=deep_link,
            download_url=f"/download/{file_id}"
            )
        
    except Exception as e:
        logger.error(f"Error en proxy: {e}")
        return jsonify({
            "error": "Error en proxy",
            "message": str(e)
        }), 500

@app.route('/download/<file_id>')
def download_file(file_id):
    """Endpoint de descarga directa desde Telegram"""
    try:
        # Obtener información del archivo desde Telegram
        api_url = f"{TELEGRAM_API_URL}/bot{BOT_TOKEN}/getFile?file_id={file_id}"
        
        response = requests.get(api_url, timeout=10)
        if response.status_code != 200:
            return jsonify({
                "error": "No se pudo obtener información del archivo",
                "telegram_response": response.json()
            }), 404
        
        file_info = response.json()
        if not file_info.get('ok'):
            return jsonify({
                "error": "Archivo no encontrado en Telegram",
                "details": file_info
            }), 404
        
        # Construir URL de descarga directa de Telegram
        file_path = file_info['result']['file_path']
        download_url = f"{TELEGRAM_API_URL}/file/bot{BOT_TOKEN}/{file_path}"
        
        # Redirigir directamente a Telegram (el navegador maneja la descarga)
        return redirect(download_url, code=302)
        
    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Timeout al conectar con Telegram",
            "message": "Intenta nuevamente en unos momentos"
        }), 504
    except Exception as e:
        logger.error(f"Error en descarga: {e}")
        return jsonify({
            "error": "Error en descarga",
            "message": str(e)
        }), 500

@app.route('/list/<user_id>')
def list_files(user_id):
    """Endpoint informativo para listar archivos"""
    return jsonify({
        "note": "Para listar tus archivos, usa el bot de Telegram directamente",
        "instructions": "Envía /list al bot para ver todos tus archivos",
        "user_id": user_id,
        "telegram_bot": f"https://t.me/{BOT_USERNAME}",
        "endpoints": {
            "home": "/",
            "health": "/health"
        }
    })

@app.errorhandler(404)
def not_found(error):
    """Manejo de errores 404"""
    return jsonify({
        "error": "Endpoint no encontrado",
        "message": "La ruta solicitada no existe en este servidor",
        "available_endpoints": [
            "/",
            "/health",
            "/system-status",
            "/file/<file_id>/<user_id>",
            "/download/<file_id>",
            f"https://t.me/{BOT_USERNAME} (Bot de Telegram)"
        ],
        "timestamp": datetime.now().isoformat()
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Manejo de errores 500"""
    return jsonify({
        "error": "Error interno del servidor",
        "message": "Ha ocurrido un error inesperado",
        "note": "Este es solo un proxy ligero. Los archivos están seguros en Telegram.",
        "timestamp": datetime.now().isoformat()
    }), 500

if __name__ == '__main__':
    # Solo para desarrollo local
    app.run(host='0.0.0.0', port=8080, debug=False)