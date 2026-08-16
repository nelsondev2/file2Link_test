import os
import time
from flask import Flask, send_from_directory, jsonify, render_template_string

from config import BASE_DIR, RENDER_DOMAIN, MAX_FILE_SIZE_MB
from load_manager import load_manager
from file_service import file_service

app = Flask(__name__)


def _format_size(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"


def _directory_structure(startpath):
    structure = []
    try:
        for root, dirs, files in os.walk(startpath):
            level = root.replace(startpath, "").count(os.sep)
            indent = "  " * level
            structure.append(f"{indent}[D] {os.path.basename(root)}/")
            subindent = "  " * (level + 1)
            for f in files:
                size = os.path.getsize(os.path.join(root, f))
                structure.append(f"{subindent}[F] {f} ({_format_size(size)})")
    except Exception as e:
        structure.append(f"Error: {str(e)}")
    return structure


@app.route("/")
def home():
    return f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>File2Link</title>
        <style>
            * {{ margin: 0; padding: 0; box-sizing: border-box; }}
            body {{
                font-family: 'Segoe UI', system-ui, sans-serif;
                background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                min-height: 100vh;
                color: #e0e0e0;
            }}
            .container {{ max-width: 900px; margin: 0 auto; padding: 30px 20px; }}
            .header {{
                text-align: center; margin-bottom: 40px; padding: 40px 20px;
                background: rgba(255,255,255,0.05); border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.1);
            }}
            .header h1 {{ font-size: 2.2rem; color: #e94560; margin-bottom: 8px; }}
            .header p {{ color: #a0a0a0; margin-bottom: 16px; }}
            .badge {{
                display: inline-block; background: #27ae60; color: #fff;
                padding: 6px 18px; border-radius: 20px; font-size: 0.85rem; font-weight: 600;
            }}
            .stats {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
                gap: 16px; margin: 30px 0;
            }}
            .stat {{
                background: rgba(255,255,255,0.05); padding: 20px; border-radius: 12px;
                text-align: center; border: 1px solid rgba(255,255,255,0.08);
            }}
            .stat .num {{ font-size: 1.8rem; font-weight: 700; color: #e94560; }}
            .stat .lbl {{ font-size: 0.85rem; color: #888; margin-top: 4px; }}
            .features {{
                display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
                gap: 16px; margin: 30px 0;
            }}
            .feat {{
                background: rgba(255,255,255,0.05); padding: 24px; border-radius: 12px;
                border: 1px solid rgba(255,255,255,0.08);
            }}
            .feat h4 {{ color: #e94560; margin-bottom: 8px; }}
            .feat p {{ color: #a0a0a0; font-size: 0.9rem; line-height: 1.5; }}
            .info {{
                background: rgba(255,255,255,0.05); padding: 24px; border-radius: 12px;
                margin: 20px 0; border: 1px solid rgba(255,255,255,0.08);
            }}
            .info h3 {{ color: #e94560; margin-bottom: 12px; }}
            .info p {{ color: #a0a0a0; line-height: 1.7; margin-bottom: 8px; }}
            .code {{
                background: #0a0a0a; color: #e94560; padding: 14px; border-radius: 8px;
                font-family: 'Courier New', monospace; font-size: 0.85rem;
                margin: 10px 0; overflow-x: auto;
            }}
            .footer {{
                text-align: center; padding: 30px; color: #555;
                border-top: 1px solid rgba(255,255,255,0.05); margin-top: 40px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>File2Link</h1>
                <div class="badge">ACTIVO</div>
                <p>Servidor de archivos via Telegram</p>
                <p>Limite por archivo: {MAX_FILE_SIZE_MB} MB</p>
            </div>

            <div class="stats">
                <div class="stat"><div class="num">{MAX_FILE_SIZE_MB} MB</div><div class="lbl">Limite por archivo</div></div>
                <div class="stat"><div class="num">ZIP</div><div class="lbl">Empaquetado</div></div>
                <div class="stat"><div class="num">Cola</div><div class="lbl">Procesamiento secuencial</div></div>
            </div>

            <div class="features">
                <div class="feat">
                    <h4>Almacenamiento</h4>
                    <p>Archivos guardados con enlaces permanentes de descarga directa.</p>
                </div>
                <div class="feat">
                    <h4>Empaquetado</h4>
                    <p>Comprime tus archivos en ZIP, con opcion de dividir en partes.</p>
                </div>
                <div class="feat">
                    <h4>Cola inteligente</h4>
                    <p>Procesamiento automatico de multiples archivos con progreso en tiempo real.</p>
                </div>
                <div class="feat">
                    <h4>Gestion completa</h4>
                    <p>Renombra, elimina y organiza tus archivos desde Telegram.</p>
                </div>
            </div>

            <div class="info">
                <h3>Como funciona</h3>
                <p>1. <strong>Envia un archivo</strong> al bot de Telegram</p>
                <p>2. <strong>El archivo se guarda</strong> en tu carpeta personal</p>
                <p>3. <strong>Recibes un enlace</strong> de descarga directa</p>
                <p>4. <strong>Gestiona tus archivos</strong> con comandos simples</p>
            </div>

            <div class="info">
                <h3>Endpoints</h3>
                <div class="code">/health              — Verificacion de estado
/system-status       — Estado detallado
/files               — Explorador de archivos
/storage/&lt;uid&gt;/downloads/&lt;file&gt; — Descargar
/storage/&lt;uid&gt;/packed/&lt;file&gt;    — Descargar empaquetado</div>
            </div>

            <div class="footer">
                <p>File2Link &mdash; Sistema de gestion de archivos via Telegram</p>
            </div>
        </div>
    </body>
    </html>
    """


@app.route("/health")
def health():
    return jsonify({
        "status": "online",
        "service": "file2link",
        "timestamp": time.time(),
        "version": "2.1.0",
        "max_file_size_mb": MAX_FILE_SIZE_MB,
    })


@app.route("/system-status")
def system_status():
    status = load_manager.get_status()
    storage = {"base_directory": BASE_DIR, "exists": os.path.exists(BASE_DIR), "total_files": 0, "total_size_mb": 0}

    if os.path.exists(BASE_DIR):
        total_size, total_files = 0, 0
        for root, dirs, files in os.walk(BASE_DIR):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
                    total_files += 1
        storage.update({"total_files": total_files, "total_size_mb": round(total_size / (1024 * 1024), 2)})

    return jsonify({
        "status": "online",
        "service": "file2link",
        "timestamp": time.time(),
        "system_load": status,
        "storage": storage,
        "configuration": {
            "max_file_size_mb": MAX_FILE_SIZE_MB,
            "max_concurrent_processes": load_manager.max_processes,
        },
    })


@app.route("/files")
def file_browser():
    try:
        directory = BASE_DIR
        if not os.path.exists(directory):
            return "Directory not found", 404

        structure = _directory_structure(directory)
        total_files, total_size = 0, 0
        for root, dirs, files in os.walk(directory):
            total_files += len(files)
            for f in files:
                total_size += os.path.getsize(os.path.join(root, f))

        return render_template_string(
            '<pre>{{ content }}</pre>',
            content="\n".join(structure) + f"\n\nTotal: {total_files} archivos, {_format_size(total_size)}",
        )
    except Exception as e:
        return f"Error: {str(e)}", 500


@app.route("/storage/<path:path>")
def serve_static(path):
    try:
        filename = os.path.basename(path)
        response = send_from_directory(BASE_DIR, path)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except Exception as e:
        return jsonify({"error": "Archivo no encontrado", "path": path}), 404


@app.route("/storage/<user_id>/downloads/<filename>")
def serve_download(user_id, filename):
    try:
        user_dir = os.path.join(BASE_DIR, user_id, "downloads")
        if not os.path.exists(user_dir):
            return jsonify({"error": "Usuario no encontrado"}), 404
        if not os.path.exists(os.path.join(user_dir, filename)):
            return jsonify({"error": "Archivo no encontrado"}), 404

        original = file_service.get_original_filename(user_id, filename, "downloads")
        response = send_from_directory(user_dir, filename)
        response.headers["Content-Disposition"] = f'attachment; filename="{original}"'
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except Exception as e:
        return jsonify({"error": "Error interno"}), 500


@app.route("/storage/<user_id>/packed/<filename>")
def serve_packed(user_id, filename):
    try:
        user_dir = os.path.join(BASE_DIR, user_id, "packed")
        if not os.path.exists(user_dir):
            return jsonify({"error": "Sin archivos empaquetados"}), 404
        if not os.path.exists(os.path.join(user_dir, filename)):
            return jsonify({"error": "Archivo no encontrado"}), 404

        original = file_service.get_original_filename(user_id, filename, "packed")
        response = send_from_directory(user_dir, filename)
        response.headers["Content-Disposition"] = f'attachment; filename="{original}"'
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response
    except Exception as e:
        return jsonify({"error": "Error interno"}), 500


@app.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Endpoint no encontrado"}), 404


@app.errorhandler(500)
def internal_error(error):
    return jsonify({"error": "Error interno del servidor"}), 500
