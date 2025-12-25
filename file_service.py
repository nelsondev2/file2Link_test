# file_service.py — gestión simple y segura de archivos y metadata
import os
import json
import time
import hashlib
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger("file_service")

class FileService:
    def __init__(self, base_dir: str = "storage", metadata_file: str = "file_metadata.json"):
        self.base_dir = base_dir
        self.metadata_file = metadata_file
        self.metadata: Dict[str, Any] = {}
        self._load_metadata()
        os.makedirs(self.base_dir, exist_ok=True)

    def _load_metadata(self):
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
        except Exception:
            logger.exception("Error cargando metadata, inicializando vacía")
            self.metadata = {}

    def _save_metadata(self):
        tmp = f"{self.metadata_file}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        os.replace(tmp, self.metadata_file)

    def get_user_directory(self, user_id: str, file_type: str = "downloads") -> str:
        user_dir = os.path.join(self.base_dir, user_id, file_type)
        os.makedirs(user_dir, exist_ok=True)
        # test write
        test = os.path.join(user_dir, ".w")
        with open(test, "w") as f:
            f.write("ok")
        os.remove(test)
        return user_dir

    def sanitize_filename(self, filename: str) -> str:
        if not filename:
            filename = f"file_{int(time.time())}"
        invalid = '<>:"/\\|?*'
        for c in invalid:
            filename = filename.replace(c, "_")
        return filename.strip()[:200]

    def create_download_url(self, user_id: str, filename: str) -> str:
        # RENDER_DOMAIN opcional
        domain = os.getenv("RENDER_DOMAIN", "https://nelson-file2link.onrender.com")
        safe = filename.replace(" ", "%20")
        return f"{domain}/storage/{user_id}/downloads/{safe}"

    def register_file(self, user_id: str, original_name: str, stored_name: str, file_type: str = "downloads") -> int:
        key = f"{user_id}_{file_type}"
        if key not in self.metadata:
            self.metadata[key] = {"next_number": 1, "files": {}}
        num = self.metadata[key]["next_number"]
        self.metadata[key]["files"][str(num)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time()
        }
        self.metadata[key]["next_number"] += 1
        self._save_metadata()
        logger.info(f"Archivo registrado: user={user_id} #{num} {original_name}")
        return num

    def list_user_files(self, user_id: str, file_type: str = "downloads") -> List[Dict[str, Any]]:
        key = f"{user_id}_{file_type}"
        if key not in self.metadata:
            return []
        files = []
        user_dir = self.get_user_directory(user_id, file_type)
        for num_str, data in sorted(self.metadata[key]["files"].items(), key=lambda x: int(x[0])):
            stored = data["stored_name"]
            path = os.path.join(user_dir, stored)
            if os.path.exists(path):
                files.append({
                    "number": int(num_str),
                    "name": data["original_name"],
                    "stored_name": stored,
                    "size": os.path.getsize(path),
                    "url": self.create_download_url(user_id, stored)
                })
        return files

    def format_bytes(self, size: int) -> str:
        if size < 1024:
            return f"{size} B"
        for unit in ["KB","MB","GB","TB"]:
            size /= 1024.0
            if size < 1024:
                return f"{size:.2f} {unit}"
        return f"{size:.2f} PB"