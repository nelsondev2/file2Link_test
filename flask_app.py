import os
import time
import urllib.parse
import logging
from flask import Flask, jsonify, render_template_string, request, make_response
from werkzeug.utils import safe_join

from config import BASE_DIR, RENDER_DOMAIN, MAX_FILE_SIZE_MB, HASH_EXPIRE_DAYS
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)

# ===== CREAR LA APLICACIÓN FLASK =====
app = Flask(__name__)

# ===== FUNCIONES AUXILIARES =====
def format_size(size):
    """Formatea bytes a KB/MB/GB"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def format_date(timestamp):
    """Formatea timestamp a fecha legible"""
    try:
        return time.strftime('%Y-%m-%d %H:%M', time.localtime(timestamp))
    except:
        return '-'

def get_breadcrumbs(path):
    """Genera breadcrumbs para navegación"""
    breadcrumbs = [{'name': '🏠', 'path': '/'}]
    if path:
        parts = path.strip('/').split('/')
        current = ''
        for part in parts:
            current = f"{current}/{part}".strip('/')
            breadcrumbs.append({'name': part, 'path': f'/{current}'})
    return breadcrumbs

# ===== RUTA PRINCIPAL: INDEX OF FILES =====
@app.route('/')
@app.route('/<path:subpath>')
def index_of_files(subpath=''):
    """Index of files - Listado simple de directorios y archivos"""
    try:
        # Verificar que BASE_DIR exista
        if not os.path.exists(BASE_DIR):
            os.makedirs(BASE_DIR)
        
        # Construir ruta segura
        current_path = safe_join(BASE_DIR, subpath) if subpath else BASE_DIR
        
        # Verificación de seguridad: evitar path traversal
        if not current_path or not current_path.startswith(os.path.abspath(BASE_DIR)):
            return "⚠️ Acceso denegado", 403
        
        # Verificar si existe el path
        if not os.path.exists(current_path):
            return "📁 Directorio no encontrado", 404
        
        # Si es un archivo, servirlo directamente
        if os.path.isfile(current_path):
            filename = os.path.basename(current_path)
            return jsonify({
                'error': 'Usa /download/<hash>?file=nombre para descargar archivos',
                'message': 'Este servidor requiere URLs seguras con hash'
            }), 403
        
        # ===== ES UN DIRECTORIO - Mostrar listado =====
        # Obtener breadcrumbs
        breadcrumbs = get_breadcrumbs(subpath)
        
        # Listar contenido
        items = []
        
        # Enlace al directorio padre (excepto en raíz)
        if subpath:
            parent_path = os.path.dirname(subpath.rstrip('/'))
            items.append({
                'name': '⬆️ ..',
                'is_dir': True,
                'size': '-',
                'date': '-',
                'path': f'/{parent_path}' if parent_path else '/'
            })
        
        # Listar archivos y directorios
        for item in sorted(os.listdir(current_path)):
            item_path = os.path.join(current_path, item)
            
            try:
                stat = os.stat(item_path)
                is_dir = os.path.isdir(item_path)
                
                items.append({
                    'name': item,
                    'is_dir': is_dir,
                    'size': '-' if is_dir else format_size(stat.st_size),
                    'date': format_date(stat.st_mtime),
                    'path': f'/{subpath}/{item}'.replace('//', '/') if subpath else f'/{item}'
                })
            except Exception:
                # Saltar archivos a los que no se puede acceder
                continue
        
        # ===== GENERAR HTML =====
        html = f'''
        <!DOCTYPE html>
        <html>
        <head>
            <title>Index of /{subpath}</title>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                * {{ margin: 0; padding: 0; box-sizing: border-box; }}
                body {{
                    font-family: 'SF Mono', 'Monaco', 'DejaVu Sans Mono', 'Courier New', monospace;
                    background: #1e1e1e;
                    color: #d4d4d4;
                    padding: 20px;
                    line-height: 1.6;
                }}
                .container {{
                    max-width: 1200px;
                    margin: 0 auto;
                }}
                h1 {{
                    color: #569cd6;
                    margin-bottom: 20px;
                    font-size: 24px;
                    font-weight: normal;
                }}
                .breadcrumbs {{
                    margin-bottom: 15px;
                    padding: 8px 0;
                    border-bottom: 1px solid #3a3a3a;
                }}
                .breadcrumbs a {{
                    color: #4ec9b0;
                    text-decoration: none;
                    margin-right: 5px;
                }}
                .breadcrumbs a:hover {{
                    text-decoration: underline;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th {{
                    text-align: left;
                    padding: 8px 12px;
                    background: #252526;
                    color: #9cdcfe;
                    font-weight: normal;
                    font-size: 13px;
                    border-bottom: 2px solid #3a3a3a;
                }}
                td {{
                    padding: 6px 12px;
                    border-bottom: 1px solid #2d2d2d;
                    font-size: 13px;
                }}
                tr:hover td {{
                    background: #2a2d2e;
                }}
                .dir a {{
                    color: #4ec9b0;
                    text-decoration: none;
                    display: inline-block;
                    max-width: 80%;
                }}
                .dir a:hover {{
                    text-decoration: underline;
                }}
                .file a {{
                    color: #dcdcaa;
                    text-decoration: none;
                    display: inline-block;
                    max-width: 80%;
                }}
                .file a:hover {{
                    text-decoration: underline;
                }}
                .size {{
                    color: #b5cea8;
                    width: 120px;
                    text-align: right;
                    font-family: 'SF Mono', monospace;
                }}
                .date {{
                    color: #64666d;
                    width: 160px;
                    font-family: 'SF Mono', monospace;
                }}
                .info {{
                    margin-top: 30px;
                    padding: 15px;
                    background: #252526;
                    border-left: 4px solid #569cd6;
                    font-size: 12px;
                    color: #9cdcfe;
                }}
                .info strong {{
                    color: #4ec9b0;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>Index of /{subpath if subpath else ''}</h1>
                
                <!-- Breadcrumbs -->
                <div class="breadcrumbs">
                    {' '.join([f'<a href="{crumb["path"]}">{crumb["name"]}</a> /' for crumb in breadcrumbs])}
                </div>
                
                <!-- Listado de archivos -->
                <table>
                    <tr>
                        <th>Nombre</th>
                        <th class="size">Tamaño</th>
                        <th class="date">Última modificación</th>
                    </tr>
        '''
        
        # Agregar items a la tabla
        for item in items:
            icon = '📁' if item['is_dir'] else '📄'
            css_class = 'dir' if item['is_dir'] else 'file'
            
            html += f'''
                    <tr>
                        <td class="{css_class}">
                            <a href="{item['path']}">{icon} {item['name']}</a>
                        </td>
                        <td class="size">{item['size']}</td>
                        <td class="date">{item['date']}</td>
                    </tr>
            '''
        
        html += f'''
                </table>
                
                <!-- Información -->
                <div class="info">
                    <strong>Nelson File2Link</strong> - Servidor de archivos<br>
                    Para descargar archivos, usa el bot de Telegram para obtener URLs seguras con hash.<br>
                    <strong>Base:</strong> {BASE_DIR}<br>
                    <strong>Hash expire:</strong> {HASH_EXPIRE_DAYS} días
                </div>
            </div>
        </body>
        </html>
        '''
        
        return html
        
    except Exception as e:
        logger.error(f"Error en index_of_files: {e}", exc_info=True)
        return f"Error: {str(e)}", 500

# ===== RUTAS DE DESCARGA SEGURA =====
@app.route('/download/<file_hash>')
def secure_download(file_hash):
    """Descarga segura con hash"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({"error": "Nombre de archivo requerido"}), 400
        
        # Decodificar nombre
        filename = urllib.parse.unquote(filename)
        
        # Protección contra path traversal
        if ".." in filename or filename.startswith("/"):
            return jsonify({"error": "Nombre de archivo inválido"}), 400
        
        # Verificar hash
        file_info = file_service.get_file_by_hash(file_hash)
        if not file_info:
            return jsonify({"error": "Hash inválido o expirado"}), 403
        
        if file_info['filename'] != filename:
            return jsonify({"error": "Nombre de archivo no coincide"}), 400
        
        # Servir archivo
        user_dir = file_service.get_user_directory(file_info['user_id'], file_info['file_type'])
        file_path = safe_join(user_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        # Obtener nombre original
        original_name = file_service.get_original_filename(
            file_info['user_id'], 
            filename, 
            file_info['file_type']
        )
        
        # Leer y servir archivo
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers['Content-Disposition'] = f'attachment; filename="{original_name}"'
        response.headers['Content-Length'] = str(len(file_data))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        logger.info(f"✅ Descarga: {original_name} via hash {file_hash[:8]}")
        return response
        
    except Exception as e:
        logger.error(f"Error en descarga: {e}", exc_info=True)
        return jsonify({"error": "Error interno"}), 500

@app.route('/packed/<file_hash>')
def secure_packed(file_hash):
    """Descarga de archivos empaquetados con hash"""
    try:
        filename = request.args.get('file')
        if not filename:
            return jsonify({"error": "Nombre de archivo requerido"}), 400
        
        filename = urllib.parse.unquote(filename)
        
        # Protección contra path traversal
        if ".." in filename or filename.startswith("/"):
            return jsonify({"error": "Nombre de archivo inválido"}), 400
        
        # Verificar hash
        file_info = file_service.get_file_by_hash(file_hash)
        if not file_info:
            return jsonify({"error": "Hash inválido o expirado"}), 403
        
        if file_info['filename'] != filename:
            return jsonify({"error": "Nombre de archivo no coincide"}), 400
        
        if file_info['file_type'] != 'packed':
            return jsonify({"error": "Tipo incorrecto"}), 400
        
        user_dir = file_service.get_user_directory(file_info['user_id'], "packed")
        file_path = safe_join(user_dir, filename)
        
        if not os.path.exists(file_path):
            return jsonify({"error": "Archivo no encontrado"}), 404
        
        # Obtener nombre original
        original_name = file_service.get_original_filename(
            file_info['user_id'], 
            filename, 
            "packed"
        )
        
        # Leer y servir archivo
        with open(file_path, 'rb') as f:
            file_data = f.read()
        
        response = make_response(file_data)
        response.headers['Content-Type'] = 'application/octet-stream'
        response.headers['Content-Disposition'] = f'attachment; filename="{original_name}"'
        response.headers['Content-Length'] = str(len(file_data))
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        logger.info(f"✅ Packed download: {original_name} via hash {file_hash[:8]}")
        return response
        
    except Exception as e:
        logger.error(f"Error en packed download: {e}", exc_info=True)
        return jsonify({"error": "Error interno"}), 500

# ===== ENDPOINTS DE API =====
@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        "status": "online",
        "service": "nelson-file2link",
        "timestamp": time.time()
    })

