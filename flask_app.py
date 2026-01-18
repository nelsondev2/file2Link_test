import os
import time
import json
from flask import Flask, send_from_directory, jsonify, render_template_string, request, Response

from config import BASE_DIR, RENDER_DOMAIN, MAX_FILE_SIZE_MB
from load_manager import load_manager
from file_service import file_service
from streaming_service import streaming_service

app = Flask(__name__)

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
        
        # Calcular estadísticas
        total_files = 0
        total_size = 0
        for root, dirs, files in os.walk(directory):
            total_files += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                total_size += os.path.getsize(file_path)
        
        return render_template_string(html_template,
            structure=structure,
            base_dir=directory,
            total_files=total_files,
            total_size=format_file_size(total_size)
        )
        
    except Exception as e:
        return f"Error: {str(e)}", 500

@app.route('/')
def home():
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
                <h1>🤖 Nelson File2Link</h1>
                <div class="status-badge">✅ ACTIVO Y FUNCIONANDO</div>
                <p>Servidor profesional de archivos via Telegram</p>
                <p><strong>📏 Tamaño máximo por archivo: {MAX_FILE_SIZE_MB} MB</strong></p>
                
                <a href="https://t.me/nelson_file2link_bot" class="btn btn-telegram">🚀 Usar el Bot en Telegram</a>
                <a href="/system-status" class="btn">📊 Estado del Sistema</a>
                <a href="/health" class="btn">❤️ Health Check</a>
                <a href="/files" class="btn">📁 Explorador de Archivos</a>
            </div>

            <div class="stats">
                <div class="stat-card">
                    <div class="stat-number">{MAX_FILE_SIZE_MB} MB</div>
                    <div class="stat-label">Límite por Archivo</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">📁</div>
                    <div class="stat-label">Sistema de Carpetas</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">📦</div>
                    <div class="stat-label">Empaquetado ZIP</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number">🔄</div>
                    <div class="stat-label">Cola Inteligente</div>
                </div>
            </div>

            <div class="features">
                <div class="feature-card">
                    <div class="feature-icon">📁</div>
                    <h4>Almacenamiento Seguro</h4>
                    <p>Tus archivos almacenados de forma segura con enlaces permanentes y cifrado</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">📦</div>
                    <h4>Empaquetado Simple</h4>
                    <p>Une todos tus archivos en un ZIP sin compresión para descargas rápidas</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">🔄</div>
                    <h4>Cola Inteligente</h4>
                    <p>Procesamiento automático de múltiples archivos en cola con progreso en tiempo real</p>
                </div>
                
                <div class="feature-card">
                    <div class="feature-icon">⚡</div>
                    <h4>Descargas Rápidas</h4>
                    <p>Sube y descarga archivos hasta {MAX_FILE_SIZE_MB}MB con enlaces directos</p>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">🔐</div>
                    <h4>Acceso Seguro</h4>
                    <p>Cada usuario tiene su espacio privado con archivos organizados y protegidos</p>
                </div>

                <div class="feature-card">
                    <div class="feature-icon">🎯</div>
                    <h4>Fácil Gestión</h4>
                    <p>Renombra, elimina y organiza tus archivos fácilmente desde Telegram</p>
                </div>
            </div>

            <div class="info-section">
                <h3>📁 ¿Cómo funciona?</h3>
                <p>1. <strong>Envía cualquier archivo</strong> al bot de Telegram (@nelson_file2link_bot)</p>
                <p>2. <strong>El archivo se guarda</strong> en tu carpeta personal segura en el servidor</p>
                <p>3. <strong>Obtienes un enlace web permanente</strong> para compartir o descargar</p>
                <p>4. <strong>Gestiona tus archivos</strong> fácilmente desde cualquier dispositivo</p>

                <h3>🎬 STREAMING EN DIRECTO (NUEVO)</h3>
                <p>• <strong>Videos y audios</strong> se reproducen directamente en el navegador</p>
                <p>• <strong>Player HTML5</strong> con controles completos (pausa, volumen, etc.)</p>
                <p>• <strong>No requiere descarga</strong> para ver o escuchar contenido</p>
                <p>• <strong>Soporte para móviles</strong> y tablets</p>

                <h3>🔗 Ejemplo de enlace de streaming:</h3>
                <div class="code">https://nelson-file2link.onrender.com/stream_page/123456/mi_video.mp4</div>
                
                <h3>🔗 Ejemplo de enlace de descarga:</h3>
                <div class="code">https://nelson-file2link.onrender.com/storage/123456/downloads/mi_archivo.pdf</div>
                
                <h3>📁 Sistema de Carpetas:</h3>
                <div class="code">/cd downloads - Acceder a archivos de descarga
