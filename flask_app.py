import os
import time
import logging
from functools import wraps
from datetime import datetime
from typing import Callable, Dict, Any, Optional

from flask import Flask, send_from_directory, jsonify, render_template_string, request

from config import config
from load_manager import load_manager
from file_service import file_service
from download_service import fast_download_service
from packing_service import packing_service

app = Flask(__name__)

# Configurar logging para Flask
logger = logging.getLogger(__name__)

# ===== DECORADORES UTILES =====
def cache_response(seconds: int = 60):
    """Decorador simple para cache de respuestas"""
    def decorator(f: Callable):
        @wraps(f)
        def wrapper(*args, **kwargs):
            # En una implementación real, aquí iría la lógica de cache
            # Por ahora solo pasamos la función
            return f(*args, **kwargs)
        return wrapper
    return decorator

def format_file_size(size: int) -> str:
    """Formatea el tamaño del archivo"""
    if size < 0:
        return "0 B"
    
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"

def get_directory_structure(startpath: str) -> list:
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

def get_system_stats() -> Dict[str, Any]:
    """Obtiene estadísticas del sistema"""
    system_status = load_manager.get_status()
    
    # Obtener información del sistema de archivos
    storage_info = {
        "base_directory": config.BASE_DIR,
        "exists": os.path.exists(config.BASE_DIR),
        "total_files": 0,
        "total_size_mb": 0
    }
    
    if os.path.exists(config.BASE_DIR):
        total_size = 0
        total_files = 0
        for root, dirs, files in os.walk(config.BASE_DIR):
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
    
    # Obtener métricas de servicios
    download_metrics = fast_download_service.get_metrics_summary()
    packing_stats = packing_service.get_packing_stats()
    
    return {
        "system_load": system_status,
        "storage": storage_info,
        "download_metrics": download_metrics,
        "packing_stats": packing_stats,
        "timestamp": time.time()
    }

# ===== RUTAS PRINCIPALES =====

