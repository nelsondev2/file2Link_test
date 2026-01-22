#!/usr/bin/env python3
# coding: utf-8
"""
Gestor de Descargas para Termux-X11
Versión móvil optimizada - Single Module
Autor: AI Assistant
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import json
import os
import time
import threading
import queue
import requests
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, unquote
import ssl
import concurrent.futures
import sys
import traceback

# ============================================================================
# CONFIGURACIONES GLOBALES
# ============================================================================
MAX_DESCARGAS_SIMULTANEAS = 3  # Reducido para móvil
MAX_ANALISIS_SIMULTANEOS = 2
MEMORY_CHECK_INTERVAL = 30
CACHE_SIZE_LIMIT = 100  # Reducido para móvil

# Contexto SSL
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# Colores y emojis para móvil
COLORES = {
    "fondo": "#121212",
    "fondo_tarjeta": "#1e1e1e",
    "texto": "#e0e0e0",
    "texto_secundario": "#aaaaaa",
    "acento": "#00bcd4",  # Cyan brillante
    "exito": "#4caf50",   # Verde
    "error": "#f44336",   # Rojo
    "advertencia": "#ff9800",  # Naranja
    "pausa": "#ffeb3b",   # Amarillo
    "progreso_bg": "#2d2d2d",
    "progreso_fg": "#00bcd4",
    "boton_bg": "#37474f",
    "boton_fg": "#ffffff",
    "hover_bg": "#455a64",
    "borde": "#333333"
}

EMOJIS = {
    "iniciar": "🚀",
    "pausar": "⏸️",
    "reanudar": "▶️",
    "cancelar": "❌",
    "completado": "✅",
    "error": "❌",
    "analizando": "🔍",
    "descargando": "⬇️",
    "limpiar": "🧹",
    "config": "⚙️",
    "carpeta": "📁",
    "archivo": "📄",
    "url": "🔗",
    "pegar": "📋",
    "tema": "🎨",
    "estadisticas": "📊",
    "logs": "📝",
    "reloj": "⏱️",
    "velocidad": "⚡",
    "tamano": "💾",
    "audio": "🎵",
    "video": "🎬",
    "imagen": "🖼️",
    "documento": "📝",
    "comprimido": "📦",
    "codigo": "🐍",
    "web": "🌐"
}

# ============================================================================
# CLASE DESCARGA
# ============================================================================
class Descarga:
    """Clase para representar una descarga individual"""
    
    def __init__(self, url, descarga_id=None, datos_persistencia=None):
        self.url = url
        self.id = descarga_id or f"{hash(url)}_{int(time.time())}"
        
        # Datos básicos
        self.nombre_archivo = ""
        self.ruta_completa = ""
        self.ruta_parcial = ""
        self.bytes_descargados = 0
        self.total_bytes = None
        self.pausada = False
        self.cancelada = False
        self.completada = False
        self.analizando = False
        
        # Estadísticas
        self.inicio_tiempo = time.time()
        self.ultima_actualizacion = time.time()
        self.velocidad_promedio = 0
        self.tiempo_restante = None
        
        # Hilo
        self.hilo = None
        
        # Inicializar desde persistencia si existe
        if datos_persistencia:
            self._inicializar_desde_persistencia(datos_persistencia)
            
    def _inicializar_desde_persistencia(self, datos):
        """Inicializa desde datos de persistencia"""
        self.nombre_archivo = datos.get('nombre_archivo', '')
        self.ruta_completa = datos.get('ruta_completa', '')
        self.ruta_parcial = datos.get('ruta_parcial', '')
        self.bytes_descargados = datos.get('bytes_descargados', 0)
        self.total_bytes = datos.get('total_bytes')
        self.pausada = datos.get('pausada', False)
        self.completada = datos.get('completada', False)
        self.cancelada = datos.get('cancelada', False)
        
    def obtener_nombre_archivo(self):
        """Extrae el nombre de archivo de la URL"""
        if self.nombre_archivo:
            return self.nombre_archivo
            
        parsed = urlparse(self.url)
        path = parsed.path
        nombre = unquote(os.path.basename(path))
        
        if not nombre or len(nombre) < 3 or '.' not in nombre:
            query = parsed.query
            for param in query.split('&'):
                if param.startswith('filename='):
                    nombre = unquote(param.split('=')[1])
                    break
            
            if not nombre or len(nombre) < 3:
                nombre = f"descarga_{int(time.time()) % 10000}.bin"
        
        nombre = nombre.replace('/', '_').replace('\\', '_').replace(':', '_')[:50]  # Más corto para móvil
        self.nombre_archivo = nombre
        return nombre
        
    def obtener_icono(self):
        """Devuelve un emoji según la extensión del archivo"""
        extension = self.nombre_archivo.lower().split('.')[-1] if '.' in self.nombre_archivo else ''
        
        iconos = {
            'pdf': '📄', 'doc': '📝', 'docx': '📝', 'txt': '📃',
            'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'webp': '🖼️',
            'mp3': '🎵', 'wav': '🎵', 'flac': '🎵', 'ogg': '🎵',
            'mp4': '🎬', 'avi': '🎬', 'mkv': '🎬', 'mov': '🎬', 'webm': '🎬',
            'zip': '📦', 'rar': '📦', '7z': '📦', 'tar': '📦', 'gz': '📦',
            'exe': '⚙️', 'apk': '📱', 'deb': '🐧',
            'py': '🐍', 'js': '📜', 'html': '🌐', 'css': '🎨', 'json': '📋',
            'torrent': '🧲', 'magnet': '🧲'
        }
        
        return iconos.get(extension, '📁')

# ============================================================================
# CLASE GESTOR DESCARGAS CORE
# ============================================================================
class GestorDescargasCore:
    """Clase principal para la lógica del gestor de descargas"""
    
    def __init__(self, directorio_descargas=None):
        # En Termux, usar almacenamiento interno
        if directorio_descargas:
            self.directorio_descargas = directorio_descargas
        else:
            # Intentar detectar directorio de descargas en Termux
            posibles_rutas = [
                "/sdcard/Download",
                "/storage/emulated/0/Download",
                str(Path.home() / "storage" / "shared" / "Download"),
                str(Path.home() / "downloads")
            ]
            
            for ruta in posibles_rutas:
                if os.path.exists(ruta):
                    self.directorio_descargas = ruta
                    break
            else:
                self.directorio_descargas = str(Path.home())
        
        self.archivo_persistencia = "descargas_pendientes.json"
        
        # Estructuras de datos
        self.descargas_activas = {}
        self.cola_progreso = queue.Queue()
        self.descargas_semaphore = threading.Semaphore(MAX_DESCARGAS_SIMULTANEAS)
        self.analisis_semaphore = threading.Semaphore(MAX_ANALISIS_SIMULTANEOS)
        
        # Pool de sesiones
        self.session_pool = {}
        
        # Thread pool para análisis
        self.thread_pool = concurrent.futures.ThreadPoolExecutor(
            max_workers=MAX_ANALISIS_SIMULTANEOS
        )
        
    def obtener_session(self, thread_id=None):
        """Obtiene o crea una sesión HTTP reutilizable"""
        if thread_id is None:
            thread_id = threading.get_ident()
        
        if thread_id not in self.session_pool:
            session = requests.Session()
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=MAX_DESCARGAS_SIMULTANEAS * 2,
                pool_maxsize=MAX_DESCARGAS_SIMULTANEAS * 2,
                max_retries=2
            )
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            self.session_pool[thread_id] = session
        
        return self.session_pool[thread_id]
        
    def analizar_servidor_async(self, url, callback):
        """Analiza el servidor de forma asíncrona"""
        def analizar():
            with self.analisis_semaphore:
                tamaños = []
                try:
                    session = self.obtener_session()
                    
                    # Intentar HEAD
                    try:
                        respuesta = session.head(url, timeout=3, allow_redirects=True)
                        if 'content-length' in respuesta.headers:
                            tamaños.append(int(respuesta.headers['content-length']))
                    except:
                        pass
                    
                    # Intentar GET con rango
                    if not tamaños:
                        try:
                            headers = {'Range': 'bytes=0-0'}
                            respuesta = session.get(url, headers=headers, timeout=3)
                            if 'content-range' in respuesta.headers:
                                rango = respuesta.headers['content-range']
                                if '/' in rango:
                                    tamaños.append(int(rango.split('/')[-1]))
                        except:
                            pass
                            
                except Exception as e:
                    print(f"Error analizando {url}: {e}")
                
                # Ejecutar callback
                callback(url, max(tamaños) if tamaños else None)
        
        # Ejecutar en thread pool
        self.thread_pool.submit(analizar)
        
    def agregar_descarga(self, url, descarga_id=None, datos_persistencia=None):
        """Agrega una nueva descarga"""
        descarga = Descarga(url, descarga_id, datos_persistencia)
        
        # Configurar nombre si no existe
        if not descarga.nombre_archivo:
            descarga.nombre_archivo = descarga.obtener_nombre_archivo()
        
        # Configurar rutas
        if not descarga.ruta_completa:
            descarga.ruta_completa = os.path.join(
                self.directorio_descargas, 
                descarga.nombre_archivo
            )
            descarga.ruta_parcial = descarga.ruta_completa + ".part"
        
        # Verificar archivo parcial existente
        if os.path.exists(descarga.ruta_parcial) and descarga.bytes_descargados == 0:
            try:
                descarga.bytes_descargados = os.path.getsize(descarga.ruta_parcial)
            except:
                pass
        
        # Almacenar descarga
        self.descargas_activas[descarga.id] = descarga
        
        # Si no hay tamaño total y no es de persistencia, analizar
        if descarga.total_bytes is None and datos_persistencia is None:
            descarga.analizando = True
            self.analizar_servidor_async(
                url, 
                lambda url, tamano: self._on_analisis_completado(descarga.id, tamano)
            )
        elif not descarga.pausada:
            # Iniciar descarga inmediatamente
            self.iniciar_hilo_descarga(descarga.id)
        
        return descarga.id
        
    def _on_analisis_completado(self, descarga_id, total_bytes):
        """Callback cuando se completa el análisis"""
        descarga = self.descargas_activas.get(descarga_id)
        if not descarga:
            return
            
        descarga.analizando = False
        if total_bytes:
            descarga.total_bytes = total_bytes
        
        # Enviar actualización
        self._enviar_progreso(descarga_id, 'analisis_completado', total_bytes)
        
        # Iniciar descarga si no está pausada
        if not descarga.pausada:
            self.iniciar_hilo_descarga(descarga_id)
            
    def iniciar_hilo_descarga(self, descarga_id):
        """Inicia un hilo para la descarga"""
        descarga = self.descargas_activas.get(descarga_id)
        if not descarga or (descarga.hilo and descarga.hilo.is_alive()):
            return
            
        hilo = threading.Thread(target=self._descargar_archivo, args=(descarga_id,))
        hilo.daemon = True
        descarga.hilo = hilo
        hilo.start()
        
    def _descargar_archivo(self, descarga_id):
        """Método interno para descargar archivo"""
        with self.descargas_semaphore:
            descarga = self.descargas_activas.get(descarga_id)
            if not descarga:
                return
                
            try:
                session = self.obtener_session()
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36',
                    'Accept': '*/*',
                }
                
                if descarga.bytes_descargados > 0:
                    headers['Range'] = f'bytes={descarga.bytes_descargados}-'
                
                with session.get(descarga.url, headers=headers, stream=True, 
                               timeout=(5, 15)) as respuesta:
                    respuesta.raise_for_status()
                    
                    # Actualizar tamaño total
                    if 'content-length' in respuesta.headers and descarga.total_bytes is None:
                        content_length = int(respuesta.headers['content-length'])
                        descarga.total_bytes = content_length + descarga.bytes_descargados
                        self._enviar_progreso(descarga_id, 'tamano_actualizado', descarga.total_bytes)
                    
                    modo = 'ab' if descarga.bytes_descargados > 0 else 'wb'
                    with open(descarga.ruta_parcial, modo, buffering=8192) as archivo:
                        tiempo_inicio = time.time()
                        ultima_actualizacion = tiempo_inicio
                        bytes_por_segundo = 0
                        bytes_este_segundo = 0
                        
                        for chunk in respuesta.iter_content(chunk_size=16384):  # Reducido para móvil
                            if not chunk:
                                continue
                            
                            # Verificar pausa
                            if descarga.pausada:
                                while descarga.pausada and not descarga.cancelada:
                                    time.sleep(0.1)
                            
                            # Verificar cancelación
                            if descarga.cancelada:
                                archivo.close()
                                if os.path.exists(descarga.ruta_parcial):
                                    try:
                                        os.remove(descarga.ruta_parcial)
                                    except:
                                        pass
                                self._enviar_progreso(descarga_id, 'cancelada', 0)
                                return
                            
                            # Escribir chunk
                            archivo.write(chunk)
                            descarga.bytes_descargados += len(chunk)
                            bytes_este_segundo += len(chunk)
                            
                            tiempo_actual = time.time()
                            
                            # Calcular velocidad
                            if tiempo_actual - tiempo_inicio >= 1:
                                bytes_por_segundo = bytes_este_segundo / (tiempo_actual - tiempo_inicio)
                                bytes_este_segundo = 0
                                tiempo_inicio = tiempo_actual
                            
                            # Actualizar cada 0.3 segundos (más lento para móvil)
                            if tiempo_actual - ultima_actualizacion >= 0.3:
                                descarga.velocidad_promedio = bytes_por_segundo
                                
                                if descarga.total_bytes and bytes_por_segundo > 0:
                                    bytes_restantes = descarga.total_bytes - descarga.bytes_descargados
                                    descarga.tiempo_restante = bytes_restantes / bytes_por_segundo
                                
                                self._enviar_progreso(descarga_id, 'progreso', descarga.bytes_descargados)
                                ultima_actualizacion = tiempo_actual
                
                # Descarga completada
                if not descarga.cancelada:
                    if os.path.exists(descarga.ruta_parcial):
                        os.rename(descarga.ruta_parcial, descarga.ruta_completa)
                    
                    descarga.completada = True
                    self._enviar_progreso(descarga_id, 'completada', descarga.bytes_descargados)
                    
            except Exception as e:
                if not descarga.cancelada:
                    self._enviar_progreso(descarga_id, 'error', str(e)[:100])
                    
    def _enviar_progreso(self, descarga_id, tipo, dato):
        """Envía actualización a la cola de progreso"""
        self.cola_progreso.put((descarga_id, tipo, dato))
        
    def pausar_reanudar_descarga(self, descarga_id):
        """Pausa o reanuda una descarga específica"""
        descarga = self.descargas_activas.get(descarga_id)
        if not descarga:
            return
            
        descarga.pausada = not descarga.pausada
        
        if not descarga.pausada and (descarga.hilo is None or not descarga.hilo.is_alive()):
            self.iniciar_hilo_descarga(descarga_id)
            
    def cancelar_descarga(self, descarga_id):
        """Cancela una descarga específica"""
        descarga = self.descargas_activas.get(descarga_id)
        if not descarga:
            return
            
        descarga.cancelada = True
        descarga.pausada = False
        
        # Enviar notificación
        self._enviar_progreso(descarga_id, 'cancelada', 0)
        
    def limpiar_descargas_completadas(self):
        """Elimina las descargas completadas de la lista"""
        descargas_a_eliminar = []
        
        for descarga_id, descarga in self.descargas_activas.items():
            if descarga.completada or descarga.cancelada:
                descargas_a_eliminar.append(descarga_id)
        
        for descarga_id in descargas_a_eliminar:
            if descarga_id in self.descargas_activas:
                del self.descargas_activas[descarga_id]
        
        return len(descargas_a_eliminar)
        
    def obtener_estadisticas(self):
        """Obtiene estadísticas de las descargas"""
        total = len(self.descargas_activas)
        activas = sum(1 for d in self.descargas_activas.values() 
                     if not d.pausada and not d.completada and not d.cancelada)
        pausadas = sum(1 for d in self.descargas_activas.values() 
                      if d.pausada and not d.completada and not d.cancelada)
        completadas = sum(1 for d in self.descargas_activas.values() 
                         if d.completada)
        analizando = sum(1 for d in self.descargas_activas.values() 
                        if d.analizando)
        
        return {
            'total': total,
            'activas': activas,
            'pausadas': pausadas,
            'completadas': completadas,
            'analizando': analizando
        }
        
    def formatear_tamano(self, bytes):
        """Formatea el tamaño en bytes a una cadena legible"""
        if bytes is None:
            return "?"
        
        if bytes < 1024:
            return f"{bytes} B"
        elif bytes < 1024 * 1024:
            return f"{bytes/1024:.1f} KB"
        elif bytes < 1024 * 1024 * 1024:
            return f"{bytes/(1024*1024):.1f} MB"
        else:
            return f"{bytes/(1024*1024*1024):.2f} GB"
            
    def formatear_tiempo(self, segundos):
        """Formatea segundos a una cadena legible"""
        if segundos is None or segundos <= 0:
            return "--:--"
        
        if segundos < 60:
            return f"{int(segundos)}s"
        elif segundos < 3600:
            minutos = int(segundos // 60)
            segundos = int(segundos % 60)
            return f"{minutos}:{segundos:02d}"
        else:
            horas = int(segundos // 3600)
            minutos = int((segundos % 3600) // 60)
            return f"{horas}:{minutos:02d}:{int(segundos%60):02d}"
            
    # Métodos de persistencia
    def guardar_descarga_persistente(self, descarga_id):
        """Guarda el estado de una descarga en el archivo de persistencia"""
        descarga = self.descargas_activas.get(descarga_id)
        if not descarga:
            return
            
        descargas_persistentes = self.cargar_todas_descargas_persistentes()
        
        descargas_persistentes[descarga_id] = {
            'url': descarga.url,
            'nombre_archivo': descarga.nombre_archivo,
            'ruta_completa': descarga.ruta_completa,
            'ruta_parcial': descarga.ruta_parcial,
            'bytes_descargados': descarga.bytes_descargados,
            'total_bytes': descarga.total_bytes,
            'pausada': descarga.pausada,
            'completada': descarga.completada,
            'cancelada': descarga.cancelada,
            'directorio_descargas': self.directorio_descargas,
            'timestamp': time.time()
        }
        
        try:
            with open(self.archivo_persistencia, 'w', encoding='utf-8') as f:
                json.dump(descargas_persistentes, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error guardando persistencia: {e}")
            
    def eliminar_descarga_persistente(self, descarga_id):
        """Elimina una descarga del archivo de persistencia"""
        descargas_persistentes = self.cargar_todas_descargas_persistentes()
        
        if descarga_id in descargas_persistentes:
            del descargas_persistentes[descarga_id]
            
            try:
                with open(self.archivo_persistencia, 'w', encoding='utf-8') as f:
                    json.dump(descargas_persistentes, f, ensure_ascii=False, indent=2)
            except Exception as e:
                print(f"Error guardando persistencia: {e}")
                
    def cargar_todas_descargas_persistentes(self):
        """Carga todas las descargas del archivo de persistencia"""
        try:
            if os.path.exists(self.archivo_persistencia):
                with open(self.archivo_persistencia, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            print(f"Error cargando persistencia: {e}")
            
        return {}
        
    def cargar_descargas_pendientes(self):
        """Carga las descargas pendientes desde el archivo de persistencia"""
        descargas_persistentes = self.cargar_todas_descargas_persistentes()
        
        if not descargas_persistentes:
            return []
            
        # Filtrar descargas antiguas (más de 7 días)
        tiempo_actual = time.time()
        descargas_cargadas = []
        
        for descarga_id, datos in descargas_persistentes.items():
            timestamp = datos.get('timestamp', 0)
            
            # Cargar descargas de los últimos 7 días
            if tiempo_actual - timestamp < 7 * 24 * 3600:
                # Solo cargar si no está completada ni cancelada
                if not datos.get('completada', False) and not datos.get('cancelada', False):
                    try:
                        self.agregar_descarga(datos['url'], descarga_id, datos)
                        descargas_cargadas.append(descarga_id)
                    except Exception as e:
                        print(f"Error cargando descarga {descarga_id}: {e}")
        
        return descargas_cargadas
        
    def cerrar(self):
        """Cierra todas las sesiones y recursos"""
        # Pausar todas las descargas
        for descarga in self.descargas_activas.values():
            if not descarga.pausada and not descarga.completada and not descarga.cancelada:
                descarga.pausada = True
        
        # Guardar todas las descargas
        for descarga_id in self.descargas_activas:
            self.guardar_descarga_persistente(descarga_id)
        
        # Cerrar thread pool
        self.thread_pool.shutdown(wait=False)
        
        # Cerrar sesiones
        for session in self.session_pool.values():
            try:
                session.close()
            except:
                pass
        self.session_pool.clear()

# ============================================================================
# INTERFAZ GRÁFICA OPTIMIZADA PARA MÓVIL
# ============================================================================
class GestorDescargasMobileGUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"{EMOJIS['iniciar']} Gestor Descargas Mobile")
        
        # Configurar para pantalla móvil
        self.ancho_pantalla = root.winfo_screenwidth()
        self.alto_pantalla = root.winfo_screenheight()
        
        # Tamaño optimizado para móvil
        self.ancho_ventana = min(400, self.ancho_pantalla)
        self.alto_ventana = min(700, self.alto_pantalla)
        
        self.root.geometry(f"{self.ancho_ventana}x{self.alto_ventana}")
        self.root.resizable(True, True)
        
        # Instanciar el core
        self.core = GestorDescargasCore()
        
        # Variables de estado
        self.pausar_todas_estado = "pausar"
        self.widgets_descargas = {}
        self.menu_abierto = False
        
        # Configurar estilo
        self.configurar_estilos()
        
        # Configurar interfaz
        self.configurar_interfaz()
        
        # Cargar descargas pendientes
        self.cargar_descargas_pendientes()
        
        # Iniciar bucle de actualización
        self.actualizar_interfaz()
        
    def configurar_estilos(self):
        """Configura estilos para móvil"""
        self.estilo = ttk.Style()
        self.estilo.theme_use('clam')
        
        # Configurar colores
        self.root.configure(bg=COLORES["fondo"])
        
        # Configurar fuentes para móvil
        self.fuente_titulo = ("Segoe UI", 14, "bold")
        self.fuente_normal = ("Segoe UI", 10)
        self.fuente_pequena = ("Segoe UI", 9)
        
    def configurar_interfaz(self):
        """Configura la interfaz optimizada para móvil"""
        # Frame principal con scroll
        self.main_canvas = tk.Canvas(self.root, bg=COLORES["fondo"], highlightthickness=0)
        self.scrollbar = ttk.Scrollbar(self.root, orient="vertical", command=self.main_canvas.yview)
        self.scrollable_frame = tk.Frame(self.main_canvas, bg=COLORES["fondo"])
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
        )
        
        self.main_canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.main_canvas.configure(yscrollcommand=self.scrollbar.set)
        
        # Empaquetar
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.scrollbar.pack(side="right", fill="y")
        
        # Configurar scroll con touch
        self.main_canvas.bind_all("<MouseWheel>", self._on_mousewheel)
        
        # ===== HEADER =====
        header_frame = tk.Frame(self.scrollable_frame, bg=COLORES["fondo_tarjeta"], 
                               relief="flat", borderwidth=1)
        header_frame.pack(fill="x", padx=10, pady=10)
        
        # Título con emoji
        titulo_label = tk.Label(
            header_frame,
            text=f"{EMOJIS['iniciar']} GESTOR DE DESCARGAS",
            font=self.fuente_titulo,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["acento"],
            padx=15,
            pady=15
        )
        titulo_label.pack()
        
        # Versión móvil
        version_label = tk.Label(
            header_frame,
            text="📱 Versión Mobile Optimizada",
            font=self.fuente_pequena,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto_secundario"],
            pady=5
        )
        version_label.pack()
        
        # ===== ENTRADA DE URLs =====
        entrada_frame = tk.Frame(self.scrollable_frame, bg=COLORES["fondo_tarjeta"],
                                relief="flat", borderwidth=1)
        entrada_frame.pack(fill="x", padx=10, pady=5)
        
        tk.Label(
            entrada_frame,
            text=f"{EMOJIS['url']} URLs a descargar:",
            font=self.fuente_normal,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 5))
        
        # Textarea para URLs
        self.text_urls = scrolledtext.ScrolledText(
            entrada_frame,
            height=4,
            font=self.fuente_normal,
            bg=COLORES["fondo"],
            fg=COLORES["texto"],
            relief="sunken",
            borderwidth=2,
            insertbackground=COLORES["acento"]
        )
        self.text_urls.pack(fill="x", padx=15, pady=5)
        self.text_urls.insert("1.0", "Pega URLs aquí...")
        self.text_urls.bind("<Button-1>", lambda e: self.limpiar_texto_urls())
        
        # Botones de entrada rápida
        botones_frame = tk.Frame(entrada_frame, bg=COLORES["fondo_tarjeta"])
        botones_frame.pack(fill="x", padx=15, pady=10)
        
        self.btn_pegar = self.crear_boton(
            botones_frame,
            f"{EMOJIS['pegar']} Pegar",
            self.pegar_urls,
            width=15
        )
        self.btn_pegar.pack(side="left", padx=(0, 10))
        
        self.btn_limpiar = self.crear_boton(
            botones_frame,
            f"{EMOJIS['limpiar']} Limpiar",
            self.limpiar_texto_urls,
            width=15
        )
        self.btn_limpiar.pack(side="left")
        
        # ===== CONTROLES PRINCIPALES =====
        controles_frame = tk.Frame(self.scrollable_frame, bg=COLORES["fondo_tarjeta"],
                                  relief="flat", borderwidth=1)
        controles_frame.pack(fill="x", padx=10, pady=10)
        
        # Botón principal de iniciar
        self.btn_iniciar = self.crear_boton(
            controles_frame,
            f"{EMOJIS['iniciar']} INICIAR DESCARGAS",
            self.iniciar_descargas,
            bg=COLORES["exito"],
            fg="white",
            font=("Segoe UI", 11, "bold"),
            pady=12
        )
        self.btn_iniciar.pack(fill="x", padx=20, pady=5)
        
        # Controles secundarios en grid
        grid_frame = tk.Frame(controles_frame, bg=COLORES["fondo_tarjeta"])
        grid_frame.pack(fill="x", padx=20, pady=10)
        
        # Fila 1
        row1 = tk.Frame(grid_frame, bg=COLORES["fondo_tarjeta"])
        row1.pack(fill="x", pady=5)
        
        self.btn_carpeta = self.crear_boton(
            row1,
            f"{EMOJIS['carpeta']} Carpeta",
            self.seleccionar_directorio,
            width=15
        )
        self.btn_carpeta.pack(side="left", padx=(0, 10))
        
        self.btn_pausar_todas = self.crear_boton(
            row1,
            f"{EMOJIS['pausar']} Pausar Todas",
            self.pausar_descargas_todas,
            width=15,
            state="disabled"
        )
        self.btn_pausar_todas.pack(side="left")
        
        # Fila 2
        row2 = tk.Frame(grid_frame, bg=COLORES["fondo_tarjeta"])
        row2.pack(fill="x", pady=5)
        
        self.btn_limpiar_completadas = self.crear_boton(
            row2,
            f"{EMOJIS['limpiar']} Limpiar",
            self.limpiar_completadas,
            width=15
        )
        self.btn_limpiar_completadas.pack(side="left", padx=(0, 10))
        
        self.btn_config = self.crear_boton(
            row2,
            f"{EMOJIS['config']} Config",
            self.mostrar_config,
            width=15
        )
        self.btn_config.pack(side="left")
        
        # ===== LISTA DE DESCARGAS =====
        descargas_frame = tk.Frame(self.scrollable_frame, bg=COLORES["fondo_tarjeta"],
                                  relief="flat", borderwidth=1)
        descargas_frame.pack(fill="x", padx=10, pady=10)
        
        tk.Label(
            descargas_frame,
            text=f"{EMOJIS['descargando']} DESCARGAS ACTIVAS",
            font=self.fuente_normal,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 5))
        
        # Frame para lista de descargas
        self.lista_descargas_frame = tk.Frame(descargas_frame, bg=COLORES["fondo_tarjeta"])
        self.lista_descargas_frame.pack(fill="x", padx=10, pady=5)
        
        # Label cuando no hay descargas
        self.label_sin_descargas = tk.Label(
            self.lista_descargas_frame,
            text=f"{EMOJIS['iniciar']} No hay descargas activas\nPega URLs y presiona INICIAR",
            font=self.fuente_normal,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto_secundario"],
            pady=20,
            justify="center"
        )
        self.label_sin_descargas.pack(fill="x")
        
        # ===== ESTADÍSTICAS =====
        stats_frame = tk.Frame(self.scrollable_frame, bg=COLORES["fondo_tarjeta"],
                              relief="flat", borderwidth=1)
        stats_frame.pack(fill="x", padx=10, pady=10)
        
        self.label_stats = tk.Label(
            stats_frame,
            text=f"{EMOJIS['estadisticas']} Cargando estadísticas...",
            font=self.fuente_pequena,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto_secundario"],
            anchor="w"
        )
        self.label_stats.pack(fill="x", padx=15, pady=10)
        
        # ===== LOGS =====
        logs_frame = tk.Frame(self.scrollable_frame, bg=COLORES["fondo_tarjeta"],
                             relief="flat", borderwidth=1)
        logs_frame.pack(fill="x", padx=10, pady=(5, 20))
        
        tk.Label(
            logs_frame,
            text=f"{EMOJIS['logs']} REGISTRO",
            font=self.fuente_pequena,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto_secundario"],
            anchor="w"
        ).pack(fill="x", padx=15, pady=(10, 5))
        
        self.text_logs = scrolledtext.ScrolledText(
            logs_frame,
            height=3,
            font=self.fuente_pequena,
            bg=COLORES["fondo"],
            fg=COLORES["texto"],
            relief="sunken",
            borderwidth=1
        )
        self.text_logs.pack(fill="x", padx=15, pady=(0, 10))
        
        # Configurar cierre
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        
    def _on_mousewheel(self, event):
        """Maneja el scroll con rueda del mouse/touch"""
        self.main_canvas.yview_scroll(int(-1*(event.delta/120)), "units")
    
    def crear_boton(self, parent, text, command, **kwargs):
        """Crea un botón estilizado para móvil"""
        bg = kwargs.pop('bg', COLORES["boton_bg"])
        fg = kwargs.pop('fg', COLORES["boton_fg"])
        font = kwargs.pop('font', self.fuente_normal)
        width = kwargs.pop('width', None)
        state = kwargs.pop('state', 'normal')
        pady = kwargs.pop('pady', 8)
        
        btn = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=fg,
            font=font,
            relief="flat",
            borderwidth=0,
            padx=15,
            pady=pady,
            cursor="hand2",
            activebackground=COLORES["hover_bg"],
            activeforeground=fg,
            state=state
        )
        
        if width:
            btn.config(width=width)
        
        # Efecto hover
        btn.bind("<Enter>", lambda e, b=btn: b.config(bg=COLORES["hover_bg"]))
        btn.bind("<Leave>", lambda e, b=btn: b.config(bg=bg))
        
        return btn
    
    def limpiar_texto_urls(self, event=None):
        """Limpia el área de texto de URLs"""
        if "Pega URLs aquí..." in self.text_urls.get("1.0", "end"):
            self.text_urls.delete("1.0", "end")
    
    def pegar_urls(self):
        """Pega URLs desde el portapapeles"""
        try:
            self.limpiar_texto_urls()
            texto = self.root.clipboard_get()
            
            if texto:
                self.text_urls.insert("1.0", texto)
                self.agregar_log(f"{EMOJIS['pegar']} URLs pegadas desde portapapeles")
            else:
                self.agregar_log(f"{EMOJIS['advertencia']} Portapapeles vacío")
                
        except Exception as e:
            self.agregar_log(f"{EMOJIS['error']} Error al pegar: {str(e)[:30]}")
    
    def seleccionar_directorio(self):
        """Selecciona directorio de destino"""
        directorio = filedialog.askdirectory(
            initialdir=self.core.directorio_descargas,
            title="Seleccionar carpeta de descargas"
        )
        
        if directorio:
            self.core.directorio_descargas = directorio
            self.agregar_log(f"{EMOJIS['carpeta']} Carpeta cambiada a: {directorio[-30:]}")
    
    def iniciar_descargas(self):
        """Inicia las descargas"""
        contenido = self.text_urls.get("1.0", "end").strip()
        
        if not contenido or contenido == "Pega URLs aquí...":
            messagebox.showwarning("Sin URLs", "No hay URLs para descargar.")
            return
        
        lineas = contenido.split('\n')
        urls = []
        
        for linea in lineas:
            linea = linea.strip()
            if linea and (linea.startswith('http://') or linea.startswith('https://')):
                urls.append(linea)
        
        if not urls:
            messagebox.showwarning("Sin URLs válidas", "No se encontraron URLs válidas.")
            return
        
        # Actualizar interfaz
        self.btn_iniciar.config(state="disabled", text=f"{EMOJIS['analizando']} PROCESANDO...")
        self.btn_pausar_todas.config(state="normal")
        self.label_sin_descargas.pack_forget()
        
        # Procesar en hilo
        threading.Thread(
            target=self._procesar_urls_hilo,
            args=(urls,),
            daemon=True
        ).start()
    
    def _procesar_urls_hilo(self, urls):
        """Procesa URLs en hilo separado"""
        agregadas = 0
        
        for i, url in enumerate(urls):
            try:
                # Verificar si ya existe
                existe = any(d.url == url for d in self.core.descargas_activas.values())
                
                if not existe:
                    descarga_id = self.core.agregar_descarga(url)
                    self.root.after(0, self.crear_widget_descarga, descarga_id)
                    agregadas += 1
                    
                    # Pequeña pausa para no saturar
                    time.sleep(0.1)
                    
            except Exception as e:
                print(f"Error: {e}")
        
        # Actualizar en hilo principal
        self.root.after(0, self._finalizar_inicio, agregadas, len(urls))
    
    def _finalizar_inicio(self, agregadas, total):
        """Finaliza el inicio de descargas"""
        mensaje = f"{EMOJIS['iniciar']} {agregadas} descargas iniciadas"
        if agregadas < total:
            mensaje += f" ({total - agregadas} duplicadas)"
        
        self.agregar_log(mensaje)
        self.btn_iniciar.config(state="normal", text=f"{EMOJIS['iniciar']} INICIAR DESCARGAS")
        self.text_urls.delete("1.0", "end")
        self.text_urls.insert("1.0", "Pega más URLs aquí...")
    
    def crear_widget_descarga(self, descarga_id):
        """Crea widget para una descarga"""
        descarga = self.core.descargas_activas.get(descarga_id)
        if not descarga:
            return
        
        # Crear frame de descarga
        frame = tk.Frame(
            self.lista_descargas_frame,
            bg=COLORES["fondo_tarjeta"],
            relief="ridge",
            borderwidth=1
        )
        frame.pack(fill="x", padx=5, pady=5)
        
        # Header con icono y nombre
        header_frame = tk.Frame(frame, bg=COLORES["fondo_tarjeta"])
        header_frame.pack(fill="x", padx=10, pady=(10, 5))
        
        # Icono
        icono = descarga.obtener_icono()
        lbl_icono = tk.Label(
            header_frame,
            text=icono,
            font=("Segoe UI", 16),
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["acento"]
        )
        lbl_icono.pack(side="left", padx=(0, 10))
        
        # Nombre (truncado para móvil)
        nombre = descarga.nombre_archivo
        if len(nombre) > 25:
            nombre = nombre[:22] + "..."
        
        lbl_nombre = tk.Label(
            header_frame,
            text=nombre,
            font=self.fuente_normal,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto"],
            anchor="w"
        )
        lbl_nombre.pack(side="left", fill="x", expand=True)
        
        # Barra de progreso
        progress_frame = tk.Frame(frame, bg=COLORES["progreso_bg"], height=10)
        progress_frame.pack(fill="x", padx=10, pady=5)
        
        # Barra interior
        porcentaje = 0
        if descarga.total_bytes and descarga.total_bytes > 0:
            porcentaje = (descarga.bytes_descargados / descarga.total_bytes) * 100
        
        barra_width = int((porcentaje / 100) * (self.ancho_ventana - 40))
        barra = tk.Frame(
            progress_frame,
            bg=COLORES["progreso_fg"],
            height=10
        )
        barra.place(x=0, y=0, width=barra_width, height=10)
        
        # Info de progreso
        info_frame = tk.Frame(frame, bg=COLORES["fondo_tarjeta"])
        info_frame.pack(fill="x", padx=10, pady=(0, 5))
        
        # Porcentaje
        lbl_porcentaje = tk.Label(
            info_frame,
            text=f"{porcentaje:.1f}%",
            font=self.fuente_pequena,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto"],
            width=8
        )
        lbl_porcentaje.pack(side="left")
        
        # Tamaño
        tamano_text = f"{self.core.formatear_tamano(descarga.bytes_descargados)}"
        if descarga.total_bytes:
            tamano_text += f" / {self.core.formatear_tamano(descarga.total_bytes)}"
        
        lbl_tamano = tk.Label(
            info_frame,
            text=tamano_text,
            font=self.fuente_pequena,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto_secundario"]
        )
        lbl_tamano.pack(side="left", padx=(10, 0))
        
        # Estado
        estado_text = "🔍 Analizando..." if descarga.analizando else \
                     "⏸️ Pausada" if descarga.pausada else \
                     "⏳ Preparando..."
        
        lbl_estado = tk.Label(
            info_frame,
            text=estado_text,
            font=self.fuente_pequena,
            bg=COLORES["fondo_tarjeta"],
            fg=COLORES["texto_secundario"]
        )
        lbl_estado.pack(side="right")
        
        # Botones
        btn_frame = tk.Frame(frame, bg=COLORES["fondo_tarjeta"])
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        btn_pausa_text = f"{EMOJIS['reanudar']} Reanudar" if descarga.pausada else f"{EMOJIS['pausar']} Pausar"
        btn_pausa = self.crear_boton(
            btn_frame,
            btn_pausa_text,
            lambda: self.pausar_reanudar_descarga(descarga_id),
            width=12,
            pady=6
        )
        btn_pausa.pack(side="left", padx=(0, 10))
        
        btn_cancelar = self.crear_boton(
            btn_frame,
            f"{EMOJIS['cancelar']} Cancelar",
            lambda: self.cancelar_descarga(descarga_id),
            width=12,
            pady=6
        )
        btn_cancelar.pack(side="left")
        
        # Guardar widgets
        self.widgets_descargas[descarga_id] = {
            'frame': frame,
            'barra': barra,
            'lbl_porcentaje': lbl_porcentaje,
            'lbl_tamano': lbl_tamano,
            'lbl_estado': lbl_estado,
            'lbl_nombre': lbl_nombre,
            'btn_pausa': btn_pausa,
            'btn_cancelar': btn_cancelar,
            'barra_width': self.ancho_ventana - 40
        }
    
    def pausar_reanudar_descarga(self, descarga_id):
        """Pausa o reanuda una descarga"""
        self.core.pausar_reanudar_descarga(descarga_id)
        descarga = self.core.descargas_activas.get(descarga_id)
        widgets = self.widgets_descargas.get(descarga_id)
        
        if descarga and widgets:
            if descarga.pausada:
                widgets['btn_pausa'].config(text=f"{EMOJIS['reanudar']} Reanudar")
                widgets['lbl_estado'].config(text="⏸️ Pausada", fg=COLORES["pausa"])
                self.agregar_log(f"{EMOJIS['pausar']} Pausada: {descarga.nombre_archivo[:20]}...")
            else:
                widgets['btn_pausa'].config(text=f"{EMOJIS['pausar']} Pausar")
                widgets['lbl_estado'].config(text="⬇️ Descargando...", fg=COLORES["texto"])
                self.agregar_log(f"{EMOJIS['reanudar']} Reanudada: {descarga.nombre_archivo[:20]}...")
    
    def pausar_descargas_todas(self):
        """Pausa o reanuda todas las descargas"""
        if self.pausar_todas_estado == "pausar":
            # Pausar todas
            for descarga_id, descarga in self.core.descargas_activas.items():
                if not descarga.pausada and not descarga.completada and not descarga.cancelada:
                    descarga.pausada = True
                    widgets = self.widgets_descargas.get(descarga_id)
                    if widgets:
                        widgets['btn_pausa'].config(text=f"{EMOJIS['reanudar']} Reanudar")
                        widgets['lbl_estado'].config(text="⏸️ Pausada", fg=COLORES["pausa"])
            
            self.btn_pausar_todas.config(text=f"{EMOJIS['reanudar']} Reanudar Todas")
            self.pausar_todas_estado = "reanudar"
            self.agregar_log(f"{EMOJIS['pausar']} TODAS las descargas pausadas")
            
        else:
            # Reanudar todas
            for descarga_id, descarga in self.core.descargas_activas.items():
                if descarga.pausada and not descarga.completada and not descarga.cancelada:
                    descarga.pausada = False
                    widgets = self.widgets_descargas.get(descarga_id)
                    if widgets:
                        widgets['btn_pausa'].config(text=f"{EMOJIS['pausar']} Pausar")
                        widgets['lbl_estado'].config(text="⬇️ Descargando...", fg=COLORES["texto"])
            
            self.btn_pausar_todas.config(text=f"{EMOJIS['pausar']} Pausar Todas")
            self.pausar_todas_estado = "pausar"
            self.agregar_log(f"{EMOJIS['reanudar']} TODAS las descargas reanudadas")
    
    def cancelar_descarga(self, descarga_id):
        """Cancela una descarga"""
        descarga = self.core.descargas_activas.get(descarga_id)
        if not descarga:
            return
        
        descarga.cancelada = True
        widgets = self.widgets_descargas.get(descarga_id)
        
        if widgets:
            widgets['lbl_estado'].config(text="❌ Cancelando...", fg=COLORES["error"])
            widgets['btn_pausa'].config(state="disabled")
            widgets['btn_cancelar'].config(state="disabled")
        
        self.agregar_log(f"{EMOJIS['cancelar']} Cancelando: {descarga.nombre_archivo[:20]}...")
    
    def limpiar_completadas(self):
        """Limpia descargas completadas"""
        eliminadas = self.core.limpiar_descargas_completadas()
        
        # Eliminar widgets
        for descarga_id in list(self.widgets_descargas.keys()):
            if descarga_id not in self.core.descargas_activas:
                widgets = self.widgets_descargas[descarga_id]
                if widgets['frame'].winfo_exists():
                    widgets['frame'].destroy()
                del self.widgets_descargas[descarga_id]
        
        # Mostrar mensaje si no hay descargas
        if not self.core.descargas_activas:
            self.label_sin_descargas.pack(fill="x")
        
        if eliminadas > 0:
            self.agregar_log(f"{EMOJIS['limpiar']} {eliminadas} descargas eliminadas")
    
    def mostrar_config(self):
        """Muestra configuración"""
        config_text = f"""
{EMOJIS['config']} CONFIGURACIÓN:
• Descargas simultáneas: {MAX_DESCARGAS_SIMULTANEAS}
• Directorio: {self.core.directorio_descargas}
• Archivo persistencia: {self.core.archivo_persistencia}
• Tamaño cola: {self.core.cola_progreso.qsize()}
"""
        messagebox.showinfo("Configuración", config_text)
    
    def agregar_log(self, mensaje):
        """Agrega mensaje al log"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.text_logs.insert("end", f"[{timestamp}] {mensaje}\n")
        self.text_logs.see("end")
        
        # Limitar líneas
        lineas = int(self.text_logs.index('end-1c').split('.')[0])
        if lineas > 50:
            self.text_logs.delete('1.0', '2.0')
    
    def actualizar_interfaz(self):
        """Actualiza la interfaz periódicamente"""
        try:
            # Procesar mensajes de la cola
            procesados = 0
            while not self.core.cola_progreso.empty() and procesados < 10:
                descarga_id, tipo, dato = self.core.cola_progreso.get_nowait()
                descarga = self.core.descargas_activas.get(descarga_id)
                widgets = self.widgets_descargas.get(descarga_id)
                
                if not descarga or not widgets:
                    continue
                
                if tipo == 'progreso':
                    # Actualizar progreso
                    if descarga.total_bytes and descarga.total_bytes > 0:
                        porcentaje = min(100, (descarga.bytes_descargados / descarga.total_bytes) * 100)
                        
                        # Actualizar barra
                        barra_width = int((porcentaje / 100) * widgets['barra_width'])
                        widgets['barra'].place_configure(width=barra_width)
                        
                        # Actualizar porcentaje
                        widgets['lbl_porcentaje'].config(text=f"{porcentaje:.1f}%")
                        
                        # Actualizar tamaño
                        tamano_text = f"{self.core.formatear_tamano(descarga.bytes_descargados)}"
                        if descarga.total_bytes:
                            tamano_text += f" / {self.core.formatear_tamano(descarga.total_bytes)}"
                        widgets['lbl_tamano'].config(text=tamano_text)
                        
                        # Actualizar estado con velocidad
                        if not descarga.pausada and descarga.velocidad_promedio > 0:
                            velocidad = self.core.formatear_tamano(descarga.velocidad_promedio)
                            tiempo = self.core.formatear_tiempo(descarga.tiempo_restante) if descarga.tiempo_restante else "--:--"
                            widgets['lbl_estado'].config(
                                text=f"{EMOJIS['velocidad']} {velocidad}/s {EMOJIS['reloj']} {tiempo}",
                                fg=COLORES["acento"]
                            )
                
                elif tipo == 'analisis_completado':
                    if dato:
                        descarga.total_bytes = dato
                        widgets['lbl_estado'].config(text="⬇️ Descargando...")
                
                elif tipo == 'completada':
                    widgets['barra'].place_configure(width=widgets['barra_width'])
                    widgets['barra'].config(bg=COLORES["exito"])
                    widgets['lbl_porcentaje'].config(text="100%")
                    widgets['lbl_estado'].config(
                        text=f"{EMOJIS['completado']} Completado",
                        fg=COLORES["exito"]
                    )
                    widgets['btn_pausa'].config(state="disabled", text=f"{EMOJIS['completado']}")
                    self.agregar_log(f"{EMOJIS['completado']} Completado: {descarga.nombre_archivo[:20]}...")
                
                elif tipo == 'error':
                    widgets['lbl_estado'].config(
                        text=f"{EMOJIS['error']} Error",
                        fg=COLORES["error"]
                    )
                    self.agregar_log(f"{EMOJIS['error']} Error en: {descarga.nombre_archivo[:20]}...")
                
                elif tipo == 'cancelada':
                    widgets['lbl_estado'].config(
                        text=f"{EMOJIS['cancelar']} Cancelada",
                        fg=COLORES["advertencia"]
                    )
                    self.agregar_log(f"{EMOJIS['cancelar']} Cancelada: {descarga.nombre_archivo[:20]}...")
                
                procesados += 1
            
        except Exception as e:
            print(f"Error en actualizar_interfaz: {e}")
        
        # Actualizar estadísticas cada 3 segundos
        if int(time.time()) % 3 == 0:
            self.actualizar_estadisticas()
        
        # Programar siguiente actualización
        self.root.after(300, self.actualizar_interfaz)  # Más lento para móvil
    
    def actualizar_estadisticas(self):
        """Actualiza las estadísticas"""
        try:
            stats = self.core.obtener_estadisticas()
            
            # Calcular velocidad total
            velocidad_total = 0
            for descarga in self.core.descargas_activas.values():
                if not descarga.pausada and not descarga.completada and not descarga.cancelada:
                    velocidad_total += descarga.velocidad_promedio
            
            stats_text = f"{EMOJIS['estadisticas']} "
            stats_text += f"📊 {stats['total']} | "
            stats_text += f"⬇️ {stats['activas']} | "
            stats_text += f"⏸️ {stats['pausadas']} | "
            stats_text += f"✅ {stats['completadas']}"
            
            if velocidad_total > 0:
                stats_text += f" | {EMOJIS['velocidad']} {self.core.formatear_tamano(velocidad_total)}/s"
            
            self.label_stats.config(text=stats_text)
            
        except Exception as e:
            print(f"Error actualizando estadísticas: {e}")
    
    def cargar_descargas_pendientes(self):
        """Carga descargas pendientes"""
        self.agregar_log(f"{EMOJIS['analizando']} Cargando descargas pendientes...")
        
        descargas_cargadas = self.core.cargar_descargas_pendientes()
        
        for descarga_id in descargas_cargadas:
            self.crear_widget_descarga(descarga_id)
        
        if descargas_cargadas:
            self.btn_pausar_todas.config(state="normal")
            self.label_sin_descargas.pack_forget()
            self.agregar_log(f"{EMOJIS['completado']} Cargadas {len(descargas_cargadas)} descargas pendientes")
    
    def cerrar_aplicacion(self):
        """Cierra la aplicación"""
        # Pausar todas las descargas
        activas = 0
        for descarga in self.core.descargas_activas.values():
            if not descarga.pausada and not descarga.completada and not descarga.cancelada:
                descarga.pausada = True
                activas += 1
        
        # Guardar persistencia
        for descarga_id in self.core.descargas_activas:
            self.core.guardar_descarga_persistente(descarga_id)
        
        # Cerrar core
        self.core.cerrar()
        
        if activas > 0:
            self.agregar_log(f"{EMOJIS['pausar']} {activas} descargas pausadas. Se reanudarán al abrir.")
        
        self.agregar_log(f"{EMOJIS['iniciar']} Aplicación cerrada.")
        self.root.destroy()