/cd packed - Acceder a archivos empaquetados
/list - Ver archivos en carpeta actual
/rename 3 nuevo_nombre - Renombrar archivo #3
/delete 5 - Eliminar archivo #5
/clear - Vaciar carpeta actual</div>
                
                <h3>📦 Comandos de Empaquetado:</h3>
                <div class="code">/pack - Crear ZIP con todos los archivos de descarga
/pack 100 - Dividir en partes de 100MB cada una</div>
                
                <h3>🔄 Comandos de Cola:</h3>
                <div class="code">/queue - Ver archivos en cola de procesamiento
/clearqueue - Limpiar cola de descargas</div>

                <h3>🔍 Comandos de Información:</h3>
                <div class="code">/status - Ver estado del sistema y uso de almacenamiento
/help - Mostrar ayuda completa
/cleanup - Limpiar archivos temporales</div>

                <h3>📏 Límites y Especificaciones:</h3>
                <div class="code">Tamaño máximo por archivo: {MAX_FILE_SIZE_MB} MB
Archivos soportados: Documentos, Videos, Audio, Fotos
Formato de empaquetado: ZIP sin compresión
Máximo de procesos concurrentes: 1
Sistema optimizado para baja CPU</div>
            </div>

            <div class="info-section">
                <h3>🚀 Características Técnicas</h3>
                <p><strong>Arquitectura:</strong> Bot de Telegram + Servidor Web Flask</p>
                <p><strong>Almacenamiento:</strong> Sistema de archivos con estructura por usuario</p>
                <p><strong>Seguridad:</strong> Enlaces únicos por usuario y archivo</p>
                <p><strong>Rendimiento:</strong> Optimizado para entornos con recursos limitados</p>
                <p><strong>Escalabilidad:</strong> Procesamiento en cola para múltiples usuarios</p>
                
                <h3>🔧 Endpoints del API:</h3>
                <div class="code">/health - Verificación de estado del servicio
/system-status - Estado detallado del sistema
/storage/[user_id]/downloads/[archivo] - Descargar archivos
/storage/[user_id]/packed/[archivo] - Descargar archivos empaquetados
/stream/[user_id]/[archivo] - Streaming directo (range requests)
/stream_page/[user_id]/[archivo] - Página HTML con player
/files - Explorador de archivos del servidor</div>

                <h3>🛡️ Características de Seguridad:</h3>
                <div class="code">• Sanitización automática de nombres de archivo