@app.route('/')
@cache_response(30)
def home():
    """Página principal mejorada con información en tiempo real"""
    try:
        # Obtener estadísticas del sistema
        stats = get_system_stats()
        
        # Contar usuarios únicos (estimación simple)
        user_dirs = []
        if os.path.exists(config.BASE_DIR):
            user_dirs = [d for d in os.listdir(config.BASE_DIR) 
                        if os.path.isdir(os.path.join(config.BASE_DIR, d))]
        
        # Información dinámica para la página
        system_info = {
            'total_users': len(user_dirs),
            'total_files': stats['storage']['total_files'],
            'total_size': format_file_size(stats['storage']['total_size_mb'] * 1024 * 1024),
            'system_load': stats['system_load']['cpu_percent'],
            'active_processes': stats['system_load']['active_processes'],
            'can_accept_work': stats['system_load']['can_accept_work'],
            'download_stats': stats['download_metrics'],
            'packing_stats': stats['packing_stats']
        }
        
        html_template = '''
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
                
                .status-warning {{
                    background: #e67e22;
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
                
                .system-status {{
                    background: rgba(255, 255, 255, 0.95);
                    padding: 20px;
                    border-radius: 10px;
                    margin: 20px 0;
                    box-shadow: 0 3px 10px rgba(0, 0, 0, 0.1);
                }}
                
                .status-item {{
                    display: flex;
                    justify-content: space-between;
                    margin-bottom: 10px;
                    padding-bottom: 10px;
                    border-bottom: 1px solid #eee;
                }}
                
                .status-label {{
                    font-weight: bold;
                    color: #2c3e50;
                }}
                
                .status-value {{
                    color: #7f8c8d;
                }}
                
                .status-good {{
                    color: #27ae60;
                }}
                
                .status-warning {{
                    color: #e67e22;
                }}
                
                .status-danger {{
                    color: #e74c3c;
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
                    <h1>🤖 Nelson File2Link - Sistema Profesional</h1>
                    <div class="status-badge {{ 'status-warning' if not system_info.can_accept_work else '' }}">
                        {{ '⚠️ CARGADO - ESPERA' if not system_info.can_accept_work else '✅ ACTIVO Y FUNCIONANDO' }}
                    </div>
                    <p>Servidor profesional de archivos via Telegram</p>
                    <p><strong>📏 Tamaño máximo por archivo: {max_file_size} MB</strong></p>
                    <p><strong>👥 Usuarios activos: {total_users}</strong></p>
                    <p><strong>📁 Archivos totales: {total_files}</strong></p>
                    <p><strong>💾 Almacenamiento usado: {total_size}</strong></p>
                    
                    <a href="https://t.me/nelson_file2link_bot" class="btn btn-telegram">🚀 Usar el Bot en Telegram</a>
                    <a href="/system-status" class="btn">📊 Estado del Sistema</a>
                    <a href="/health" class="btn">❤️ Health Check</a>
                    <a href="/files" class="btn">📁 Explorador de Archivos</a>
                </div>

                <div class="system-status">
                    <h3>📈 Estado del Sistema en Tiempo Real</h3>
                    <div class="status-item">
                        <span class="status-label">🖥️ Uso de CPU:</span>
                        <span class="status-value {{ 'status-warning' if system_info.system_load > 70 else 'status-good' }}">
                            {system_info.system_load:.1f}%
                        </span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">🔄 Procesos Activos:</span>
                        <span class="status-value">{{ system_info.active_processes }}/1</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">📥 Descargas Totales:</span>
                        <span class="status-value">{{ system_info.download_stats.total_downloads if system_info.download_stats else 0 }}</span>
                    </div>
                    <div class="status-item">
                        <span class="status-label">📦 Empaquetados:</span>
                        <span class="status-value">{{ system_info.packing_stats.total_packs if system_info.packing_stats else 0 }}</span>
                    </div>
                </div>

                <div class="stats">
                    <div class="stat-card">
                        <div class="stat-number">{max_file_size} MB</div>
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
                        <p>Sube y descarga archivos hasta {max_file_size}MB con enlaces directos</p>
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
                    <div class="code">Tamaño máximo por archivo: {max_file_size} MB
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
/files - Explorador de archivos del servidor</div>
                </div>

                <div class="info-section" style="text-align: center; background: #2c3e50; color: white;">
                    <h3 style="color: white;">🤖 Nelson File2Link - Sistema Profesional</h3>
                    <p>Versión 2.1.0 - Optimizado para Render.com</p>
                    <p>© {current_year} - Todos los derechos reservados</p>
                </div>
            </div>
        </body>
        </html>
        '''
        
        return render_template_string(
            html_template,
            max_file_size=config.MAX_FILE_SIZE_MB,
            total_users=system_info['total_users'],
            total_files=system_info['total_files'],
            total_size=system_info['total_size'],
            system_info=system_info,
            current_year=datetime.now().year
        )
        
    except Exception as e:
        logger.error(f"Error en página principal: {e}")
        return f"""
        <!DOCTYPE html>
        <html>
        <head><title>Error</title></head>
        <body>
            <h1>⚠️ Error en el servidor</h1>
            <p>El servidor encontró un error inesperado.</p>
            <p>Detalles: {str(e)}</p>
            <a href="/">Volver al inicio</a>
        </body>
        </html>
        """, 500

@app.route('/health')
def health():
    """Health check avanzado"""
    try:
        # Obtener métricas del sistema
        stats = get_system_stats()
        
        # Verificar servicios críticos
        services_ok = {
            'telegram_bot': True,  # Asumir OK si el endpoint responde
            'web_server': True,
            'file_service': os.path.exists("file_metadata.json"),
            'storage': os.path.exists(config.BASE_DIR),
            'writable': os.access(config.BASE_DIR, os.W_OK)
        }
        
        # Verificar métricas del sistema
        system_ok = (
            stats['system_load']['cpu_percent'] < 90 and 
            stats['system_load']['memory_percent'] < 90 and
            stats['system_load']['active_processes'] <= stats['system_load']['max_processes']
        )
        
        all_services_ok = all(services_ok.values())
        
        health_status = {
            "status": "healthy" if (all_services_ok and system_ok) else "degraded",
            "timestamp": time.time(),
            "service": "nelson-file2link-pro",
            "version": "2.1.0",
            "system": {
                "cpu_percent": stats['system_load']['cpu_percent'],
                "memory_percent": stats['system_load']['memory_percent'],
                "active_processes": stats['system_load']['active_processes'],
                "can_accept_work": stats['system_load']['can_accept_work'],
                "is_overloaded": stats['system_load']['is_overloaded']
            },
            "services": services_ok,
            "storage": stats['storage'],
            "metrics": {
                "downloads": stats['download_metrics'],
                "packing": stats['packing_stats']
            },
            "configuration": {
                "max_file_size_mb": config.MAX_FILE_SIZE_MB,
                "max_concurrent_processes": config.MAX_CONCURRENT_PROCESSES,
                "render_domain": config.RENDER_DOMAIN,
                "base_directory": config.BASE_DIR
            }
        }
        
        return jsonify(health_status), 200 if health_status["status"] == "healthy" else 503
        
    except Exception as e:
        logger.error(f"Error en health check: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": time.time()
        }), 500

