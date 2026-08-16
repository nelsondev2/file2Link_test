import os
import urllib.parse
import hashlib
import json
import time
import logging
import re
import unicodedata
from config import BASE_DIR, RENDER_DOMAIN

logger = logging.getLogger(__name__)


class FileService:
    def __init__(self):
        self.file_mappings = {}
        self.metadata_file = "file_metadata.json"
        self._load_metadata()

    # ── Metadata ────────────────────────────────

    def _load_metadata(self):
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
        except Exception as e:
            logger.error(f"Error cargando metadata: {e}")
            self.metadata = {}

    def _save_metadata(self):
        try:
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")

    # ── Numeracion ──────────────────────────────

    def get_next_file_number(self, user_id, file_type="downloads"):
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}

        next_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1
        self._save_metadata()
        return next_num

    # ── Sanitizacion ────────────────────────────

    def sanitize_filename(self, filename):
        """Limpia el nombre de archivo para que sea seguro en disco y URL."""
        filename = unicodedata.normalize("NFD", filename)
        filename = "".join(
            c for c in filename if unicodedata.category(c) != "Mn"
        )
        filename = filename.encode("ascii", "ignore").decode("ascii")

        name, ext = os.path.splitext(filename)
        ext = re.sub(r"[^\w.]", "", ext)
        name = re.sub(r"[^\w.\-]", "_", name)
        name = re.sub(r"_+", "_", name)
        name = name.strip("_").strip(".")

        if not name:
            name = "archivo"
        if len(name) > 100:
            name = name[:100]

        return name + ext

    # ── URLs ────────────────────────────────────

    def filename_to_url(self, stored_filename):
        return urllib.parse.quote(stored_filename, safe="")

    def create_download_url(self, user_id, filename):
        return f"{RENDER_DOMAIN}/storage/{user_id}/downloads/{self.filename_to_url(filename)}"

    def create_packed_url(self, user_id, filename):
        return f"{RENDER_DOMAIN}/storage/{user_id}/packed/{self.filename_to_url(filename)}"

    # ── Formato ─────────────────────────────────

    @staticmethod
    def format_bytes(size):
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    # ── Directorios ─────────────────────────────

    def get_user_directory(self, user_id, file_type="downloads"):
        user_dir = os.path.join(BASE_DIR, str(user_id), file_type)
        os.makedirs(user_dir, exist_ok=True)
        return user_dir

    def get_user_storage_usage(self, user_id):
        total_size = 0
        for file_type in ("downloads", "packed"):
            user_dir = self.get_user_directory(user_id, file_type)
            if not os.path.exists(user_dir):
                continue
            for f in os.listdir(user_dir):
                fp = os.path.join(user_dir, f)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
        return total_size

    # ── Hash ────────────────────────────────────

    def create_file_hash(self, user_id, filename):
        data = f"{user_id}_{filename}_{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    # ── Listado ─────────────────────────────────

    def list_user_files(self, user_id, file_type="downloads"):
        user_dir = self.get_user_directory(user_id, file_type)
        if not os.path.exists(user_dir):
            return []

        files = []
        user_key = f"{user_id}_{file_type}"

        if user_key in self.metadata:
            existing = []
            for file_num, file_data in self.metadata[user_key]["files"].items():
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.exists(file_path):
                    existing.append((int(file_num), file_data))

            existing.sort(key=lambda x: x[0])

            for file_number, file_data in existing:
                file_path = os.path.join(user_dir, file_data["stored_name"])
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    if file_type == "downloads":
                        url = self.create_download_url(user_id, file_data["stored_name"])
                    else:
                        url = self.create_packed_url(user_id, file_data["stored_name"])

                    files.append(
                        {
                            "number": file_number,
                            "name": file_data["original_name"],
                            "stored_name": file_data["stored_name"],
                            "size": size,
                            "size_mb": size / (1024 * 1024),
                            "url": url,
                            "file_type": file_type,
                        }
                    )

        return files

    # ── Registro ────────────────────────────────

    def register_file(self, user_id, original_name, stored_name, file_type="downloads"):
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            self.metadata[user_key] = {"next_number": 1, "files": {}}

        file_num = self.metadata[user_key]["next_number"]
        self.metadata[user_key]["next_number"] += 1

        self.metadata[user_key]["files"][str(file_num)] = {
            "original_name": original_name,
            "stored_name": stored_name,
            "registered_at": time.time(),
        }
        self._save_metadata()

        logger.info(f"Archivo registrado: #{file_num} - {original_name} (user {user_id})")
        return file_num

    # ── Busqueda ────────────────────────────────

    def get_file_by_number(self, user_id, file_number, file_type="downloads"):
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return None

        file_data = self.metadata[user_key]["files"].get(str(file_number))
        if not file_data:
            return None

        user_dir = self.get_user_directory(user_id, file_type)
        file_path = os.path.join(user_dir, file_data["stored_name"])

        if not os.path.exists(file_path):
            return None

        if file_type == "downloads":
            url = self.create_download_url(user_id, file_data["stored_name"])
        else:
            url = self.create_packed_url(user_id, file_data["stored_name"])

        return {
            "number": file_number,
            "original_name": file_data["original_name"],
            "stored_name": file_data["stored_name"],
            "path": file_path,
            "url": url,
            "file_type": file_type,
        }

    def get_original_filename(self, user_id, stored_filename, file_type="downloads"):
        user_key = f"{user_id}_{file_type}"
        if user_key not in self.metadata:
            return stored_filename

        for file_data in self.metadata[user_key]["files"].values():
            if file_data["stored_name"] == stored_filename:
                return file_data["original_name"]

        return stored_filename

    # ── Renombrar ───────────────────────────────

    def rename_file(self, user_id, file_number, new_name, file_type="downloads"):
        try:
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado", None

            file_data = self.metadata[user_key]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado", None

            user_dir = self.get_user_directory(user_id, file_type)
            old_path = os.path.join(user_dir, file_data["stored_name"])

            if not os.path.exists(old_path):
                return False, "Archivo fisico no encontrado", None

            new_name = self.sanitize_filename(new_name)
            _, ext = os.path.splitext(file_data["stored_name"])
            new_stored_name = new_name + ext

            counter = 1
            base_new = new_stored_name
            while os.path.exists(os.path.join(user_dir, new_stored_name)):
                name_no_ext = os.path.splitext(base_new)[0]
                ext = os.path.splitext(base_new)[1]
                new_stored_name = f"{name_no_ext}_{counter}{ext}"
                counter += 1

            new_path = os.path.join(user_dir, new_stored_name)
            os.rename(old_path, new_path)

            file_data["original_name"] = new_name
            file_data["stored_name"] = new_stored_name
            self._save_metadata()

            if file_type == "downloads":
                new_url = self.create_download_url(user_id, new_stored_name)
            else:
                new_url = self.create_packed_url(user_id, new_stored_name)

            return True, f"Archivo renombrado a: {new_name}", new_url

        except Exception as e:
            logger.error(f"Error renombrando archivo: {e}")
            return False, f"Error al renombrar: {str(e)}", None

    # ── Eliminar ────────────────────────────────

    def delete_file_by_number(self, user_id, file_number, file_type="downloads"):
        try:
            user_key = f"{user_id}_{file_type}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado"

            file_data = self.metadata[user_key]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado"

            user_dir = self.get_user_directory(user_id, file_type)
            file_path = os.path.join(user_dir, file_data["stored_name"])

            if os.path.exists(file_path):
                os.remove(file_path)

            del self.metadata[user_key]["files"][str(file_number)]

            # Reasignar numeros consecutivos
            remaining = sorted(
                self.metadata[user_key]["files"].items(), key=lambda x: int(x[0])
            )
            self.metadata[user_key]["files"] = {}
            new_number = 1
            for _, data in remaining:
                self.metadata[user_key]["files"][str(new_number)] = data
                new_number += 1
            self.metadata[user_key]["next_number"] = new_number
            self._save_metadata()

            return True, f"Archivo #{file_number} eliminado correctamente"

        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False, f"Error al eliminar: {str(e)}"

    # ── Vaciar carpeta ──────────────────────────

    def delete_all_files(self, user_id, file_type="downloads"):
        try:
            user_dir = self.get_user_directory(user_id, file_type)

            if not os.path.exists(user_dir):
                return False, f"No hay archivos de {file_type} para eliminar"

            files = os.listdir(user_dir)
            if not files:
                return False, f"No hay archivos de {file_type} para eliminar"

            deleted_count = 0
            for filename in files:
                file_path = os.path.join(user_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1

            user_key = f"{user_id}_{file_type}"
            if user_key in self.metadata:
                self.metadata[user_key] = {"next_number": 1, "files": {}}
                self._save_metadata()

            return True, f"Se eliminaron {deleted_count} archivos de {file_type}"

        except Exception as e:
            logger.error(f"Error eliminando archivos: {e}")
            return False, f"Error al eliminar: {str(e)}"


file_service = FileService()