• Hash único por archivo para streaming
• Validación de tamaño máximo
• Protección contra caracteres maliciosos
• Cada usuario tiene espacio aislado</div>
            </div>

            <div class="info-section" style="text-align: center; background: #2c3e50; color: white;">
                <h3 style="color: white;">🤖 Nelson File2Link</h3>
                <p>Sistema profesional de gestión de archivos via Telegram</p>
                <p>Desarrollado para Render.com - Optimizado para bajos recursos</p>
                <p>© 2024 - Todos los derechos reservados</p>
            </div>
        </div>
    </body>
    </html>
    """

@app.route('/health')
def health():
    """Endpoint de health check para monitoreo"""
    return jsonify({
        "status": "online",
        "service": "nelson-file2link",
        "bot_status": "running",
        "timestamp": time.time(),
        "version": "3.0.0",
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "features": [
            "streaming",
            "file_management",
            "packing",
            "queue_system",
            "admin_tools"
        ]
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
        "total_size_mb": 0,
        "users_count": 0
    }
    
    if os.path.exists(BASE_DIR):
        total_size = 0
        total_files = 0
        users_dirs = set()
        
        for root, dirs, files in os.walk(BASE_DIR):
            # Contar usuarios únicos
            if root.count(os.sep) == BASE_DIR.count(os.sep) + 1:
                dir_name = os.path.basename(root)
                if dir_name.isdigit():
                    users_dirs.add(dir_name)
            
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
                    total_files += 1
        
        storage_info.update({
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "total_size_gb": round(total_size / (1024 * 1024 * 1024), 2),
            "users_count": len(users_dirs)
        })
    
    # Información de metadata
    metadata_info = {
        "total_entries": len(file_service.metadata),
        "downloads_count": 0,
        "packed_count": 0
    }
    
    for key in file_service.metadata.keys():
        if "_downloads" in key:
            metadata_info["downloads_count"] += len(file_service.metadata[key]["files"])
        elif "_packed" in key:
            metadata_info["packed_count"] += len(file_service.metadata[key]["files"])
    
    return jsonify({
        "status": "online",
        "service": "nelson-file2link-optimized",
        "timestamp": time.time(),
        "system_load": status,
        "storage": storage_info,
        "metadata": metadata_info,
        "configuration": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "max_concurrent_processes": load_manager.max_processes,
            "cpu_usage_limit": status.get('cpu_percent', 0),
            "memory_usage_percent": status.get('memory_percent', 0),
            "optimized_for": "low-cpu-environment"
        },
        "endpoints": {
            "web_interface": "/",
            "health_check": "/health",
            "system_status": "/system-status",
            "file_download": "/storage/<user_id>/<folder>/<filename>",
            "file_streaming": "/stream/<user_id>/<filename>",
            "streaming_page": "/stream_page/<user_id>/<filename>",
            "file_browser": "/files"
        }
    })

@app.route('/storage/<path:path>')
def serve_static(path):
    """Sirve archivos estáticos de forma genérica forzando la descarga"""
    try:
        # Verificar si el archivo existe
        full_path = os.path.join(BASE_DIR, path)
        
        if not os.path.exists(full_path):
            return jsonify({
                "error": "Archivo no encontrado",
                "path": path,
                "message": "El archivo no existe en el servidor"
            }), 404
        
        # Extraer información del path
        parts = path.split('/')
        if len(parts) >= 3:
            user_id = parts[0]
            folder_type = parts[1]
            filename = '/'.join(parts[2:])
            
            # Obtener nombre original del archivo
            if folder_type in ["downloads", "packed"]:
                original_filename = file_service.get_original_filename(user_id, os.path.basename(filename), folder_type)
            else:
                original_filename = os.path.basename(filename)
        else:
            original_filename = os.path.basename(path)
        
        # Servir el archivo
        response = send_from_directory(BASE_DIR, path)
        
        # Configurar headers para forzar descarga
        response.headers["Content-Disposition"] = f"attachment; filename=\"{original_filename}\""
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
    except Exception as e:
        return jsonify({
            "error": "Archivo no encontrado",
            "path": path,
            "message": str(e)
        }), 404

@app.route('/storage/<user_id>/downloads/<filename>')
def serve_download(user_id, filename):
    """Sirve archivos de descarga forzando la descarga"""
    try:
        user_download_dir = os.path.join(BASE_DIR, user_id, "downloads")
        
        # Verificar que el directorio existe
        if not os.path.exists(user_download_dir):
            return jsonify({
                "error": "Usuario no encontrado",
                "user_id": user_id
            }), 404
        
        # Verificar que el archivo existe
        file_path = os.path.join(user_download_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({
                "error": "Archivo no encontrado",
                "filename": filename,
                "user_id": user_id
            }), 404
        
        # Obtener el nombre original del archivo desde la metadata
        original_filename = file_service.get_original_filename(user_id, filename, "downloads")
        
        # Verificar si es una solicitud de streaming (range request)
        range_header = request.headers.get('Range')
        
        if range_header and (filename.lower().endswith(('.mp4', '.webm', '.ogg', '.mp3', '.wav', '.m4a'))):
            # Usar streaming service para archivos multimedia con range requests
            response = streaming_service.serve_file_with_range(user_id, filename, request.headers)
            if response:
                # Forzar descarga en lugar de streaming
                response.headers["Content-Disposition"] = f"attachment; filename=\"{original_filename}\""
                return response
        
        # Servir el archivo forzando la descarga (método tradicional)
        response = send_from_directory(user_download_dir, filename)
        
        # Configurar headers para forzar descarga
        response.headers["Content-Disposition"] = f"attachment; filename=\"{original_filename}\""
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
        
    except Exception as e:
        return jsonify({
            "error": "Error interno del servidor",
            "message": str(e)
        }), 500

@app.route('/storage/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados forzando la descarga"""
    try:
        user_packed_dir = os.path.join(BASE_DIR, user_id, "packed")
        
        # Verificar que el directorio existe
        if not os.path.exists(user_packed_dir):
            return jsonify({
                "error": "Usuario no encontrado o sin archivos empaquetados",
                "user_id": user_id
            }), 404
        
        # Verificar que el archivo existe
        file_path = os.path.join(user_packed_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({
                "error": "Archivo empaquetado no encontrado",
                "filename": filename,
                "user_id": user_id
            }), 404
        
        # Obtener el nombre original del archivo desde la metadata
        original_filename = file_service.get_original_filename(user_id, filename, "packed")
        
        # Servir el archivo forzando la descarga
        response = send_from_directory(user_packed_dir, filename)
        
        # Configurar headers para forzar descarga
        response.headers["Content-Disposition"] = f"attachment; filename=\"{original_filename}\""
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
        
    except Exception as e:
        return jsonify({
            "error": "Error interno del servidor",
            "message": str(e)
        }), 500

@app.route('/stream/<user_id>/<filename>')
def stream_file(user_id, filename):
    """Endpoint para streaming de archivos con range requests"""
    try:
        # Verificar que el archivo existe
        user_dir = file_service.get_user_directory(user_id, "downloads")
        file_path = os.path.join(user_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({
                "error": "Archivo no encontrado",
                "user_id": user_id,
                "filename": filename
            }), 404
        
        # Verificar que sea un archivo multimedia
        file_ext = os.path.splitext(filename)[1].lower()
        if file_ext not in ['.mp4', '.webm', '.ogg', '.mp3', '.wav', '.m4a', '.flac', '.aac']:
            return jsonify({
                "error": "Formato no soportado para streaming",
                "filename": filename,
                "supported_formats": ['.mp4', '.webm', '.ogg', '.mp3', '.wav', '.m4a', '.flac', '.aac']
            }), 400
        
        # Servir archivo con soporte para range requests (streaming)
        response = streaming_service.serve_file_with_range(user_id, filename, request.headers)
        
        if response:
            # Configurar headers adicionales para streaming
            response.headers["Accept-Ranges"] = "bytes"
            response.headers["Access-Control-Allow-Origin"] = "*"
            response.headers["Access-Control-Allow-Methods"] = "GET, HEAD"
            response.headers["Access-Control-Expose-Headers"] = "Content-Length, Content-Range"
            
            # No forzar descarga, permitir reproducción en navegador
            if "Content-Disposition" in response.headers:
                del response.headers["Content-Disposition"]
            
            return response
        else:
            # Fallback a descarga directa
            return send_from_directory(user_dir, filename)
        
    except Exception as e:
        return jsonify({
            "error": "Error en streaming",
            "message": str(e)
        }), 500

@app.route('/stream_page/<user_id>/<filename>')
def stream_page(user_id, filename):
    """Página HTML para streaming con reproductor"""
    try:
        # Verificar que el archivo existe
        user_dir = file_service.get_user_directory(user_id, "downloads")
        file_path = os.path.join(user_dir, filename)
        
        if not os.path.exists(file_path):
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head><title>Error - Archivo no encontrado</title></head>
            <body style="background: #1a1a1a; color: white; padding: 40px; text-align: center;">
                <h1>❌ Archivo no encontrado</h1>
                <p>El archivo solicitado no existe en el servidor.</p>
                <a href="/" style="color: #3498db;">Volver al inicio</a>
            </body>
            </html>
            ''')
        
        # Crear página de streaming
        html_content = streaming_service.create_stream_page(user_id, filename)
        
        if html_content:
            return html_content
        else:
            return render_template_string('''
            <!DOCTYPE html>
            <html>
            <head><title>Error - Streaming</title></head>
            <body style="background: #1a1a1a; color: white; padding: 40px; text-align: center;">
                <h1>❌ Error creando página de streaming</h1>
                <p>No se pudo generar la página de reproducción.</p>
                <a href="/" style="color: #3498db;">Volver al inicio</a>
            </body>
            </html>
            ''')
        
    except Exception as e:
        return render_template_string(f'''
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body style="background: #1a1a1a; color: white; padding: 40px; text-align: center;">
            <h1>❌ Error del servidor</h1>
            <p>{str(e)}</p>
            <a href="/" style="color: #3498db;">Volver al inicio</a>
        </body>
        </html>
        ''')

@app.route('/api/metadata')
def get_metadata():
    """Endpoint API para obtener metadata del sistema (solo lectura)"""
    try:
        # Estadísticas básicas
        stats = {
            "total_users": 0,
            "total_files": 0,
            "total_size_mb": 0,
            "downloads_count": 0,
            "packed_count": 0
        }
        
        # Contar usuarios únicos
        user_ids = set()
        for key in file_service.metadata.keys():
            if "_downloads" in key or "_packed" in key:
                try:
                    user_id = key.split("_")[0]
                    user_ids.add(user_id)
                    
                    if "_downloads" in key:
                        stats["downloads_count"] += len(file_service.metadata[key]["files"])
                    elif "_packed" in key:
                        stats["packed_count"] += len(file_service.metadata[key]["files"])
                except:
                    continue
        
        stats["total_users"] = len(user_ids)
        stats["total_files"] = stats["downloads_count"] + stats["packed_count"]
        
        # Calcular tamaño total
        total_size = 0
        if os.path.exists(BASE_DIR):
            for root, dirs, files in os.walk(BASE_DIR):
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
        
        stats["total_size_mb"] = round(total_size / (1024 * 1024), 2)
        
        return jsonify({
            "status": "success",
            "timestamp": time.time(),
            "stats": stats,
            "metadata_summary": {
                "total_entries": len(file_service.metadata),
                "last_updated": file_service.metadata.get("_last_updated", "unknown")
            }
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500

@app.route('/api/user/<user_id>/files')
def get_user_files(user_id):
    """Endpoint API para obtener archivos de un usuario específico"""
    try:
        downloads = file_service.list_user_files(user_id, "downloads")
        packed = file_service.list_user_files(user_id, "packed")
        
        # Formatear respuesta
        response_data = {
            "user_id": user_id,
            "downloads": [],
            "packed": [],
            "stats": {
                "total_files": len(downloads) + len(packed),
                "total_downloads": len(downloads),
                "total_packed": len(packed),
                "storage_used_mb": round(file_service.get_user_storage_usage(user_id) / (1024 * 1024), 2)
            }
        }
        
        # Procesar downloads
        for file_info in downloads:
            response_data["downloads"].append({
                "id": file_info["number"],
                "name": file_info["name"],
                "stored_name": file_info["stored_name"],
                "size_mb": file_info["size_mb"],
                "download_url": file_info["url"],
                "stream_url": file_info.get("stream_url"),
                "type": "download"
            })
        
        # Procesar packed
        for file_info in packed:
            response_data["packed"].append({
                "id": file_info["number"],
                "name": file_info["name"],
                "stored_name": file_info["stored_name"],
                "size_mb": file_info["size_mb"],
                "download_url": file_info["url"],
                "type": "packed"
            })
        
        return jsonify({
            "status": "success",
            "data": response_data
        })
        
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "user_id": user_id
        }), 500

@app.route('/admin')
def admin_panel():
    """Panel de administración básico (solo para ver)"""
    try:
        # Solo permitir acceso local o con token (simple)
        admin_token = request.args.get('token', '')
        allowed_tokens = os.getenv("ADMIN_TOKENS", "admin123").split(",")
        
        if admin_token not in allowed_tokens and request.remote_addr not in ["127.0.0.1", "localhost"]:
            return "Acceso no autorizado", 403
        
        # Obtener estadísticas
        import psutil
        
        system_stats = load_manager.get_status()
        
        # Estadísticas de almacenamiento
        total_files = 0
        total_size = 0
        users_count = 0
        
        if os.path.exists(BASE_DIR):
            for root, dirs, files in os.walk(BASE_DIR):
                if root.count(os.sep) == BASE_DIR.count(os.sep) + 1:
                    users_count += 1
                
                total_files += len(files)
                for file in files:
                    file_path = os.path.join(root, file)
                    if os.path.isfile(file_path):
                        total_size += os.path.getsize(file_path)
        
        # Metadata stats
        metadata_stats = {
            "total_entries": len(file_service.metadata),
            "downloads_count": 0,
            "packed_count": 0
        }
        
        for key in file_service.metadata.keys():
            if "_downloads" in key:
                metadata_stats["downloads_count"] += len(file_service.metadata[key]["files"])
            elif "_packed" in key:
                metadata_stats["packed_count"] += len(file_service.metadata[key]["files"])
        
        html = f'''<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Panel - Nelson File2Link</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }}
        .container {{ max-width: 1400px; margin: 0 auto; }}
        .header {{ 
            text-align: center; 
            margin-bottom: 40px;
            padding: 30px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 15px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .header h1 {{ 
            color: #00d4ff;
            margin-bottom: 10px;
            font-size: 2.5rem;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: rgba(255, 255, 255, 0.05);
            padding: 25px;
            border-radius: 12px;
            border: 1px solid rgba(255, 255, 255, 0.1);
            transition: transform 0.3s, border-color 0.3s;
        }}
        .stat-card:hover {{
            transform: translateY(-5px);
            border-color: #00d4ff;
        }}
        .stat-card h3 {{
            color: #00d4ff;
            margin-bottom: 15px;
            font-size: 1.2rem;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .stat-value {{
            font-size: 2rem;
            font-weight: bold;
            color: #fff;
            margin-bottom: 5px;
        }}
        .stat-label {{
            color: #aaa;
            font-size: 0.9rem;
        }}
        .status-badge {{
            display: inline-block;
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.8rem;
            font-weight: bold;
            margin-left: 10px;
        }}
        .status-online {{ background: #27ae60; color: white; }}
        .status-offline {{ background: #e74c3c; color: white; }}
        .status-warning {{ background: #f39c12; color: white; }}
        .section {{
            background: rgba(255, 255, 255, 0.05);
            padding: 25px;
            border-radius: 12px;
            margin-bottom: 30px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .section h2 {{
            color: #00d4ff;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 2px solid rgba(0, 212, 255, 0.3);
        }}
        .endpoint-list {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 15px;
        }}
        .endpoint {{
            background: rgba(0, 0, 0, 0.2);
            padding: 15px;
            border-radius: 8px;
            border-left: 4px solid #00d4ff;
        }}
        .endpoint-method {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: bold;
            margin-right: 10px;
        }}
        .method-get {{ background: #27ae60; color: white; }}
        .method-post {{ background: #3498db; color: white; }}
        .endpoint-path {{
            font-family: 'Courier New', monospace;
            color: #00d4ff;
            margin: 10px 0;
        }}
        .endpoint-desc {{
            color: #aaa;
            font-size: 0.9rem;
        }}
        .refresh-btn {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 10px 20px;
            border-radius: 25px;
            text-decoration: none;
            font-weight: bold;
            margin-top: 20px;
            transition: background 0.3s;
        }}
        .refresh-btn:hover {{
            background: #2980b9;
        }}
        .system-status {{
            display: flex;
            align-items: center;
            gap: 20px;
            margin-top: 15px;
            padding: 15px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 8px;
        }}
        .cpu-bar, .ram-bar, .disk-bar {{
            flex: 1;
        }}
        .bar-container {{
            height: 10px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 5px;
            overflow: hidden;
            margin-top: 5px;
        }}
        .bar-fill {{
            height: 100%;
            border-radius: 5px;
        }}
        .cpu-bar .bar-fill {{ background: linear-gradient(90deg, #00d4ff, #0088cc); }}
        .ram-bar .bar-fill {{ background: linear-gradient(90deg, #27ae60, #219653); }}
        .disk-bar .bar-fill {{ background: linear-gradient(90deg, #f39c12, #e67e22); }}
        .bar-label {{
            display: flex;
            justify-content: space-between;
            font-size: 0.9rem;
            color: #aaa;
        }}
        @media (max-width: 768px) {{
            .stats-grid {{ grid-template-columns: 1fr; }}
            .endpoint-list {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 Admin Panel - Nelson File2Link</h1>
            <p>Panel de monitoreo y administración del sistema</p>
            <div class="status-badge status-online">✅ SISTEMA OPERATIVO</div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <h3>📊 ESTADÍSTICAS GENERALES</h3>
                <div class="stat-value">{total_files}</div>
                <div class="stat-label">Archivos totales en el sistema</div>
                <div class="stat-value">{users_count}</div>
                <div class="stat-label">Usuarios activos</div>
                <div class="stat-value">{round(total_size / (1024**3), 2)} GB</div>
                <div class="stat-label">Espacio total usado</div>
            </div>
            
            <div class="stat-card">
                <h3>📁 METADATA</h3>
                <div class="stat-value">{metadata_stats['total_entries']}</div>
                <div class="stat-label">Entradas en metadata</div>
                <div class="stat-value">{metadata_stats['downloads_count']}</div>
                <div class="stat-label">Archivos en downloads</div>
                <div class="stat-value">{metadata_stats['packed_count']}</div>
                <div class="stat-label">Archivos empaquetados</div>
            </div>
            
            <div class="stat-card">
                <h3>⚙️ CONFIGURACIÓN</h3>
                <div class="stat-value">{MAX_FILE_SIZE_MB} MB</div>
                <div class="stat-label">Límite por archivo</div>
                <div class="stat-value">{load_manager.max_processes}</div>
                <div class="stat-label">Procesos máximos</div>
                <div class="stat-value">{'✅ Activado' if system_stats['can_accept_work'] else '❌ Desactivado'}</div>
                <div class="stat-label">Aceptando trabajo</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📈 ESTADO DEL SISTEMA</h2>
            <div class="system-status">
                <div class="cpu-bar">
                    <div class="bar-label">
                        <span>CPU</span>
                        <span>{system_stats.get('cpu_percent', 0):.1f}%</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {system_stats.get('cpu_percent', 0)}%"></div>
                    </div>
                </div>
                
                <div class="ram-bar">
                    <div class="bar-label">
                        <span>RAM</span>
                        <span>{system_stats.get('memory_percent', 0):.1f}%</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {system_stats.get('memory_percent', 0)}%"></div>
                    </div>
                </div>
                
                <div class="disk-bar">
                    <div class="bar-label">
                        <span>DISCO</span>
                        <span>{psutil.disk_usage('/').percent:.1f}%</span>
                    </div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {psutil.disk_usage('/').percent}%"></div>
                    </div>
                </div>
            </div>
            
            <div style="margin-top: 20px; color: #aaa; font-size: 0.9rem;">
                <p>🔄 <strong>Procesos activos:</strong> {system_stats.get('active_processes', 0)} / {system_stats.get('max_processes', 1)}</p>
                <p>⏰ <strong>Última actualización:</strong> {time.strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p>🌐 <strong>IP de acceso:</strong> {request.remote_addr}</p>
            </div>
        </div>
        
        <div class="section">
            <h2>🔗 ENDPOINTS DISPONIBLES</h2>
            <div class="endpoint-list">
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/</div>
                    <div class="endpoint-desc">Interfaz web principal del sistema</div>
                </div>
                
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/health</div>
                    <div class="endpoint-desc">Health check del servicio</div>
                </div>
                
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/system-status</div>
                    <div class="endpoint-desc">Estado detallado del sistema (JSON)</div>
                </div>
                
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/files</div>
                    <div class="endpoint-desc">Explorador de archivos del servidor</div>
                </div>
                
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/storage/&lt;user_id&gt;/downloads/&lt;filename&gt;</div>
                    <div class="endpoint-desc">Descargar archivos de usuario</div>
                </div>
                
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/stream/&lt;user_id&gt;/&lt;filename&gt;</div>
                    <div class="endpoint-desc">Streaming de archivos multimedia</div>
                </div>
                
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/stream_page/&lt;user_id&gt;/&lt;filename&gt;</div>
                    <div class="endpoint-desc">Página HTML con reproductor</div>
                </div>
                
                <div class="endpoint">
                    <span class="endpoint-method method-get">GET</span>
                    <div class="endpoint-path">/api/metadata</div>
                    <div class="endpoint-desc">API para obtener metadata del sistema</div>
                </div>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 40px;">
            <a href="/admin?token={admin_token}" class="refresh-btn">🔄 Actualizar Panel</a>
            <a href="/" class="refresh-btn" style="background: #27ae60; margin-left: 10px;">🏠 Ir al Inicio</a>
            <a href="/files" class="refresh-btn" style="background: #f39c12; margin-left: 10px;">📁 Explorador</a>
        </div>
        
        <div style="text-align: center; margin-top: 40px; color: #666; font-size: 0.9rem;">
            <p>🤖 <strong>Nelson File2Link v3.0</strong> - Panel de Administración</p>
            <p>© 2024 - Sistema optimizado para Render.com</p>
            <p style="margin-top: 10px;">
                <span style="color: #00d4ff;">●</span> Online 
                <span style="color: #f39c12; margin-left: 20px;">●</span> Advertencia 
                <span style="color: #e74c3c; margin-left: 20px;">●</span> Crítico
            </p>
        </div>
    </div>
    
    <script>
        // Auto-refresh cada 60 segundos
        setTimeout(function() {{
            window.location.reload();
        }}, 60000);
        
        // Actualizar hora
        function updateTime() {{
            const now = new Date();
            document.getElementById('current-time').textContent = 
                now.toLocaleDateString('es-ES') + ' ' + now.toLocaleTimeString('es-ES');
        }}
        
        setInterval(updateTime, 1000);
        updateTime();
    </script>
</body>
</html>'''
        
        return html
        
    except Exception as e:
        return f"Error en panel de administración: {str(e)}", 500

@app.errorhandler(404)
def not_found(error):
    """Manejo de errores 404"""
    return jsonify({
        "status": "error",
        "error": "Endpoint no encontrado",
        "message": "La ruta solicitada no existe en el servidor",
        "timestamp": time.time(),
        "available_endpoints": [
            "/",
            "/health", 
            "/system-status",
            "/files",
            "/admin",
            "/api/metadata",
            "/storage/<user_id>/downloads/<filename>",
            "/storage/<user_id>/packed/<filename>",
            "/stream/<user_id>/<filename>",
            "/stream_page/<user_id>/<filename>",
            "/api/user/<user_id>/files"
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Manejo de errores 500"""
    return jsonify({
        "status": "error",
        "error": "Error interno del servidor",
        "message": "Ha ocurrido un error inesperado en el servidor",
        "timestamp": time.time(),
        "support": "Contacta al administrador del sistema"
    }), 500

@app.errorhandler(400)
def bad_request(error):
    """Manejo de errores 400"""
    return jsonify({
        "status": "error",
        "error": "Solicitud incorrecta",
        "message": "La solicitud no puede ser procesada",
        "timestamp": time.time()
    }), 400

@app.errorhandler(403)
def forbidden(error):
    """Manejo de errores 403"""
    return jsonify({
        "status": "error",
        "error": "Acceso prohibido",
        "message": "No tienes permisos para acceder a este recurso",
        "timestamp": time.time()
    }), 403

@app.before_request
def log_request_info():
    """Log de solicitudes para debugging"""
    if request.path.startswith('/storage/') or request.path.startswith('/stream/'):
        app.logger.info(f'Request: {request.method} {request.path} - IP: {request.remote_addr}')

@app.after_request
def add_security_headers(response):
    """Añadir headers de seguridad a todas las respuestas"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    # Headers específicos para archivos
    if request.path.startswith('/storage/') or request.path.startswith('/stream/'):
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
    
    return response

if __name__ == '__main__':
    # Solo para desarrollo local
    app.run(host='0.0.0.0', port=8080, debug=False)