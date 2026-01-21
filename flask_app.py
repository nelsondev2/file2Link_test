import os
import time
import urllib.parse
import logging
from flask import Flask, Response, jsonify, render_template_string, request, send_file, make_response
from werkzeug.utils import safe_join
from io import BytesIO

from config import BASE_DIR, RENDER_DOMAIN, MAX_FILE_SIZE_MB, HASH_EXPIRE_DAYS, MAX_CACHED_USERS, MAX_FILES_PER_USER
from load_manager import load_manager
from file_service import file_service
from url_utils import decode_filename_from_url

logger = logging.getLogger(__name__)

# ===== CREAR LA APLICACIÓN FLASK PRIMERO =====
app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB límite

# ===== FUNCIONES AUXILIARES =====
def get_directory_structure(startpath):
    """Genera la estructura de directorios similar a la imagen"""
    structure = []
    try:
        for root, dirs, files in os.walk(startpath):
            level = root.replace(startpath, '').count(os.sep)
            indent = ' ' * 2 * level
            structure.append(f"{indent}📁 {os.path.basename(root)}/")
            subindent = ' ' * 2 * (level + 1)
            for file in files:
                size = os.path.getsize(os.path.join(root, file))
                size_str = format_file_size(size)
                structure.append(f"{subindent}📄 {file} ({size_str})")
    except Exception as e:
        structure.append(f"Error reading directory: {str(e)}")
    return structure

