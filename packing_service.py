# packing_service.py — empaquetado rápido (ZIP sin compresión)
import os
import zipfile
import time
import logging
from typing import List, Tuple, Optional, Dict, Any

logger = logging.getLogger("packing_service")

class PackingService:
    def __init__(self, file_service, max_part_size_mb: int = 100):
        self.file_service = file_service
        self.max_part_size_mb = max_part_size_mb

    def pack_folder(self, user_id: str, split_size_mb: Optional[int] = None) -> Tuple[Optional[List[Dict[str,Any]]], str]:
        """
        Crea ZIP sin compresión. Si split_size_mb se proporciona, divide en partes.
        Retorna (files_list, message)
        """
        try:
            user_dir = self.file_service.get_user_directory(user_id, "downloads")
            packed_dir = self.file_service.get_user_directory(user_id, "packed")
            os.makedirs(packed_dir, exist_ok=True)

            files = [f for f in os.listdir(user_dir) if os.path.isfile(os.path.join(user_dir, f))]
            if not files:
                return None, "No hay archivos para empaquetar."

            timestamp = int(time.time())
            base = f"packed_{timestamp}"
            zip_path = os.path.join(packed_dir, f"{base}.zip")

            # Crear ZIP sin compresión (ZIP_STORED)
            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as zf:
                for fname in files:
                    zf.write(os.path.join(user_dir, fname), arcname=fname)

            size_mb = os.path.getsize(zip_path) / (1024*1024)
            # Registrar
            num = self.file_service.register_file(user_id, f"{base}.zip", f"{base}.zip", "packed")
            url = self.file_service.create_download_url(user_id, f"{base}.zip")
            result = [{
                "number": num,
                "filename": f"{base}.zip",
                "url": url,
                "size_mb": size_mb
            }]

            # Si se solicita dividir en partes
            if split_size_mb and split_size_mb > 0:
                parts = []
                part_size = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
                with open(zip_path, "rb") as zf:
                    idx = 1
                    while True:
                        chunk = zf.read(part_size)
                        if not chunk:
                            break
                        part_name = f"{base}.zip.{idx:03d}"
                        part_path = os.path.join(packed_dir, part_name)
                        with open(part_path, "wb") as pf:
                            pf.write(chunk)
                        pnum = self.file_service.register_file(user_id, part_name, part_name, "packed")
                        parts.append({
                            "number": pnum,
                            "filename": part_name,
                            "url": self.file_service.create_download_url(user_id, part_name),
                            "size_mb": os.path.getsize(part_path) / (1024*1024)
                        })
                        idx += 1
                # eliminar zip original
                os.remove(zip_path)
                return parts, f"Empaquetado en {len(parts)} partes."
            return result, f"Empaquetado completado: {size_mb:.1f} MB"
        except Exception:
            logger.exception("Error en pack_folder")
            return None, "Error empaquetando archivos."