@app.route('/system-status')
@cache_response(10)
def system_status():
    """Endpoint para verificar el estado detallado del sistema"""
    try:
        stats = get_system_stats()
        
        response = {
            "status": "online",
            "service": "nelson-file2link-optimized",
            "timestamp": time.time(),
            "uptime": time.time() - stats['timestamp'],  # Tiempo desde que se obtuvieron las métricas
            "system_load": stats['system_load'],
            "storage": stats['storage'],
            "service_metrics": {
                "downloads": stats['download_metrics'],
                "packing": stats['packing_stats']
            },
            "configuration": {
                "max_file_size_mb": config.MAX_FILE_SIZE_MB,
                "max_concurrent_processes": config.MAX_CONCURRENT_PROCESSES,
                "cpu_usage_limit": config.CPU_USAGE_LIMIT,
                "memory_usage_percent": stats['system_load'].get('memory_percent', 0),
                "optimized_for": "low-cpu-environment",
                "base_directory": config.BASE_DIR,
                "render_domain": config.RENDER_DOMAIN
            },
            "endpoints": {
                "web_interface": "/",
                "health_check": "/health",
                "system_status": "/system-status",
                "file_download": "/storage/<user_id>/<folder>/<filename>",
                "file_browser": "/files",
                "api_docs": "https://github.com/tuusuario/nelson-file2link"
            },
            "recommendations": []
        }
        
        # Agregar recomendaciones basadas en métricas
        if stats['system_load']['cpu_percent'] > 80:
            response["recommendations"].append("CPU alta. Considera reducir la carga.")
        
        if stats['system_load']['memory_percent'] > 85:
            response["recommendations"].append("Memoria alta. Podría afectar el rendimiento.")
        
        if not stats['system_load']['can_accept_work']:
            response["recommendations"].append("Sistema sobrecargado. No acepta nuevo trabajo temporalmente.")
        
        if stats['storage']['total_size_mb'] > 1000:  # Más de 1GB
            response["recommendations"].append("Almacenamiento alto. Considera limpiar archivos antiguos.")
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error en system-status: {e}")
        return jsonify({
            "status": "error",
            "message": str(e),
            "timestamp": time.time()
        }), 500

@app.route('/files')
def file_browser():
    """Navegador de archivos del servidor"""
    try:
        directory = config.BASE_DIR
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
        logger.error(f"Error en file browser: {e}")
        return f"Error: {str(e)}", 500

@app.route('/storage/<path:path>')
def serve_static(path):
    """Sirve archivos estáticos de forma genérica forzando la descarga"""
    try:
        # Verificar que el path esté dentro del directorio base
        safe_path = os.path.normpath(path)
        full_path = os.path.join(config.BASE_DIR, safe_path)
        
        # Verificar que no haya traversal directory
        if not os.path.commonprefix([os.path.realpath(full_path), os.path.realpath(config.BASE_DIR)]) == os.path.realpath(config.BASE_DIR):
            return jsonify({"error": "Acceso no permitido"}), 403
        
        # Extraer el nombre del archivo del path
        filename = os.path.basename(path)
        
        # Verificar que el archivo exista
        if not os.path.exists(full_path):
            return jsonify({
                "error": "Archivo no encontrado",
                "path": path
            }), 404
        
        # Servir el archivo
        response = send_from_directory(config.BASE_DIR, safe_path)
        
        # Configurar headers para forzar descarga
        response.headers["Content-Disposition"] = f"attachment; filename=\"{filename}\""
        response.headers["Content-Type"] = "application/octet-stream"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        
        return response
    except Exception as e:
        logger.error(f"Error sirviendo archivo {path}: {e}")
        return jsonify({
            "error": "Archivo no encontrado",
            "path": path,
            "message": str(e)
        }), 404

