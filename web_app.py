"""
Servidor web Flask.

Expone únicamente los endpoints necesarios para descargar archivos.
No hay explorador de directorios público (riesgo de seguridad).
"""
from __future__ import annotations

import os
import time

from flask import Flask, Response, jsonify, send_from_directory

from config import MAX_FILE_SIZE_MB, PUBLIC_DOMAIN, STORAGE_DIR
from storage import storage
from system_monitor import monitor

app = Flask(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _force_download(directory: str, filename: str, display_name: str) -> Response:
    """Sirve un archivo forzando la descarga con el nombre original."""
    resp = send_from_directory(directory, filename)
    resp.headers["Content-Disposition"] = f'attachment; filename="{display_name}"'
    resp.headers["Content-Type"] = "application/octet-stream"
    resp.headers["X-Content-Type-Options"] = "nosniff"
    return resp


# ── Descarga de archivos ───────────────────────────────────────────────────────

@app.route("/storage/<int:user_id>/downloads/<filename>")
def download_file(user_id: int, filename: str) -> Response:
    user_dir = os.path.join(STORAGE_DIR, str(user_id), "downloads")
    file_path = os.path.join(user_dir, filename)

    if not os.path.isfile(file_path):
        return jsonify(error="Archivo no encontrado"), 404

    display = storage.get_original_name(user_id, filename, "downloads")
    return _force_download(user_dir, filename, display)


@app.route("/storage/<int:user_id>/packed/<filename>")
def download_packed(user_id: int, filename: str) -> Response:
    user_dir = os.path.join(STORAGE_DIR, str(user_id), "packed")
    file_path = os.path.join(user_dir, filename)

    if not os.path.isfile(file_path):
        return jsonify(error="Archivo no encontrado"), 404

    display = storage.get_original_name(user_id, filename, "packed")
    return _force_download(user_dir, filename, display)


# ── Health check ───────────────────────────────────────────────────────────────

@app.route("/health")
def health() -> Response:
    return jsonify(
        status="ok",
        timestamp=time.time(),
        max_file_size_mb=MAX_FILE_SIZE_MB,
    )


@app.route("/system-status")
def system_status() -> Response:
    sys = monitor.status()

    # Calcular uso de almacenamiento global
    total_files = 0
    total_bytes = 0
    if os.path.isdir(STORAGE_DIR):
        for root, _, files in os.walk(STORAGE_DIR):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.isfile(fp):
                    total_files += 1
                    total_bytes += os.path.getsize(fp)

    return jsonify(
        status="ok",
        system=sys,
        storage={
            "total_files": total_files,
            "total_size_mb": round(total_bytes / (1024 * 1024), 2),
        },
        config={"max_file_size_mb": MAX_FILE_SIZE_MB},
    )


# ── Página principal ───────────────────────────────────────────────────────────

@app.route("/")
def home() -> str:
    sys = monitor.status()
    status_badge = (
        '<span style="color:#27ae60">● En línea</span>'
        if sys["available"] else
        '<span style="color:#e74c3c">● Ocupado</span>'
    )
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>File2Link — Servidor de archivos</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',sans-serif;background:#f4f6f9;color:#333;min-height:100vh}}
  header{{background:linear-gradient(135deg,#2d6cdf,#7b2ff7);color:#fff;padding:3rem 2rem;text-align:center}}
  header h1{{font-size:2.2rem;margin-bottom:.5rem}}
  header p{{font-size:1.1rem;opacity:.9}}
  .badge{{display:inline-block;background:rgba(255,255,255,.2);border-radius:20px;
          padding:.3rem 1rem;margin-top:1rem;font-size:.95rem}}
  main{{max-width:900px;margin:2rem auto;padding:0 1.5rem}}
  .card{{background:#fff;border-radius:12px;padding:2rem;margin-bottom:1.5rem;
         box-shadow:0 2px 10px rgba(0,0,0,.07)}}
  .card h2{{margin-bottom:1rem;color:#2d6cdf}}
  .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-top:1rem}}
  .stat{{background:#f0f4ff;border-radius:8px;padding:1.2rem;text-align:center}}
  .stat .num{{font-size:1.8rem;font-weight:700;color:#2d6cdf}}
  .stat .lbl{{font-size:.85rem;color:#666;margin-top:.2rem}}
  code{{background:#eef2fb;padding:.2rem .5rem;border-radius:4px;font-size:.9rem}}
  footer{{text-align:center;padding:2rem;color:#999;font-size:.9rem}}
</style>
</head>
<body>
<header>
  <h1>🤖 File2Link</h1>
  <p>Tu asistente personal de archivos en Telegram</p>
  <div class="badge">{status_badge}</div>
</header>
<main>
  <div class="card">
    <h2>¿Cómo funciona?</h2>
    <p>Envía cualquier archivo al bot y obtendrás un enlace de descarga directo.
    Organiza, renombra, empaqueta en ZIP y comparte fácilmente.</p>
    <div class="grid">
      <div class="stat"><div class="num">📁</div><div class="lbl">Almacenamiento privado</div></div>
      <div class="stat"><div class="num">📦</div><div class="lbl">Empaquetado ZIP</div></div>
      <div class="stat"><div class="num">🔗</div><div class="lbl">Enlace directo</div></div>
      <div class="stat"><div class="num">{MAX_FILE_SIZE_MB} MB</div><div class="lbl">Límite por archivo</div></div>
    </div>
  </div>
  <div class="card">
    <h2>Estado del servidor</h2>
    <div class="grid">
      <div class="stat">
        <div class="num">{sys['cpu_percent']}%</div>
        <div class="lbl">CPU</div>
      </div>
      <div class="stat">
        <div class="num">{sys['memory_percent']}%</div>
        <div class="lbl">Memoria</div>
      </div>
      <div class="stat">
        <div class="num">{sys['active_packs']}/{sys['max_packs']}</div>
        <div class="lbl">Procesos activos</div>
      </div>
    </div>
  </div>
  <div class="card">
    <h2>Endpoints disponibles</h2>
    <p><code>GET /health</code> — Verificación de estado</p>
    <p style="margin-top:.5rem"><code>GET /system-status</code> — Estado detallado (JSON)</p>
    <p style="margin-top:.5rem">
      <code>GET /storage/&#123;user_id&#125;/downloads/&#123;archivo&#125;</code> — Descargar archivo
    </p>
    <p style="margin-top:.5rem">
      <code>GET /storage/&#123;user_id&#125;/packed/&#123;archivo&#125;</code> — Descargar ZIP
    </p>
  </div>
</main>
<footer>File2Link © {__import__('datetime').date.today().year}</footer>
</body>
</html>"""


# ── Errores ────────────────────────────────────────────────────────────────────

@app.errorhandler(404)
def not_found(_) -> tuple[Response, int]:
    return jsonify(error="Recurso no encontrado"), 404


@app.errorhandler(500)
def server_error(_) -> tuple[Response, int]:
    return jsonify(error="Error interno del servidor"), 500
