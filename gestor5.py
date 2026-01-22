import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import time
import os
import json
import re
import shutil
import mimetypes

# Paleta de colores Premium para Termux X11
COLOR_BG = "#0f111a"          
COLOR_CARD = "#1a1c25"        
COLOR_PRIMARY = "#00d2ff"     
COLOR_SUCCESS = "#00ff88"     
COLOR_PAUSE = "#ffdf00"       
COLOR_ERROR = "#ff3e3e"       
COLOR_TEXT = "#ffffff"        
COLOR_TEXT_DIM = "#94a3b8"    
CONFIG_FILE = "download_config.json"

class ConfigManager:
    @staticmethod
    def load():
        defaults = {
            "dest_folder": os.path.join(os.path.expanduser("~"), "Downloads"),
            "max_simultaneous": 2
        }
        if not os.path.exists(defaults["dest_folder"]):
            try: os.makedirs(defaults["dest_folder"])
            except: pass
            
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r") as f:
                    return {**defaults, **json.load(f)}
            except:
                return defaults
        return defaults

    @staticmethod
    def save(config):
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(config, f)
        except:
            pass

class DownloadManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TURBO DOWNLOADER ULTIMATE v2.1")
        
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        width = int(sw * 0.96) if sw < 1000 else 1000
        height = int(sh * 0.88) if sh < 1000 else 750
        self.root.geometry(f"{width}x{height}")
        self.root.configure(bg=COLOR_BG)

        self.config = ConfigManager.load()
        self.dest_folder = self.config["dest_folder"]
        self.max_simultaneous = tk.IntVar(value=self.config["max_simultaneous"])
        
        self.queue = [] 
        self.active_count = 0
        self.lock = threading.Lock()
        
        self.pause_events = {}
        self.cancel_flags = {}

        self.url_var = tk.StringVar()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept-Encoding': 'identity',
            'Connection': 'keep-alive'
        }

        self.setup_styles()
        self.create_header()
        self.create_body()
        self.create_footer()

    def setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Treeview", 
                        background=COLOR_CARD, 
                        foreground=COLOR_TEXT, 
                        rowheight=55, 
                        fieldbackground=COLOR_CARD,
                        borderwidth=0,
                        font=('Segoe UI', 10))
        style.configure("Treeview.Heading", 
                        font=('Segoe UI', 10, 'bold'), 
                        background="#24283b", 
                        foreground=COLOR_PRIMARY)
        style.map("Treeview", background=[('selected', "#2d314d")])

    def create_header(self):
        header = tk.Frame(self.root, bg=COLOR_BG, pady=15, padx=20)
        header.pack(fill=tk.X)

        row1 = tk.Frame(header, bg=COLOR_BG)
        row1.pack(fill=tk.X, pady=(0, 10))
        tk.Label(row1, text="⚡ TURBO DOWNLOADER", font=('Segoe UI', 18, 'bold'), bg=COLOR_BG, fg=COLOR_PRIMARY).pack(side=tk.LEFT)
        
        tk.Button(row1, text="🗑️ LIMPIAR", command=self.clear_all_list, bg="#2d314d", fg=COLOR_ERROR, 
                  font=('Segoe UI', 9, 'bold'), relief="flat", padx=15, pady=5, 
                  activebackground=COLOR_ERROR, activeforeground="white").pack(side=tk.RIGHT)

        row2 = tk.Frame(header, bg=COLOR_BG)
        row2.pack(fill=tk.X, pady=(0, 15))
        tk.Label(row2, text="⚙️ Descargas simultáneas:", bg=COLOR_BG, fg=COLOR_TEXT_DIM, font=('Segoe UI', 10)).pack(side=tk.LEFT)
        spin = tk.Spinbox(row2, from_=1, to=10, textvariable=self.max_simultaneous, width=5, 
                          command=self.save_current_config, bg=COLOR_CARD, fg=COLOR_PRIMARY, 
                          buttonbackground=COLOR_PRIMARY, relief="flat", font=('Segoe UI', 10, 'bold'), justify='center')
        spin.pack(side=tk.LEFT, padx=15)

        entry_bg = tk.Frame(header, bg="#334155", padx=1, pady=1)
        entry_bg.pack(fill=tk.X)
        entry_inner = tk.Frame(entry_bg, bg=COLOR_CARD, padx=10, pady=10)
        entry_inner.pack(fill=tk.X)

        tk.Label(entry_inner, text="🔗", bg=COLOR_CARD, fg=COLOR_PRIMARY, font=('Segoe UI', 14)).pack(side=tk.LEFT, padx=(0, 10))
        
        self.entry_url = tk.Entry(entry_inner, textvariable=self.url_var, bg=COLOR_CARD, fg=COLOR_TEXT, 
                                 insertbackground=COLOR_PRIMARY, relief="flat", font=('Segoe UI', 12))
        self.entry_url.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.entry_url.insert(0, "Pegue el enlace aquí...")
        self.entry_url.bind("<FocusIn>", lambda e: self.entry_url.delete(0, tk.END) if self.url_var.get() == "Pegue el enlace aquí..." else None)

        btn_add = tk.Button(entry_inner, text="➕ AÑADIR", command=self.add_to_queue, 
                           bg=COLOR_PRIMARY, fg="#0f172a", font=('Segoe UI', 10, 'bold'), 
                           relief="flat", padx=25, pady=6, activebackground=COLOR_SUCCESS)
        btn_add.pack(side=tk.RIGHT, padx=(10, 0))

    def create_body(self):
        body_frame = tk.Frame(self.root, bg=COLOR_BG, padx=20, pady=5)
        body_frame.pack(fill=tk.BOTH, expand=True)

        columns = ("filename", "size", "progress", "speed", "status")
        self.tree = ttk.Treeview(body_frame, columns=columns, show="headings")
        
        headings = {"filename": "📦 ARCHIVO", "size": "⚖️ PESO", "progress": "📊 PROGRESO", "speed": "🚀 VEL.", "status": "📝 ESTADO"}
        for col, text in headings.items():
            self.tree.heading(col, text=text)
            self.tree.column(col, anchor=tk.CENTER, width=100)

        self.tree.column("filename", width=220, anchor=tk.W)
        self.tree.column("progress", width=180)
        
        scrollbar = ttk.Scrollbar(body_frame, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<Double-1>", self.toggle_pause)
        
        self.tree.tag_configure('terminado', foreground=COLOR_SUCCESS)
        self.tree.tag_configure('pausado', foreground=COLOR_PAUSE)
        self.tree.tag_configure('error', foreground=COLOR_ERROR)
        self.tree.tag_configure('descargando', foreground=COLOR_PRIMARY)
        self.tree.tag_configure('reanudando', foreground="#ff9f43")

        self.context_menu = tk.Menu(self.root, tearoff=0, bg=COLOR_CARD, fg=COLOR_TEXT)
        self.context_menu.add_command(label="▶️ Reanudar / Pausar", command=self.toggle_pause)
        self.context_menu.add_command(label="🗑️ Eliminar", command=self.remove_item)
        self.tree.bind("<Button-3>", lambda e: self.context_menu.post(e.x_root, e.y_root))

    def create_footer(self):
        footer = tk.Frame(self.root, bg=COLOR_CARD, padx=20, pady=12)
        footer.pack(fill=tk.X, side=tk.BOTTOM)
        
        tk.Button(footer, text="📁 DESTINO", command=self.choose_directory, 
                 bg="#334155", fg="white", font=('Segoe UI', 8, 'bold'), 
                 relief="flat", padx=12, pady=4).pack(side=tk.LEFT)

        self.path_display = tk.Label(footer, text=f"{self.dest_folder}", bg=COLOR_CARD, fg=COLOR_TEXT_DIM, font=('Segoe UI', 9))
        self.path_display.pack(side=tk.LEFT, padx=15)

    def save_current_config(self):
        self.config["dest_folder"] = self.dest_folder
        self.config["max_simultaneous"] = self.max_simultaneous.get()
        ConfigManager.save(self.config)

    def choose_directory(self):
        path = filedialog.askdirectory(initialdir=self.dest_folder)
        if path:
            self.dest_folder = path
            self.path_display.config(text=f"{self.dest_folder}")
            self.save_current_config()

    def get_smart_filename(self, url, session):
        """Intenta obtener el nombre y la extensión correcta usando múltiples métodos."""
        name = ""
        try:
            resp = session.head(url, allow_redirects=True, timeout=5)
            
            # 1. Intentar Content-Disposition
            cd = resp.headers.get('content-disposition')
            if cd:
                fname_match = re.findall('filename=["\']?([^"\']+)["\']?', cd)
                if fname_match:
                    name = fname_match[0]
            
            # 2. Si no hay nombre, usar la URL pero limpiar parámetros
            if not name:
                name = url.split("/")[-1].split("?")[0]

            # 3. Validar/Añadir extensión usando Content-Type (MIME)
            content_type = resp.headers.get('content-type', '').split(';')[0].strip()
            if content_type:
                ext = mimetypes.guess_extension(content_type)
                if ext and not name.lower().endswith(ext.lower()):
                    # Caso especial: algunos MIME devuelven .jpe o .htm, corregimos a .jpg o .html
                    corrections = {".jpe": ".jpg", ".htm": ".html"}
                    ext = corrections.get(ext, ext)
                    name += ext

        except:
            name = url.split("/")[-1].split("?")[0]
            
        # Nombre de respaldo final si todo falla
        if not name or len(name) < 3:
            name = f"descarga_{int(time.time())}.bin"
            
        return name

    def add_to_queue(self):
        url = self.url_var.get().strip()
        if not url or url == "Pegue el enlace aquí...": return
        
        # Nombre temporal basado en URL rápida
        temp_name = url.split("/")[-1].split("?")[0] or "Analizando..."
        item_id = self.tree.insert("", tk.END, values=(f"📄 {temp_name}", "---", "0%", "---", "⏳ Esperando"))
        
        self.pause_events[item_id] = threading.Event()
        self.pause_events[item_id].set() 
        self.cancel_flags[item_id] = False
        self.queue.append((url, item_id))
        self.url_var.set("")
        self.process_queue()

    def process_queue(self):
        with self.lock:
            while self.active_count < self.max_simultaneous.get() and self.queue:
                url, item_id = self.queue.pop(0)
                if not self.tree.exists(item_id): continue
                self.active_count += 1
                threading.Thread(target=self.download_engine, args=(url, item_id), daemon=True).start()

    def toggle_pause(self, event=None):
        selected = self.tree.selection()
        if not selected: return
        item_id = selected[0]
        if item_id in self.pause_events:
            status = self.tree.set(item_id, "status")
            if "✅" in status or "❌" in status: return
            if self.pause_events[item_id].is_set():
                self.pause_events[item_id].clear()
                self.update_status(item_id, "status", "⏸️ Pausado", "pausado")
            else:
                self.pause_events[item_id].set()
                self.update_status(item_id, "status", "⬇️ Reanudando", "reanudando")

    def check_disk_space(self, path, required_bytes):
        try:
            total, used, free = shutil.disk_usage(os.path.dirname(os.path.abspath(path)))
            return free > (required_bytes + 1024 * 1024 * 50)
        except: return True

    def get_robust_file_size(self, url, session):
        try:
            resp = session.head(url, timeout=5, allow_redirects=True)
            if 'content-length' in resp.headers:
                return int(resp.headers['content-length'])
        except: pass
        try:
            h = self.headers.copy()
            h['Range'] = 'bytes=0-0'
            resp = session.get(url, headers=h, timeout=5, stream=True)
            if 'content-range' in resp.headers:
                cr = resp.headers['content-range']
                if '/' in cr:
                    s = int(cr.split('/')[-1])
                    resp.close()
                    return s
            resp.close()
        except: pass
        return 0

    def download_engine(self, url, item_id):
        session = requests.Session()
        retry_strategy = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
        session.mount("https://", HTTPAdapter(max_retries=retry_strategy))
        session.mount("http://", HTTPAdapter(max_retries=retry_strategy))
        session.headers.update(self.headers)
        
        attempt = 0
        while attempt < 10:
            try:
                if self.cancel_flags.get(item_id, False): return
                self.update_status(item_id, "status", "📡 Identificando...", "descargando")
                
                # Obtener nombre real con extensión inteligente
                real_name = self.get_smart_filename(url, session)
                self.update_status(item_id, "filename", f"📄 {real_name}")
                filepath = os.path.join(self.dest_folder, real_name)
                
                total_remote = self.get_robust_file_size(url, session)
                self.update_status(item_id, "size", self.format_size(total_remote) if total_remote > 0 else "---")

                if total_remote > 0 and not self.check_disk_space(filepath, total_remote):
                    self.update_status(item_id, "status", "❌ Disco Lleno", "error")
                    break

                local_size = 0
                resume = False
                mode = 'wb'
                
                if os.path.exists(filepath):
                    local_size = os.path.getsize(filepath)
                    if total_remote > 0 and local_size < total_remote:
                        resume = True
                        mode = 'ab'
                        session.headers['Range'] = f"bytes={local_size}-"
                    elif total_remote > 0 and local_size == total_remote:
                        self.update_status(item_id, "status", "✅ Ya existe", "terminado")
                        self.update_status(item_id, "progress", "100% [██████████]")
                        break

                with session.get(url, stream=True, timeout=30) as r:
                    if resume and r.status_code != 206:
                        local_size = 0
                        mode = 'wb'
                    
                    r.raise_for_status()
                    
                    # Verificación final de nombre si cambió durante la descarga real
                    if not resume:
                        actual_ct = r.headers.get('content-type', '').split(';')[0]
                        ext_check = mimetypes.guess_extension(actual_ct)
                        if ext_check and not filepath.lower().endswith(ext_check.lower()):
                             new_name = real_name + ext_check
                             filepath = os.path.join(self.dest_folder, new_name)
                             self.update_status(item_id, "filename", f"📄 {new_name}")

                    if total_remote <= 0:
                        cl = r.headers.get('content-length')
                        if cl: total_remote = int(cl) + local_size
                        self.update_status(item_id, "size", self.format_size(total_remote))

                    downloaded_session = 0
                    start_t = time.time()
                    last_ui = 0
                    
                    self.update_status(item_id, "status", "⬇️ Descargando", "descargando")

                    with open(filepath, mode) as f:
                        for chunk in r.iter_content(chunk_size=131072): # Búfer de 128KB para máxima eficiencia
                            if self.cancel_flags.get(item_id, False): return
                            self.pause_events[item_id].wait()
                            
                            if chunk:
                                f.write(chunk)
                                downloaded_session += len(chunk)
                                now = time.time()
                                if now - last_ui > 0.15: # Reducir frecuencia de refresco UI para ahorrar CPU
                                    self.refresh_ui(item_id, downloaded_session, downloaded_session + local_size, total_remote, start_t)
                                    last_ui = now
                    
                    self.update_status(item_id, "status", "✅ Terminado", "terminado")
                    self.update_status(item_id, "progress", "100% [██████████]")
                    break

            except Exception as e:
                attempt += 1
                if not self.cancel_flags.get(item_id, False):
                    self.update_status(item_id, "status", f"⚠️ Reintento ({attempt}/10)", "error")
                    time.sleep(3)
                else: break
        
        session.close()
        with self.lock: self.active_count -= 1
        self.process_queue()

    def refresh_ui(self, item_id, bytes_session, total_now, total_all, start_t):
        elap = time.time() - start_t
        speed = bytes_session / elap if elap > 0 else 0
        if self.tree.exists(item_id):
            self.root.after(0, lambda: self.tree.set(item_id, "speed", f"{self.format_size(speed)}/s"))
            if total_all > 0:
                p = (total_now / total_all) * 100
                bar = "█" * int(p/10) + "░" * (10 - int(p/10))
                self.root.after(0, lambda: self.tree.set(item_id, "progress", f"{p:.1f}% [{bar}]"))
            else:
                self.root.after(0, lambda: self.tree.set(item_id, "progress", f"📥 {self.format_size(total_now)}"))

    def format_size(self, size):
        if size <= 0: return "0.0B"
        for unit in ['B','KB','MB','GB']:
            if size < 1024: return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def update_status(self, item_id, column, value, tag=None):
        if self.tree.exists(item_id):
            self.root.after(0, lambda: self.tree.set(item_id, column, value))
            if tag: self.root.after(0, lambda: self.tree.item(item_id, tags=(tag,)))

    def clear_all_list(self):
        if not self.tree.get_children(): return
        if messagebox.askyesno("Limpiar", "¿Deseas borrar todo de la lista?"):
            for item_id in self.tree.get_children():
                self.cancel_flags[item_id] = True
                if item_id in self.pause_events: self.pause_events[item_id].set()
            self.queue.clear()
            self.tree.delete(*self.tree.get_children())

    def remove_item(self):
        sel = self.tree.selection()
        if sel:
            item_id = sel[0]
            self.cancel_flags[item_id] = True
            if item_id in self.pause_events: self.pause_events[item_id].set()
            self.tree.delete(sel)

if __name__ == "__main__":
    root = tk.Tk()
    app = DownloadManagerApp(root)
    root.mainloop()
