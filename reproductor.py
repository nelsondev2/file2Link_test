import tkinter as tk
from tkinter import filedialog, messagebox
import os
import subprocess
import threading

# --- Configuración de Estética Profesional ---
COLORS = {
    "bg": "#0f172a",       # Slate 900
    "card": "#1e293b",     # Slate 800
    "accent": "#38bdf8",   # Sky 400
    "text": "#f1f5f9",     # Slate 100
    "text_dim": "#94a3b8", # Slate 400
    "danger": "#ef4444"    # Red 500
}

class TermuxPlayer:
    def __init__(self, root):
        self.root = root
        self.root.title("Termux Audio Pro")
        
        # Ajuste para tamaño típico de móvil en Termux-X11
        # Usualmente se escala, pero 360x740 es un aspecto común de smartphone
        self.root.geometry("360x640")
        self.root.configure(bg=COLORS["bg"])

        self.playlist = []
        self.current_index = -1
        self.process = None  # Para controlar el binario de audio
        
        self.setup_ui()
        
    def setup_ui(self):
        """Crea una interfaz moderna y táctil."""
        # Header
        header = tk.Frame(self.root, bg=COLORS["bg"], pady=20)
        header.pack(fill=tk.X)
        
        tk.Label(
            header, text="REPRODUCTOR", 
            font=("Sans", 18, "bold"), fg=COLORS["accent"], bg=COLORS["bg"]
        ).pack()

        # Visualizador / Portada (Placeholder)
        self.cover_art = tk.Frame(self.root, bg=COLORS["card"], height=200)
        self.cover_art.pack(fill=tk.X, padx=30, pady=10)
        self.cover_art.pack_propagate(False)
        
        self.lbl_now_playing = tk.Label(
            self.cover_art, text="Seleccione una canción",
            font=("Sans", 10, "italic"), fg=COLORS["text_dim"], 
            bg=COLORS["card"], wraplength=250
        )
        self.lbl_now_playing.place(relx=0.5, rely=0.5, anchor=tk.CENTER)

        # Lista de canciones (Scrollable)
        list_frame = tk.Frame(self.root, bg=COLORS["bg"])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        self.listbox = tk.Listbox(
            list_frame, bg=COLORS["bg"], fg=COLORS["text"],
            font=("Sans", 11), borderwidth=0, highlightthickness=0,
            selectbackground=COLORS["accent"], selectforeground=COLORS["bg"],
            activestyle='none'
        )
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = tk.Scrollbar(list_frame, orient="vertical", command=self.listbox.yview)
        # En móviles el scrollbar suele estorbar, pero lo dejamos delgado
        self.listbox.config(yscrollcommand=scrollbar.set)

        # Controles Inferiores (Tamaño grande para dedos)
        controls = tk.Frame(self.root, bg=COLORS["card"], pady=20)
        controls.pack(fill=tk.X, side=tk.BOTTOM)

        btn_font = ("Sans", 12, "bold")
        
        # Grid para botones táctiles
        btn_add = tk.Button(
            controls, text="➕", font=btn_font, bg=COLORS["card"], 
            fg=COLORS["text"], borderwidth=0, command=self.add_music
        )
        btn_add.grid(row=0, column=0, sticky="nsew")

        self.btn_play = tk.Button(
            controls, text="▶ REPRODUCIR", font=btn_font, bg=COLORS["accent"], 
            fg=COLORS["bg"], borderwidth=0, padx=20, command=self.play_selected
        )
        self.btn_play.grid(row=0, column=1, sticky="nsew", padx=10)

        btn_stop = tk.Button(
            controls, text="⏹", font=btn_font, bg=COLORS["card"], 
            fg=COLORS["danger"], borderwidth=0, command=self.stop_music
        )
        btn_stop.grid(row=0, column=2, sticky="nsew")

        controls.grid_columnconfigure(0, weight=1)
        controls.grid_columnconfigure(1, weight=2)
        controls.grid_columnconfigure(2, weight=1)

    def add_music(self):
        files = filedialog.askopenfilenames(
            title="Abrir Audio",
            filetypes=(("Archivos de Audio", "*.mp3 *.wav *.ogg *.flac"), ("Todos", "*.*"))
        )
        for f in files:
            if f not in self.playlist:
                self.playlist.append(f)
                self.listbox.insert(tk.END, f" 🎵 {os.path.basename(f)}")

    def play_audio_file(self, path):
        """
        Lógica para Termux: Intenta usar 'mpv' o 'ffplay' (ligeros y comunes en Linux).
        Estos binarios manejan el hardware de audio de Android mediante ALSA/OpenSL ES.
        """
        self.stop_music()
        
        # Comando para reproducir sin ventana de video y de forma silenciosa en consola
        # 'mpv' es excelente en Termux: pkg install mpv
        cmd = ["mpv", "--no-video", "--no-terminal", path]
        
        try:
            self.process = subprocess.Popen(cmd)
        except FileNotFoundError:
            # Fallback a ffplay si mpv no está: pkg install ffmpeg
            try:
                cmd = ["ffplay", "-nodisp", "-autoexit", path]
                self.process = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
            except Exception as e:
                messagebox.showerror("Error", "No se encontró 'mpv' o 'ffplay'. Instálelos con: pkg install mpv")

    def play_selected(self):
        selected = self.listbox.curselection()
        if not selected:
            return
            
        index = selected[0]
        file_path = self.playlist[index]
        self.current_index = index
        
        self.lbl_now_playing.config(text=os.path.basename(file_path), fg=COLORS["accent"])
        
        # Ejecutar en un hilo para no congelar la UI de Tkinter
        threading.Thread(target=self.play_audio_file, args=(file_path,), daemon=True).start()

    def stop_music(self):
        if self.process:
            self.process.terminate()
            self.process = None
        self.lbl_now_playing.config(text="Reproducción detenida", fg=COLORS["text_dim"])

if __name__ == "__main__":
    # Iniciar la app
    root = tk.Tk()
    
    # Intentar detectar si estamos en un entorno X11
    if "DISPLAY" not in os.environ:
        print("Error: No se detectó una pantalla X11. Asegúrate de iniciar Termux-X11.")
    
    app = TermuxPlayer(root)
    root.mainloop()