@app.route('/system-status')
def system_status():
    """Estado del sistema"""
    status = load_manager.get_status()
    
    # Calcular estadísticas de almacenamiento
    total_files = 0
    total_size = 0
    if os.path.exists(BASE_DIR):
        for root, dirs, files in os.walk(BASE_DIR):
            total_files += len(files)
            for file in files:
                file_path = os.path.join(root, file)
                if os.path.isfile(file_path):
                    total_size += os.path.getsize(file_path)
    
    return jsonify({
        "status": "online",
        "timestamp": time.time(),
        "system_load": {
            "cpu_percent": status.get('cpu_percent', 0),
            "memory_percent": status.get('memory_percent', 0),
            "active_processes": status.get('active_processes', 0)
        },
        "storage": {
            "total_files": total_files,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        },
        "security": {
            "hash_enabled": True,
            "hash_expire_days": HASH_EXPIRE_DAYS,
            "active_hashes": len(file_service.file_hashes)
        }
    })

@app.route('/api/stats')
def api_stats():
    """Estadísticas en JSON"""
    total_users = file_service.total_users_count()
    
    # Calcular estadísticas
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
    
    return jsonify({
        "users": {
            "total": total_users
        },
        "files": {
            "total_downloads": total_files_downloads,
            "total_packed": total_files_packed,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        },
        "security": {
            "active_hashes": len(file_service.file_hashes),
            "expire_days": HASH_EXPIRE_DAYS
        }
    })

# ===== MANEJADORES DE ERROR =====
@app.errorhandler(404)
def not_found(error):
    return jsonify({
        "error": "No encontrado",
        "available_endpoints": [
            "/",
            "/<path>",
            "/download/<hash>?file=",
            "/packed/<hash>?file=",
            "/health",
            "/system-status",
            "/api/stats"
        ]
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        "error": "Error interno del servidor"
    }), 500

# ===== EJECUCIÓN DIRECTA =====
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)