def format_file_size(size):
    """Formatea el tamaño del archivo"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

# ===== RUTAS =====
@app.route('/files')
def file_browser():
    """Navegador de archivos del servidor"""
    try:
        directory = BASE_DIR
        if not os.path.exists(directory):
            return "Directory not found", 404
        
        structure = get_directory_structure(directory)
        
        html_template = '''
        <!DOCTYPE html>
        <html lang="es">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Nelson File2Link - Explorador de Archivos</title>
            <style>
                * { margin: 0; padding: 0; box-sizing: border-box; }
                body { 
                    font-family: 'Courier New', monospace; 
                    background: #1a1a1a; 
                    color: #00ff00; 
                    padding: 20px;
                    line-height: 1.6;
                }
                .container { max-width: 1200px; margin: 0 auto; }
                .header { 
                    text-align: center; 
                    margin-bottom: 30px; 
                    padding: 20px;
                    background: #2a2a2a;
                    border-radius: 10px;
                    border: 1px solid #00ff00;
                }
                .header h1 { color: #00ff00; margin-bottom: 10px; }
                .file-structure { 
                    background: #2a2a2a; 
                    padding: 20px; 
                    border-radius: 10px;
                    border: 1px solid #00ff00;
                    white-space: pre;
                    overflow-x: auto;
                    font-size: 14px;
                }
                .folder { color: #ffff00; }
                .file { color: #ffffff; }
                .size { color: #888; }
                .navigation { 
                    margin-bottom: 20px; 
                    text-align: center;
                }
                .btn { 
                    display: inline-block;
                    background: #00ff00;
                    color: #000;
                    padding: 10px 20px;
                    margin: 0 10px;
                    text-decoration: none;
                    border-radius: 5px;
                    font-weight: bold;
                }
                .stats {
                    background: #2a2a2a;
                    padding: 15px;
                    border-radius: 10px;
                    margin-bottom: 20px;
                    border: 1px solid #00ff00;
                }
                .stats h3 { color: #00ff00; margin-bottom: 10px; }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🗂️ Explorador de Archivos - Nelson File2Link</h1>
                    <p>Estructura completa del sistema de archivos</p>
                </div>
                
                <div class="navigation">
                    <a href="/" class="btn">🏠 Inicio</a>
                    <a href="/system-status" class="btn">📊 Sistema</a>
                    <a href="/files" class="btn">🔄 Actualizar</a>
                </div>
                
                <div class="stats">
                    <h3>📊 Estadísticas del Sistema</h3>
                    <p><strong>Directorio Base:</strong> {{ base_dir }}</p>
                    <p><strong>Total de Archivos:</strong> {{ total_files }}</p>
                    <p><strong>Espacio Usado:</strong> {{ total_size }}</p>
                    <p><strong>Usuarios Registrados:</strong> {{ total_users }}</p>
                    <p><strong>Optimización RAM:</strong> ✅ ACTIVA ({{ max_users }} usuarios máx)</p>
                </div>
                
                <div class="file-structure">
                    {% for line in structure %}
                        {{ line|safe }}
                    {% endfor %}
                </div>
            </div>
        </body>
        </html>
        '''
        
        total_files = 0
        total_size = 0
        for root, dirs, files in os.walk(directory):
            total_files += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        
        total_users = file_service.total_users_count()
        
        return render_template_string(html_template,
            structure=structure,
            base_dir=directory,
            total_files=total_files,
            total_size=format_file_size(total_size),
            total_users=total_users,
            max_users=MAX_CACHED_USERS
        )
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/')
def home():
    """Página principal con estadísticas mejoradas"""
    total_users = file_service.total_users_count()
    
    # Calcular archivos totales
    total_files = 0
    total_size = 0
    if os.path.exists(BASE_DIR):
        for root, dirs, files in os.walk(BASE_DIR):
            total_files += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
    
    total_size_mb = total_size / (1024 * 1024)
    
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Nelson File2Link - Servidor de Archivos</title>
        <style>
            * {{
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }}
            
            body {{
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                color: #333;
            }}
            
            .container {{
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
            }}
            
            .header {{
                text-align: center;
                margin-bottom: 40px;
                padding: 40px 20px;
                background: rgba(255, 255, 255, 0.95);
                border-radius: 20px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                backdrop-filter: blur(10px);
            }}
            
            .header h1 {{
                font-size: 2.5rem;
                margin-bottom: 10px;
                color: #2c3e50;
            }}
            
            .header p {{
                font-size: 1.2rem;
                color: #7f8c8d;
                margin-bottom: 20px;
            }}
            
            .status-badge {{
                display: inline-block;
                background: #27ae60;
                color: white;
                padding: 8px 20px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 0.9rem;
            }}
            
            .ram-badge {{
                display: inline-block;
                background: #3498db;
                color: white;
                padding: 8px 20px;
                border-radius: 25px;
                font-weight: bold;
                font-size: 0.9rem;
                margin-left: 10px;
            }}
            
            .btn {{
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
            }}
            
            .btn:hover {{
                background: #2980b9;
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0, 0, 0, 0.2);
            }}
            
            .btn-telegram {{
                background: #0088cc;
            }}
            
            .btn-telegram:hover {{
                background: #0077b5;
            }}
            
            .info-section {{
                background: rgba(255, 255, 255, 0.95);
                padding: 30px;
                border-radius: 15px;
                margin-bottom: 20px;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
            }}
            
            .info-section h3 {{
                color: #2c3e50;
                margin-bottom: 15px;
                font-size: 1.4rem;
            }}
            
            .info-section p {{
                line-height: 1.6;
                margin-bottom: 10px;
                color: #5d6d7e;
            }}
            
            .code {{
                background: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 8px;
                font-family: 'Courier New', monospace;
                margin: 10px 0;
                overflow-x: auto;
            }}
            
            .features {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin-top: 30px;
            }}
            
            .feature-card {{
                background: rgba(255, 255, 255, 0.95);
                padding: 25px;
                border-radius: 15px;
                text-align: center;
                box-shadow: 0 5px 20px rgba(0, 0, 0, 0.1);
                transition: transform 0.3s ease;
            }}
            
            .feature-card:hover {{
                transform: translateY(-5px);
            }}
            
            .feature-icon {{
                font-size: 2.5rem;
                margin-bottom: 15px;
            }}
            
            .feature-card h4 {{
                color: #2c3e50;
                margin-bottom: 10px;
                font-size: 1.2rem;
            }}
            
            .stats {{
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 20px 0;
            }}
            
            .stat-card {{
                background: rgba(255, 255, 255, 0.95);
                padding: 20px;
                border-radius: 10px;
                text-align: center;
                box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
            }}
            
            .stat-number {{
                font-size: 2rem;
                font-weight: bold;
                color: #3498db;
                margin-bottom: 5px;
            }}
            
            .stat-label {{
                font-size: 0.9rem;
                color: #7f8c8d;
            }}
            
            .optimization {{
                background: #2c3e50;
                color: white;
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }}
            
            .optimization h4 {{
                color: #3498db;
                margin-bottom: 10px;
            }}
            
            @media (max-width: 768px) {{
                .header h1 {{
                    font-size: 2rem;
                }}
                
                .features {{
                    grid-template-columns: 1fr;
                }}
                
                .stats {{
                    grid-template-columns: 1fr;
                }}
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🤖 Nelson File2Link - V2 Optimizado</h1>
                <div class="status-badge">✅ ACTIVO Y FUNCIONANDO</div>
                <div class="ram-badge">⚡ OPTIMIZADO 512MB RAM</div>
                <p>Servidor profesional de archivos via Telegram con optimización de memoria</p>
                <p><strong>📏 Tamaño máximo por archivo: {MAX_FILE_SIZE_MB} MB</strong></p>
                
                <a href="https://t.me/nelson_file2link_bot" class="btn btn-telegram">🚀 Usar el Bot en Telegram</a>
                <a href="/system-status" class="btn">📊 Estado del Sistema</a>
                <a href="/health" class="btn">❤️ Health Check</a>
                <a href="/files" class="btn">📁 Explorador de Archivos</a>
                <a href="/api/stats" class="btn">📈 Estadísticas API</a>
            </div>

            <div class="optimization">
                <h4>⚡ OPTIMIZACIONES DE MEMORIA ACTIVAS:</h4>
                <p>• Streaming de archivos (sin cargar en RAM)</p>
                <p>• Límite: {MAX_CACHED_USERS} usuarios en caché</p>
                <p>• Límite: {MAX_FILES_PER_USER} archivos por usuario</p>
                <p>• Cleanup automático cada 30 minutos</p>
                <p>• Sin psutil (ahorro de 30-50MB RAM)</p>
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{total_users}</div>
                    <div class="stat-label">Usuarios Activos</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{total_files}</div>
                    <div class="stat-label">Archivos Totales</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{total_size_mb:.1f} MB</div>
                    <div class="stat-label">Espacio Usado</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">{MAX_FILE_SIZE_MB} MB</div>
                    <div class="stat-label">Límite por Archivo</div>
                </div>
            </div>

            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <h4>Optimización RAM</h4>
                    <p>Sistema optimizado para funcionar en 512MB sin sobrecargar</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🔐</div>
                    <h4>Seguridad Mejorada</h4>
                    <p>URLs con hash único y temporal, acceso controlado</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">📁</div>
                    <h4>Sistema de Usuarios</h4>
                    <p>Registro automático con límites inteligentes</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🔄</div>
                    <h4>Cola Inteligente</h4>
                    <p>Procesamiento optimizado con límites anti-abuso</p>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">📊</div>
                    <h4>Estadísticas</h4>
                    <p>Sistema de administración completo</p>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">🎯</div>
                    <h4>Fácil Gestión</h4>
                    <p>Comandos mejorados y organización avanzada</p>
                </div>
            </div>

            <div class="info-section">
                <h3>⚡ NUEVO: Sistema Optimizado para 512MB RAM</h3>
                <p><strong>Problema anterior:</strong> Consumo excesivo de RAM (>700MB)</p>
                <p><strong>Solución implementada:</strong></p>
                <div class="code">
• Streaming de archivos (evita carga en RAM)
• Límite de {MAX_CACHED_USERS} usuarios en memoria
• Límite de {MAX_FILES_PER_USER} archivos por usuario
• Eliminado psutil (ahorro 30-50MB)
• Cleanup automático periódico
• Estructuras de datos optimizadas</div>
                
                <h3>🔐 Sistema de URLs Seguras:</h3>
                <p><strong>Ahora (seguro):</strong> <code>https://dominio.com/download/abc123def456?file=archivo.zip</code></p>
                <p>• Cada URL tiene hash único de 12 caracteres</p>
                <p>• Los hashes expiran después de {HASH_EXPIRE_DAYS} días</p>
                <p>• Imposible adivinar URLs de otros usuarios</p>

                <h3>👥 Sistema de Administración:</h3>
                <div class="code">/users - Ver total de usuarios registrados
/broadcast - Enviar mensaje a todos los usuarios
/stats - Estadísticas completas del sistema
/about - Información técnica del bot</div>
                
                <h3>📏 Especificaciones Técnicas Optimizadas:</h3>
                <div class="code">Tamaño máximo por archivo: {MAX_FILE_SIZE_MB} MB
Hash de seguridad: 12 caracteres, {HASH_EXPIRE_DAYS} días
Usuarios en caché: {MAX_CACHED_USERS} máximo
Archivos por usuario: {MAX_FILES_PER_USER} máximo
Memoria objetivo: 250-350MB (dentro de 512MB límite)</div>
            </div>

            <div class="info-section">
                <h3>🚀 Endpoints del API Optimizado</h3>
                <div class="code">/ - Esta página principal
/health - Verificación de estado del servicio
/system-status - Estado detallado del sistema
/api/stats - Estadísticas en JSON
/files - Explorador de archivos del servidor
/download/{{hash}}?file=nombre - Descargar archivo (STREAMING)
/packed/{{hash}}?file=nombre - Descargar archivo empaquetado (STREAMING)</div>
                
                <h3>🔧 Características Técnicas Avanzadas</h3>
                <p><strong>Arquitectura:</strong> Bot de Telegram + Servidor Web Flask optimizado</p>
                <p><strong>Seguridad:</strong> URLs con hash temporal, streaming seguro</p>
                <p><strong>Optimización:</strong> Sistema diseñado para 512MB RAM de Render</p>
                <p><strong>Compatibilidad:</strong> 100% compatible con funciones originales</p>
            </div>

            <div class="info-section" style="text-align: center; background: #2c3e50; color: white;">
                <h3 style="color: white;">🤖 Nelson File2Link - V2 Optimizado</h3>
                <p>Optimizado para funcionar en entornos con recursos limitados (512MB RAM)</p>
                <p>Sistema profesional de gestión de archivos via Telegram</p>
                <p>© 2024 - Versión Optimizada para Bajo Consumo de Memoria</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Endpoint de health check para monitoreo"""
    total_users = file_service.total_users_count()
    
    return jsonify({
        "status": "online",
        "service": "nelson-file2link-v2-optimized",
        "bot_status": "running",
        "timestamp": time.time(),
        "version": "2.0.1",
        "total_users": total_users,
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "hash_security": True,
        "queue_system": True,
        "user_system": True,
        "memory_optimized": True,
        "ram_limits": {
            "max_cached_users": MAX_CACHED_USERS,
            "max_files_per_user": MAX_FILES_PER_USER,
            "streaming_enabled": True
        }
    })

