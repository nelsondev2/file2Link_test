import os
import logging
import time
import zipfile
from config import BASE_DIR, MAX_PART_SIZE_MB
from load_manager import load_manager
from file_service import file_service

logger = logging.getLogger(__name__)


class PackingService:
    def __init__(self):
        self.max_part_size_mb = MAX_PART_SIZE_MB

    def pack_folder(self, user_id, split_size_mb=None):
        """Empaqueta archivos en ZIP, opcionalmente dividido en partes."""
        try:
            can_start, message = load_manager.can_start_process()
            if not can_start:
                return None, message

            try:
                user_dir = file_service.get_user_directory(user_id, "downloads")
                if not os.path.exists(user_dir):
                    return None, "No tienes archivos para empaquetar"

                files = [
                    f for f in os.listdir(user_dir)
                    if os.path.isfile(os.path.join(user_dir, f))
                ]
                if not files:
                    return None, "No tienes archivos para empaquetar"

                packed_dir = file_service.get_user_directory(user_id, "packed")
                os.makedirs(packed_dir, exist_ok=True)

                timestamp = int(time.time())
                base_filename = f"packed_{timestamp}"

                if split_size_mb:
                    result = self._pack_and_split(
                        user_id, user_dir, packed_dir, base_filename, split_size_mb, files
                    )
                else:
                    result = self._pack_single(
                        user_id, user_dir, packed_dir, base_filename, files
                    )
                return result

            finally:
                load_manager.finish_process()

        except Exception as e:
            load_manager.finish_process()
            logger.error(f"Error en empaquetado: {e}")
            return None, f"Error al empaquetar: {str(e)}"

    def _pack_single(self, user_id, user_dir, packed_dir, base_filename, files):
        """Crea un unico archivo ZIP sin compresion."""
        output_file = os.path.join(packed_dir, f"{base_filename}.zip")

        try:
            logger.info(f"Creando ZIP con {len(files)} archivos...")
            with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_STORED) as zf:
                for filename in files:
                    try:
                        zf.write(os.path.join(user_dir, filename), filename)
                    except Exception as e:
                        logger.error(f"Error agregando {filename}: {e}")

            size_mb = os.path.getsize(output_file) / (1024 * 1024)
            file_num = file_service.register_file(
                user_id, f"{base_filename}.zip", f"{base_filename}.zip", "packed"
            )
            url = file_service.create_packed_url(user_id, f"{base_filename}.zip")

            return [
                {
                    "number": file_num,
                    "filename": f"{base_filename}.zip",
                    "url": url,
                    "size_mb": size_mb,
                    "total_files": len(files),
                }
            ], f"Empaquetado completado: {len(files)} archivos, {size_mb:.1f} MB"

        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            raise e

    def _pack_and_split(self, user_id, user_dir, packed_dir, base_filename, split_size_mb, files):
        """Crea ZIP y lo divide en partes."""
        split_bytes = min(split_size_mb, self.max_part_size_mb) * 1024 * 1024
        temp_zip = os.path.join(packed_dir, f"temp_{base_filename}.zip")

        try:
            logger.info(f"Creando ZIP temporal con {len(files)} archivos...")
            with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_STORED) as zf:
                for filename in files:
                    try:
                        zf.write(os.path.join(user_dir, filename), filename)
                    except Exception as e:
                        logger.error(f"Error agregando {filename}: {e}")

            # Dividir en partes
            parts = []
            part_num = 1
            with open(temp_zip, "rb") as zf:
                while True:
                    part_name = f"{base_filename}.zip.{part_num:03d}"
                    part_path = os.path.join(packed_dir, part_name)
                    chunk = zf.read(split_bytes)
                    if not chunk:
                        break

                    with open(part_path, "wb") as pf:
                        pf.write(chunk)

                    part_mb = len(chunk) / (1024 * 1024)
                    file_num = file_service.register_file(user_id, part_name, part_name, "packed")
                    url = file_service.create_packed_url(user_id, part_name)

                    parts.append({
                        "number": file_num,
                        "filename": part_name,
                        "url": url,
                        "size_mb": part_mb,
                        "total_files": len(files) if part_num == 1 else 0,
                    })
                    logger.info(f"Parte {part_num}: {part_name} ({part_mb:.2f} MB)")
                    part_num += 1

            os.remove(temp_zip)

            # Crear lista de partes
            self._create_parts_list(user_id, packed_dir, base_filename, parts, len(files))

            total_mb = sum(p["size_mb"] for p in parts)
            return parts, (
                f"Empaquetado completado: {len(parts)} partes, "
                f"{len(files)} archivos, {total_mb:.1f} MB total"
            )

        except Exception as e:
            logger.error(f"Error en empaquetado dividido: {e}", exc_info=True)
            if os.path.exists(temp_zip):
                os.remove(temp_zip)
            raise e

    def _create_parts_list(self, user_id, packed_dir, base_filename, parts, total_files):
        """Crea archivo .txt con la lista de enlaces."""
        list_name = f"{base_filename}.txt"
        list_path = os.path.join(packed_dir, list_name)

        try:
            with open(list_path, "w", encoding="utf-8") as f:
                f.write(f"Lista de partes: {base_filename}\n")
                f.write(f"Archivos originales: {total_files}\n")
                f.write(f"Partes: {len(parts)}\n")
                f.write("=" * 50 + "\n\n")
                for i, part in enumerate(parts, 1):
                    f.write(f"Parte {i:03d}: {part['filename']}\n")
                    f.write(f"Tamaño: {part['size_mb']:.2f} MB\n")
                    f.write(f"Enlace: {part['url']}\n\n")

            file_service.register_file(user_id, list_name, list_name, "packed")
            logger.info(f"Lista de partes creada: {list_name}")
        except Exception as e:
            logger.error(f"Error creando lista: {e}")

    def clear_packed_folder(self, user_id):
        try:
            packed_dir = file_service.get_user_directory(user_id, "packed")
            if not os.path.exists(packed_dir):
                return False, "No hay archivos empaquetados"

            files = os.listdir(packed_dir)
            if not files:
                return False, "No hay archivos empaquetados"

            count = 0
            for f in files:
                fp = os.path.join(packed_dir, f)
                if os.path.isfile(fp):
                    os.remove(fp)
                    count += 1

            return True, f"Se eliminaron {count} archivos empaquetados"
        except Exception as e:
            logger.error(f"Error limpiando empaquetados: {e}")
            return False, f"Error: {str(e)}"


packing_service = PackingService()
