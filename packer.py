"""
Servicio de empaquetado de archivos en ZIP.

Soporta dos modos:
  - ZIP único   : todos los archivos en un solo .zip
  - ZIP partido : el ZIP se divide en partes de tamaño fijo (.zip.001, .zip.002 …)

Las partes se pueden reunir con:  cat archivo.zip.* > archivo.zip  &&  unzip archivo.zip
"""
from __future__ import annotations

import logging
import os
import time
import zipfile
from dataclasses import dataclass
from typing import Optional

from config import MAX_PART_SIZE_MB
from storage import storage
from system_monitor import monitor

logger = logging.getLogger(__name__)


@dataclass
class PackResult:
    filename: str
    url: str
    size_mb: float
    total_source_files: int = 0   # solo informativo en la primera parte


class PackingError(Exception):
    pass


class Packer:
    def pack(
        self, user_id: int, split_mb: Optional[int] = None
    ) -> tuple[list[PackResult], str]:
        """
        Empaqueta los archivos de descarga del usuario.

        Parámetros
        ----------
        user_id  : ID del usuario
        split_mb : si se indica, el ZIP se divide en partes de ese tamaño

        Devuelve
        --------
        (lista de PackResult, mensaje de estado)
        """
        ok, reason = monitor.request_slot()
        if not ok:
            raise PackingError(reason)

        try:
            return self._run(user_id, split_mb)
        finally:
            monitor.release_slot()

    # ── Lógica interna ─────────────────────────────────────────────────────────

    def _run(
        self, user_id: int, split_mb: Optional[int]
    ) -> tuple[list[PackResult], str]:
        src_dir = storage.user_directory(user_id, "downloads")
        files = [
            f for f in os.listdir(src_dir)
            if os.path.isfile(os.path.join(src_dir, f))
        ]
        if not files:
            raise PackingError("No tienes archivos para empaquetar.")

        dst_dir = storage.user_directory(user_id, "packed")
        base = f"pack_{int(time.time())}"

        if split_mb:
            return self._split_zip(user_id, src_dir, dst_dir, base, files, split_mb)
        else:
            return self._single_zip(user_id, src_dir, dst_dir, base, files)

    def _create_zip(self, src_dir: str, files: list[str], zip_path: str) -> None:
        """Crea un ZIP sin compresión con todos los archivos."""
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED) as zf:
            for fname in files:
                fpath = os.path.join(src_dir, fname)
                try:
                    zf.write(fpath, fname)
                except Exception as exc:
                    logger.warning("No se pudo agregar %s al ZIP: %s", fname, exc)

    def _single_zip(
        self,
        user_id: int,
        src_dir: str,
        dst_dir: str,
        base: str,
        files: list[str],
    ) -> tuple[list[PackResult], str]:
        zip_name = f"{base}.zip"
        zip_path = os.path.join(dst_dir, zip_name)

        logger.info("Creando ZIP con %d archivos…", len(files))
        self._create_zip(src_dir, files, zip_path)

        size_mb = os.path.getsize(zip_path) / (1024 * 1024)
        file_num = storage.register_file(user_id, zip_name, zip_name, "packed")
        url = storage._build_url(user_id, "packed", zip_name)

        result = PackResult(
            filename=zip_name,
            url=url,
            size_mb=size_mb,
            total_source_files=len(files),
        )
        return [result], f"Listo: {len(files)} archivos → {size_mb:.1f} MB"

    def _split_zip(
        self,
        user_id: int,
        src_dir: str,
        dst_dir: str,
        base: str,
        files: list[str],
        split_mb: int,
    ) -> tuple[list[PackResult], str]:
        cap = min(split_mb, MAX_PART_SIZE_MB) * 1024 * 1024
        tmp_path = os.path.join(dst_dir, f"_tmp_{base}.zip")

        try:
            logger.info("Creando ZIP temporal con %d archivos…", len(files))
            self._create_zip(src_dir, files, tmp_path)

            parts: list[PackResult] = []
            with open(tmp_path, "rb") as fh:
                part_num = 0
                while True:
                    chunk = fh.read(cap)
                    if not chunk:
                        break
                    part_num += 1
                    part_name = f"{base}.zip.{part_num:03d}"
                    part_path = os.path.join(dst_dir, part_name)

                    with open(part_path, "wb") as pf:
                        pf.write(chunk)

                    size_mb = len(chunk) / (1024 * 1024)
                    storage.register_file(user_id, part_name, part_name, "packed")
                    url = storage._build_url(user_id, "packed", part_name)

                    parts.append(
                        PackResult(
                            filename=part_name,
                            url=url,
                            size_mb=size_mb,
                            total_source_files=len(files) if part_num == 1 else 0,
                        )
                    )
                    logger.info("Parte %d creada: %.1f MB", part_num, size_mb)

            self._write_parts_list(user_id, dst_dir, base, parts, len(files))

            total_mb = sum(p.size_mb for p in parts)
            return parts, f"Listo: {len(files)} archivos → {len(parts)} partes ({total_mb:.1f} MB)"

        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def _write_parts_list(
        self,
        user_id: int,
        dst_dir: str,
        base: str,
        parts: list[PackResult],
        total_files: int,
    ) -> None:
        """Crea un archivo .txt con la lista de enlaces de las partes."""
        list_name = f"{base}_lista.txt"
        list_path = os.path.join(dst_dir, list_name)

        lines = [
            f"Archivos originales empaquetados: {total_files}",
            f"Número de partes: {len(parts)}",
            "",
            "Para unir las partes y extraer (Linux/Mac):",
            f"  cat {base}.zip.* > {base}.zip && unzip {base}.zip",
            "",
            "Para unir las partes (Windows, con 7-Zip):",
            f"  Abrir {base}.zip.001 con 7-Zip",
            "",
            "─" * 50,
            "",
        ]
        for i, p in enumerate(parts, 1):
            lines.append(f"Parte {i:03d}  ({p.size_mb:.1f} MB)")
            lines.append(f"  {p.url}")
            lines.append("")

        with open(list_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

        storage.register_file(user_id, list_name, list_name, "packed")


packer = Packer()