# ============================================================================
# PUNTO DE ENTRADA
# ============================================================================
def main():
    """Función principal"""
    print(f"""
    {EMOJIS['iniciar']} GESTOR DE DESCARGAS MOBILE
    {EMOJIS['velocidad']} Versión optimizada para Termux-X11
    {EMOJIS['config']} Iniciando...
    """)
    
    # Verificar requests
    try:
        import requests
    except ImportError:
        print(f"{EMOJIS['error']} Instalando requests...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
        print(f"{EMOJIS['completado']} requests instalado")
    
    # Configurar manejo de errores
    def excepcion_global(exctype, value, traceback_obj):
        error_msg = f"{EMOJIS['error']} Error: {value}"
        print(error_msg)
        
        try:
            messagebox.showerror("Error", str(value)[:100])
        except:
            pass
    
    sys.excepthook = excepcion_global
    
    # Crear ventana
    root = tk.Tk()
    
    try:
        app = GestorDescargasMobileGUI(root)
        
        # Centrar ventana
        root.update_idletasks()
        ancho = root.winfo_width()
        alto = root.winfo_height()
        x = (root.winfo_screenwidth() // 2) - (ancho // 2)
        y = (root.winfo_screenheight() // 2) - (alto // 2)
        root.geometry(f'+{x}+{y}')
        
        print(f"{EMOJIS['completado']} Interfaz cargada")
        print(f"{EMOJIS['config']} Tamaño pantalla: {app.ancho_pantalla}x{app.alto_pantalla}")
        
        root.mainloop()
        
    except Exception as e:
        print(f"{EMOJIS['error']} Error crítico: {e}")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
