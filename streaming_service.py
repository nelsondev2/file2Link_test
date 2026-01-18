import os
import mimetypes
import logging
from flask import Response, send_file, jsonify
from config import BASE_DIR
from file_service import file_service

logger = logging.getLogger(__name__)

class StreamingService:
    def __init__(self):
        self.chunk_size = 1024 * 1024  # 1MB chunks
    
    def get_mime_type(self, filename):
        """Obtiene el tipo MIME del archivo"""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'
    
    def generate_stream(self, filepath, start=0, end=None):
        """Genera stream de video/audio para HTTP range requests"""
        file_size = os.path.getsize(filepath)
        
        if end is None:
            end = file_size - 1
        
        length = end - start + 1
        
        def generate():
            with open(filepath, 'rb') as f:
                f.seek(start)
                remaining = length
                
                while remaining > 0:
                    chunk_size = min(self.chunk_size, remaining)
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        
        return generate, length, start, end, file_size
    
    def serve_file_with_range(self, user_id, filename, request_headers):
        """Sirve archivo con soporte para range requests (streaming)"""
        try:
            user_dir = file_service.get_user_directory(user_id, "downloads")
            file_path = os.path.join(user_dir, filename)
            
            if not os.path.exists(file_path):
                return None
            
            file_size = os.path.getsize(file_path)
            mime_type = self.get_mime_type(filename)
            
            range_header = request_headers.get('Range', None)
            
            if not range_header:
                # Descarga completa
                return send_file(
                    file_path,
                    as_attachment=True,
                    download_name=file_service.get_original_filename(user_id, filename, "downloads"),
                    mimetype=mime_type
                )
            
            # Parse range header
            byte1, byte2 = 0, None
            range_ = range_header.replace('bytes=', '').split('-')
            
            if len(range_) == 1:
                byte1 = int(range_[0])
            elif len(range_) == 2:
                byte1 = int(range_[0]) if range_[0] else 0
                byte2 = int(range_[1]) if range_[1] else file_size - 1
            
            if byte2 is None:
                byte2 = file_size - 1
            
            if byte1 >= file_size:
                return jsonify({'error': 'Range not satisfiable'}), 416
            
            byte2 = min(byte2, file_size - 1)
            length = byte2 - byte1 + 1
            
            generate, _, _, _, _ = self.generate_stream(file_path, byte1, byte2)
            
            response = Response(
                generate(),
                status=206,
                mimetype=mime_type,
                direct_passthrough=True
            )
            
            response.headers.add('Content-Range', f'bytes {byte1}-{byte2}/{file_size}')
            response.headers.add('Accept-Ranges', 'bytes')
            response.headers.add('Content-Length', str(length))
            response.headers.add('Cache-Control', 'no-cache')
            
            return response
            
        except Exception as e:
            logger.error(f"Error en streaming: {e}")
            return None
    
    def create_stream_page(self, user_id, filename, file_hash=None):
        """Crea una página HTML para streaming"""
        user_dir = file_service.get_user_directory(user_id, "downloads")
        file_path = os.path.join(user_dir, filename)
        
        if not os.path.exists(file_path):
            return None
        
        mime_type = self.get_mime_type(filename)
        original_name = file_service.get_original_filename(user_id, filename, "downloads")
        
        if mime_type.startswith('video/'):
            return self._create_video_player(user_id, filename, original_name, mime_type)
        elif mime_type.startswith('audio/'):
            return self._create_audio_player(user_id, filename, original_name, mime_type)
        else:
            return self._create_download_page(user_id, filename, original_name)
    
    def _create_video_player(self, user_id, filename, original_name, mime_type):
        """Crea reproductor de video HTML5"""
        stream_url = f"/stream/{user_id}/{filename}"
        download_url = f"/storage/{user_id}/downloads/{filename}"
        
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{original_name} - Streaming</title>
    <link href="https://vjs.zencdn.net/7.20.3/video-js.css" rel="stylesheet" />
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            color: white;
            font-family: Arial, sans-serif;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        .player-container {{
            background: #2a2a2a;
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
        }}
        .info {{
            background: #2a2a2a;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 10px;
        }}
        .btn {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin-right: 10px;
            margin-bottom: 10px;
        }}
        .btn:hover {{
            background: #2980b9;
        }}
        .btn-download {{
            background: #27ae60;
        }}
        .btn-download:hover {{
            background: #219653;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎬 {original_name}</h1>
        
        <div class="player-container">
            <video
                id="my-video"
                class="video-js vjs-big-play-centered"
                controls
                preload="auto"
                width="100%"
                height="auto"
                data-setup='{{}}'
            >
                <source src="{stream_url}" type="{mime_type}" />
                <p class="vjs-no-js">
                    Para ver este video por favor habilita JavaScript
                </p>
            </video>
        </div>
        
        <div class="info">
            <h3>📁 Información del archivo:</h3>
            <p><strong>Nombre:</strong> {original_name}</p>
            <p><strong>Tipo:</strong> {mime_type}</p>
            <p><strong>URL de streaming:</strong> <code>{stream_url}</code></p>
        </div>
        
        <div>
            <a href="{download_url}" class="btn btn-download" download>⬇️ Descargar Archivo</a>
            <a href="/" class="btn">🏠 Volver al inicio</a>
            <button onclick="copyStreamUrl()" class="btn">📋 Copiar URL de Streaming</button>
        </div>
    </div>
    
    <script src="https://vjs.zencdn.net/7.20.3/video.min.js"></script>
    <script>
        function copyStreamUrl() {{
            navigator.clipboard.writeText("{stream_url}")
                .then(() => alert("URL copiada al portapapeles"))
                .catch(err => console.error("Error copiando URL: ", err));
        }}
        
        // Configuración del reproductor
        const player = videojs('my-video');
    </script>
</body>
</html>"""
        return html
    
    def _create_audio_player(self, user_id, filename, original_name, mime_type):
        """Crea reproductor de audio HTML5"""
        stream_url = f"/stream/{user_id}/{filename}"
        download_url = f"/storage/{user_id}/downloads/{filename}"
        
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{original_name} - Audio Streaming</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: #1a1a1a;
            color: white;
            font-family: Arial, sans-serif;
        }}
        .container {{
            max-width: 800px;
            margin: 0 auto;
            text-align: center;
        }}
        .player-container {{
            background: #2a2a2a;
            border-radius: 10px;
            padding: 30px;
            margin: 20px 0;
        }}
        audio {{
            width: 100%;
            margin: 20px 0;
        }}
        .btn {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin: 10px;
        }}
        .btn-download {{
            background: #27ae60;
        }}
        .info {{
            background: #2a2a2a;
            padding: 15px;
            border-radius: 5px;
            margin: 20px 0;
            text-align: left;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎵 {original_name}</h1>
        
        <div class="player-container">
            <audio controls autoplay>
                <source src="{stream_url}" type="{mime_type}">
                Tu navegador no soporta el elemento de audio.
            </audio>
        </div>
        
        <div class="info">
            <h3>📁 Información:</h3>
            <p><strong>Nombre:</strong> {original_name}</p>
            <p><strong>Tipo:</strong> {mime_type}</p>
            <p><strong>URL de streaming:</strong> <code>{stream_url}</code></p>
        </div>
        
        <div>
            <a href="{download_url}" class="btn btn-download" download>⬇️ Descargar Audio</a>
            <a href="/" class="btn">🏠 Volver al inicio</a>
            <button onclick="copyStreamUrl()" class="btn">📋 Copiar URL</button>
        </div>
    </div>
    
    <script>
        function copyStreamUrl() {{
            navigator.clipboard.writeText("{stream_url}")
                .then(() => alert("URL copiada al portapapeles"))
                .catch(err => console.error("Error: ", err));
        }}
    </script>
</body>
</html>"""
        return html
    
    def _create_download_page(self, user_id, filename, original_name):
        """Crea página de descarga para archivos no multimedia"""
        download_url = f"/storage/{user_id}/downloads/{filename}"
        
        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{original_name} - Descarga</title>
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            color: white;
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .container {{
            background: rgba(255, 255, 255, 0.95);
            padding: 40px;
            border-radius: 15px;
            text-align: center;
            color: #333;
            max-width: 500px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
        }}
        h1 {{
            color: #2c3e50;
            margin-bottom: 20px;
        }}
        .file-info {{
            background: #f8f9fa;
            padding: 15px;
            border-radius: 8px;
            margin: 20px 0;
            text-align: left;
        }}
        .btn {{
            display: inline-block;
            background: #3498db;
            color: white;
            padding: 12px 30px;
            text-decoration: none;
            border-radius: 25px;
            margin: 10px;
            font-size: 16px;
            transition: all 0.3s;
        }}
        .btn:hover {{
            background: #2980b9;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }}
        .btn-download {{
            background: #27ae60;
        }}
        .btn-download:hover {{
            background: #219653;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📁 {original_name}</h1>
        
        <div class="file-info">
            <p><strong>📄 Archivo listo para descargar</strong></p>
            <p>Este tipo de archivo no es compatible con reproducción en el navegador.</p>
        </div>
        
        <a href="{download_url}" class="btn btn-download" download>
            ⬇️ Descargar Archivo
        </a>
        
        <a href="/" class="btn">🏠 Volver al inicio</a>
        
        <p style="margin-top: 20px; color: #666; font-size: 14px;">
            <strong>Nota:</strong> Haz clic derecho en el botón de descarga y selecciona 
            "Guardar enlace como..." para guardar el archivo.
        </p>
    </div>
</body>
</html>"""
        return html

streaming_service = StreamingService()