@app.route('/system-status')
def system_status():
    """Endpoint para verificar el estado detallado del sistema"""
    status = load_manager.get_status()
    
    # Obtener información del sistema de archivos
    storage_info = {
        "base_directory": BASE_DIR,
        "exists": os.path.exists(BASE_DIR),
        "total_files": 0,
        "total_size_mb": 0
    }
    
    if os.path.exists(BASE_DIR):
        total_size = 0
        total_files = 0
        for root, dirs, files in os.walk(BASE_DIR):
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    total_files += 1
        
        storage_info.update({
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2)
        })
    
    total_users = file_service.total_users_count()
    
    return jsonify({
        "status": "online",
        "service": "nelson-file2link-v2-optimized",
        "timestamp": time.time(),
        "memory_optimized": True,
        "users": {
            "total_users": total_users,
            "max_cached_users": MAX_CACHED_USERS,
            "user_system": True,
            "registration_enabled": True
        },
        "security": {
            "hash_enabled": True,
            "hash_expire_days": HASH_EXPIRE_DAYS,
            "url_protection": "enabled",
            "streaming_enabled": True
        },
        "system_load": status,
        "storage": storage_info,
        "configuration": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "max_cached_users": MAX_CACHED_USERS,
            "max_files_per_user": MAX_FILES_PER_USER,
            "max_concurrent_processes": load_manager.max_processes,
            "max_queue_size": 10,
            "max_concurrent_uploads": 1,
            "optimized_for": "512mb-ram-environment"
        },
        "endpoints": {
            "web_interface": "/",
            "health_check": "/health",
            "system_status": "/system-status",
            "api_stats": "/api/stats",
            "secure_download": "/download/<hash>?file=<filename>",
            "secure_packed": "/packed/<hash>?file=<filename>",
            "file_browser": "/files"
        }
    })