@app.route('/storage/<user_id>/downloads/<filename>')
def serve_download(user_id, filename):
    """Sirve archivos de descarga forzando la descarga"""
    try:
        user_download_dir = os.path.join(config.BASE_DIR, user_id, "downloads")
        
        # Verificar que el directorio exista
        if not os.path.exists(user_download_dir):
            return jsonify({
                "error": "Usuario no encontrado",
                "user_id": user_id
            }), 404
        
        # Verificar que el archivo exista
        file_path = os.path.join(user_download_dir, filename)
        if not os.path.exists(file_path):
            return jsonify({
                "error": "Archivo no encontrado",
                "filename": filename,
                "user_id": user_id
            }), 404
        
        # Obtener el nombre original del archivo desde la metadata
        original_filename = file_service.get_original_filename(user_id, filename, "downloads")
        
        # Servir el archivo forzando la descarga
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
        logger.error(f"Error sirviendo archivo de descarga: {e}")
        return jsonify({
            "error": "Error interno del servidor",
            "message": str(e)
        }), 500

@app.route('/storage/<user_id>/packed/<filename>')
def serve_packed(user_id, filename):
    """Sirve archivos empaquetados forzando la descarga"""
    try:
        user_packed_dir = os.path.join(config.BASE_DIR, user_id, "packed")
        
        # Verificar que el directorio exista
        if not os.path.exists(user_packed_dir):
            return jsonify({
                "error": "Usuario no encontrado o sin archivos empaquetados",
                "user_id": user_id
            }), 404
        
        # Verificar que el archivo exista
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
        logger.error(f"Error sirviendo archivo empaquetado: {e}")
        return jsonify({
            "error": "Error interno del servidor",
            "message": str(e)
        }), 500

# ===== MANEJO DE ERRORES =====

@app.errorhandler(404)
def not_found(error):
    """Manejo de errores 404"""
    return jsonify({
        "error": "Endpoint no encontrado",
        "message": "La ruta solicitada no existe",
        "timestamp": time.time(),
        "available_endpoints": [
            "/",
            "/health", 
            "/system-status",
            "/files",
            "/storage/<user_id>/downloads/<filename>",
            "/storage/<user_id>/packed/<filename>"
        ]
    }), 404

@app.errorhandler(403)
def forbidden(error):
    """Manejo de errores 403"""
    return jsonify({
        "error": "Acceso prohibido",
        "message": "No tienes permiso para acceder a este recurso",
        "timestamp": time.time()
    }), 403

@app.errorhandler(500)
def internal_error(error):
    """Manejo de errores 500"""
    logger.error(f"Error interno del servidor: {error}")
    return jsonify({
        "error": "Error interno del servidor",
        "message": "Ha ocurrido un error inesperado",
        "timestamp": time.time(),
        "support": "Contacta a soporte si el problema persiste"
    }), 500

@app.errorhandler(413)
def too_large(error):
    """Manejo de errores 413 (Payload Too Large)"""
    return jsonify({
        "error": "Archivo demasiado grande",
        "message": f"El tamaño máximo permitido es {config.MAX_FILE_SIZE_MB} MB",
        "timestamp": time.time()
    }), 413

# ===== ENDPOINTS ADICIONALES UTILES =====

@app.route('/api/stats')
@cache_response(30)
def api_stats():
    """Endpoint API para estadísticas"""
    try:
        stats = get_system_stats()
        return jsonify({
            "success": True,
            "data": stats,
            "timestamp": time.time()
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }), 500

@app.route('/robots.txt')
def robots():
    """Archivo robots.txt para crawlers"""
    return """User-agent: *
Disallow: /storage/
Disallow: /api/
Allow: /
""", 200, {'Content-Type': 'text/plain'}

@app.route('/favicon.ico')
def favicon():
    """Favicon por defecto"""
    return '', 204  # No content

# ===== INICIO DEL SERVIDOR (solo para desarrollo) =====
if __name__ == '__main__':
    # Solo para desarrollo local
    logger.info(f"Iniciando servidor Flask en modo desarrollo...")
    app.run(
        host='0.0.0.0', 
        port=config.PORT, 
        debug=False,  # Siempre False en producción
        threaded=True
    )