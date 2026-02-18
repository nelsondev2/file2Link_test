"""
Servicio de almacenamiento de archivos.

Gestiona el sistema de archivos y la metadata asociada (nombres originales,
numeración persistente, URLs de descarga).  Todas las operaciones sobre
metadata están protegidas con un RLock para evitar condiciones de carrera.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Optional

from config import METADATA_FILE, PUBLIC_DOMAIN, STORAGE_DIR

logger = logging.getLogger(__name__)


# ── Tipos de datos ─────────────────────────────────────────────────────────────

@dataclass
class FileRecord:
    number: int
    original_name: str
    stored_name: str
    folder: str          # "downloads" | "packed"
    registered_at: float = field(default_factory=time.time)


@dataclass
class FileInfo:
    number: int
    name: str
    stored_name: str
    size_bytes: int
    size_mb: float
    url: str
    folder: str


# ── Servicio principal ─────────────────────────────────────────────────────────

class StorageService:
    """Gestiona archivos y metadata de usuarios de forma thread-safe."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        os.makedirs(STORAGE_DIR, exist_ok=True)
        self._db: dict = self._load()

    # ── Persistencia ──────────────────────────────────────────────────────────

    def _load(self) -> dict:
        if not os.path.exists(METADATA_FILE):
            return {}
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.error("Error cargando metadata: %s", exc)
            return {}

    def _save(self) -> None:
        """Guarda metadata en disco. Debe llamarse con el lock adquirido."""
        try:
            os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
            tmp = METADATA_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._db, f, ensure_ascii=False, indent=2)
            os.replace(tmp, METADATA_FILE)
        except Exception as exc:
            logger.error("Error guardando metadata: %s", exc)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _user_key(self, user_id: int, folder: str) -> str:
        return f"{user_id}_{folder}"

    def _ensure_user_section(self, user_id: int, folder: str) -> dict:
        key = self._user_key(user_id, folder)
        if key not in self._db:
            self._db[key] = {"next_number": 1, "files": {}}
        return self._db[key]

    def _build_url(self, user_id: int, folder: str, stored_name: str) -> str:
        safe = urllib.parse.quote(self.sanitize_filename(stored_name))
        return f"{PUBLIC_DOMAIN}/storage/{user_id}/{folder}/{safe}"

    # ── Directorio de usuario ─────────────────────────────────────────────────

    def user_directory(self, user_id: int, folder: str) -> str:
        path = os.path.join(STORAGE_DIR, str(user_id), folder)
        os.makedirs(path, exist_ok=True)
        return path

    # ── Nombre de archivo ─────────────────────────────────────────────────────

    @staticmethod
    def sanitize_filename(name: str) -> str:
        for char in r'<>:"/\|?*':
            name = name.replace(char, "_")
        if len(name) > 100:
            base, ext = os.path.splitext(name)
            name = base[: 100 - len(ext)] + ext
        return name

    def unique_stored_name(self, user_dir: str, filename: str) -> str:
        """Devuelve un nombre de archivo único dentro del directorio."""
        base, ext = os.path.splitext(filename)
        candidate = filename
        counter = 1
        while os.path.exists(os.path.join(user_dir, candidate)):
            candidate = f"{base}_{counter}{ext}"
            counter += 1
        return candidate

    # ── Registro de archivos ──────────────────────────────────────────────────

    def register_file(
        self,
        user_id: int,
        original_name: str,
        stored_name: str,
        folder: str,
    ) -> int:
        """Registra un archivo y devuelve su número persistente."""
        with self._lock:
            section = self._ensure_user_section(user_id, folder)
            num = section["next_number"]
            section["next_number"] += 1
            section["files"][str(num)] = {
                "original_name": original_name,
                "stored_name": stored_name,
                "registered_at": time.time(),
            }
            self._save()
            logger.debug("Archivo registrado #%d – %s (%s/%s)", num, original_name, user_id, folder)
            return num

    # ── Listado ───────────────────────────────────────────────────────────────

    def list_files(self, user_id: int, folder: str) -> list[FileInfo]:
        """Lista archivos del usuario ordenados por número."""
        with self._lock:
            section = self._db.get(self._user_key(user_id, folder), {})
            raw_files: dict = section.get("files", {})

        user_dir = self.user_directory(user_id, folder)
        result: list[FileInfo] = []

        for num_str, data in sorted(raw_files.items(), key=lambda x: int(x[0])):
            stored = data["stored_name"]
            path = os.path.join(user_dir, stored)
            if not os.path.isfile(path):
                continue
            size = os.path.getsize(path)
            result.append(
                FileInfo(
                    number=int(num_str),
                    name=data["original_name"],
                    stored_name=stored,
                    size_bytes=size,
                    size_mb=size / (1024 * 1024),
                    url=self._build_url(user_id, folder, stored),
                    folder=folder,
                )
            )
        return result

    def get_file(self, user_id: int, number: int, folder: str) -> Optional[FileInfo]:
        """Obtiene un archivo por número. Devuelve None si no existe."""
        with self._lock:
            section = self._db.get(self._user_key(user_id, folder), {})
            data = section.get("files", {}).get(str(number))

        if not data:
            return None

        user_dir = self.user_directory(user_id, folder)
        path = os.path.join(user_dir, data["stored_name"])
        if not os.path.isfile(path):
            return None

        size = os.path.getsize(path)
        return FileInfo(
            number=number,
            name=data["original_name"],
            stored_name=data["stored_name"],
            size_bytes=size,
            size_mb=size / (1024 * 1024),
            url=self._build_url(user_id, folder, data["stored_name"]),
            folder=folder,
        )

    def get_original_name(self, user_id: int, stored_name: str, folder: str) -> str:
        """Devuelve el nombre original a partir del nombre almacenado."""
        with self._lock:
            section = self._db.get(self._user_key(user_id, folder), {})
            for data in section.get("files", {}).values():
                if data["stored_name"] == stored_name:
                    return data["original_name"]
        return stored_name

    # ── Modificación ──────────────────────────────────────────────────────────

    def rename_file(
        self, user_id: int, number: int, new_name: str, folder: str
    ) -> tuple[bool, str, Optional[str]]:
        """
        Renombra un archivo en disco y en metadata.
        Devuelve (éxito, mensaje, nueva_url).
        """
        info = self.get_file(user_id, number, folder)
        if not info:
            return False, "No encontré ese archivo.", None

        new_name = self.sanitize_filename(new_name)
        _, ext = os.path.splitext(info.stored_name)
        new_stored = self.unique_stored_name(
            self.user_directory(user_id, folder), new_name + ext
        )

        old_path = os.path.join(self.user_directory(user_id, folder), info.stored_name)
        new_path = os.path.join(self.user_directory(user_id, folder), new_stored)

        try:
            os.rename(old_path, new_path)
        except OSError as exc:
            logger.error("Error al renombrar archivo: %s", exc)
            return False, "No se pudo renombrar el archivo.", None

        with self._lock:
            section = self._db[self._user_key(user_id, folder)]
            section["files"][str(number)]["original_name"] = new_name
            section["files"][str(number)]["stored_name"] = new_stored
            self._save()

        new_url = self._build_url(user_id, folder, new_stored)
        return True, f"Archivo renombrado a «{new_name}»", new_url

    def delete_file(
        self, user_id: int, number: int, folder: str
    ) -> tuple[bool, str]:
        """
        Elimina un archivo en disco y en metadata.
        Renumera los archivos restantes para mantener secuencia continua.
        """
        info = self.get_file(user_id, number, folder)
        if not info:
            return False, "No encontré ese archivo."

        file_path = os.path.join(self.user_directory(user_id, folder), info.stored_name)
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except OSError as exc:
            logger.error("Error al eliminar archivo: %s", exc)
            return False, "No se pudo eliminar el archivo."

        with self._lock:
            key = self._user_key(user_id, folder)
            section = self._db[key]
            section["files"].pop(str(number), None)

            # Renumerar de forma consecutiva
            remaining = sorted(section["files"].items(), key=lambda x: int(x[0]))
            section["files"] = {str(i + 1): data for i, (_, data) in enumerate(remaining)}
            section["next_number"] = len(remaining) + 1
            self._save()

        return True, f"«{info.name}» eliminado correctamente."

    def delete_all_files(self, user_id: int, folder: str) -> tuple[bool, str]:
        """Elimina todos los archivos de una carpeta."""
        user_dir = self.user_directory(user_id, folder)
        deleted = 0

        try:
            for fname in os.listdir(user_dir):
                fpath = os.path.join(user_dir, fname)
                if os.path.isfile(fpath):
                    os.remove(fpath)
                    deleted += 1
        except OSError as exc:
            logger.error("Error al vaciar carpeta: %s", exc)
            return False, "Hubo un problema vaciando la carpeta."

        with self._lock:
            key = self._user_key(user_id, folder)
            self._db[key] = {"next_number": 1, "files": {}}
            self._save()

        if deleted == 0:
            return False, "La carpeta ya estaba vacía."
        return True, f"Se eliminaron {deleted} archivo{'s' if deleted != 1 else ''}."

    # ── Espacio de almacenamiento ─────────────────────────────────────────────

    def storage_used(self, user_id: int) -> int:
        """Devuelve el total de bytes usados por el usuario."""
        total = 0
        for folder in ("downloads", "packed"):
            d = os.path.join(STORAGE_DIR, str(user_id), folder)
            if not os.path.isdir(d):
                continue
            for fname in os.listdir(d):
                fp = os.path.join(d, fname)
                if os.path.isfile(fp):
                    total += os.path.getsize(fp)
        return total

    # ── Helpers de formato ────────────────────────────────────────────────────

    @staticmethod
    def format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


storage = StorageService()