@app.route('/api/stats')
def api_stats():
    """API de estadísticas completas"""
    total_users = file_service.total_users_count()
    
    # Calcular estadísticas de archivos
    total_files_downloads = 0
    total_files_packed = 0
    total_size = 0
    
    for user_id in file_service.users:
        user_id_int = int(user_id)
        downloads = len(file_service.list_user_files(user_id_int, "downloads"))
        packed = len(file_service.list_user_files(user_id_int, "packed"))
        user_size = file_service.get_user_storage_usage(user_id_int)
        
        total_files_downloads += downloads
        total_files_packed += packed
        total_size += user_size
    
    # Estadísticas de hashes
    expired_cleaned = file_service.cleanup_expired_hashes()
    
    return jsonify({
        "users": {
            "total": total_users,
            "max_cached": MAX_CACHED_USERS,
            "registration_active": True
        },
        "files": {
            "total_downloads": total_files_downloads,
            "total_packed": total_files_packed,
            "total_all": total_files_downloads + total_files_packed,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 3),
            "max_per_user": MAX_FILES_PER_USER
        },
        "security": {
            "active_hashes": len(file_service.file_hashes),
            "expired_cleaned": expired_cleaned,
            "hash_system": "md5_12chars",
            "expire_days": HASH_EXPIRE_DAYS
        },
        "optimization": {
            "memory_optimized": True,
            "streaming_enabled": True,
            "periodic_cleanup": True,
            "ram_safe": True
        },
        "system": {
            "uptime": load_manager.get_status().get('uptime_seconds', 0),
            "active_processes": load_manager.active_processes,
            "max_processes": load_manager.max_processes,
            "timestamp": time.time()
        }
    })

@app.route('/download/<file_hash>')
def secure_download(file_hash):
    """Descarga segura con hash - USANDO STREAMING"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({"error": "Nombre de archivo requerido"}), 400
        
        # Decodificar nombre de archivo
        filename = decode_filename_from_url(filename)
        
        # Verificar hash
        file_info = file_service.get_file_by_hash(file_hash)
        if not file_info:
            return jsonify({"error": "Hash inválido o expirado"}), 403
        
        user_dir = file_service.get_user_directory(file_info['user_id'], file_info['file_type'])
        file_path = safe_join(user_dir, file_info['filename'])
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        # Obtener nombre original
        original_name = file_service.get_original_filename(file_info['user_id'], file_info['filename'], file_info['file_type'])
        
        # Crear nombre seguro para header
        from url_utils import fix_problematic_filename
        safe_display_name = fix_problematic_filename(original_name)
        
        # STREAMING del archivo (sin cargar en RAM)
        def generate():
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):  # Bloques de 8KB
                    yield chunk
        
        response = Response(
            generate(),
            mimetype='application/octet-stream',
            direct_passthrough=True
        )
        
        response.headers['Content-Disposition'] = f'attachment; filename="{safe_display_name}"'
        response.headers['Content-Length'] = str(os.path.getsize(file_path))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        logger.info(f"✅ Descarga streaming: {original_name} via hash {file_hash[:8]}...")
        return response
        
    except Exception as e:
        logger.error(f"Error en descarga segura: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor", "message": str(e)[:100]}), 500

@app.route('/packed/<file_hash>')
def secure_packed(file_hash):
    """Descarga de archivos empaquetados con hash - USANDO STREAMING"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({"error": "Nombre de archivo requerido"}), 400
        
        filename = decode_filename_from_url(filename)
        
        # Verificar hash
        file_info = file_service.get_file_by_hash(file_hash)
        if not file_info:
            return jsonify({"error": "Hash inválido o expirado"}), 403
        
        # Verificar que sea tipo packed
        if file_info['file_type'] != 'packed':
            return jsonify({"error": "Tipo de archivo incorrecto"}), 400
        
        user_dir = file_service.get_user_directory(file_info['user_id'], "packed")
        file_path = safe_join(user_dir, file_info['filename'])
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo empaquetado no encontrado"}), 404
        
        # Obtener nombre original
        original_name = file_service.get_original_filename(file_info['user_id'], file_info['filename'], "packed")
        
        # Crear nombre seguro para header
        from url_utils import fix_problematic_filename
        safe_display_name = fix_problematic_filename(original_name)
        
        # STREAMING del archivo
        def generate():
            with open(file_path, 'rb') as f:
                while chunk := f.read(8192):
                    yield chunk
        
        response = Response(
            generate(),
            mimetype='application/octet-stream',
            direct_passthrough=True
        )
        
        response.headers['Content-Disposition'] = f'attachment; filename="{safe_display_name}"'
        response.headers['Content-Length'] = str(os.path.getsize(file_path))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        
        logger.info(f"✅ Packed download streaming: {original_name} via hash {file_hash[:8]}...")
        return response
        
    except Exception as e:
        logger.error(f"Error en packed download: {e}", exc_info=True)
        return jsonify({"error": "Error interno del servidor"}), 500

@app.errorhandler(404)
def not_found(error):
    """Manejo de errores 404"""
    return jsonify({
        "error": "Endpoint no encontrado",
        "message": "La ruta solicitada no existe",
        "available_endpoints": [
            "/",
            "/health", 
            "/system-status",
            "/api/stats",
            "/files",
            "/download/<hash>?file=<filename>",
            "/packed/<hash>?file=<filename>"
        ],
        "optimized": True,
        "memory_safe": True
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Manejo de errores 500"""
    return jsonify({
        "error": "Error interno del servidor",
        "message": "Ha ocurrido un error inesperado",
        "timestamp": time.time(),
        "service": "nelson-file2link-v2-optimized",
        "optimized": True
    }), 500

# ===== EJECUCIÓN DIRECTA (solo para desarrollo) =====
if __name__ == '__main__':
    # Solo para desarrollo local
    app.run(host='0.0.0.0', port=8080, debug=False)