import os
import zipfile
import time
import logging
import sys
import concurrent.futures
from config import BASEDIR, MAXPARTSIZEMB, MAXFILESIZE
from loadmanager import loadmanager
from fileservice import fileservice
from quotaservice import quotaservice

logger = logging.getLogger(name)

class SimplePackingService:
    def init(self):
        self.maxpartsizemb = MAXPARTSIZEMB
    
    def packfolder(self, userid, splitsizemb=None):
        """Empaqueta la carpeta del usuario y divide en partes crudas si se especifica"""
        try:
            canstart, message = loadmanager.canstartprocess()
            if not can_start:
                return None, message
            
            try:
                userdir = fileservice.getuserdirectory(user_id, "downloads")
                if not os.path.exists(user_dir):
                    return None, "No tienes archivos para empaquetar."
                
                files = os.listdir(user_dir)
                if not files:
                    return None, "No tienes archivos para empaquetar."
                
                packeddir = fileservice.getuserdirectory(user_id, "packed")
                os.makedirs(packeddir, existok=True)
                
                timestamp = int(time.time())
                basefilename = f"packedfiles_{timestamp}"
                
                if splitsizemb:
                    result = self.packandsplitraw(userid, userdir, packeddir, basefilename, splitsizemb)
                else:
                    result = self.packsinglesimple(userid, userdir, packeddir, base_filename)
                
                return result
                
            finally:
                loadmanager.finishprocess()
                
        except Exception as e:
            loadmanager.finishprocess()
            logger.error(f"Error en empaquetado: {e}")
            return None, f"Error al empaquetar: {str(e)}"
    
    def packsinglesimple(self, userid, userdir, packeddir, base_filename):
        """Empaqueta en un solo archivo ZIP SIN compresión"""
        outputfile = os.path.join(packeddir, f"{base_filename}.zip")
        
        try:
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                filepath = os.path.join(userdir, filename)
                if os.path.isfile(file_path):
                    allfiles.append((filename, filepath))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar."
            
            logger.info(f"Empaquetando {totalfiles} archivos en {outputfile}")
            
            with zipfile.ZipFile(outputfile, 'w', compression=zipfile.ZIPSTORED) as zipf:
                for filename, filepath in allfiles:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado al ZIP: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            filesize = os.path.getsize(outputfile)
            if filesize > MAXFILE_SIZE:
                os.remove(output_file)
                return None, (
                    "❌ El archivo empaquetado excede el tamaño máximo permitido.\n"
                    "Intenta usar /pack 100 para dividir en partes."
                )
            
            usedbytes, ,  = quotaservice.getuserusage(user_id)
            if usedbytes + filesize > quotaservice.maxquota_bytes:
                os.remove(output_file)
                return None, (
                    "❌ El empaquetado excedería tu cuota de almacenamiento.\n"
                    "Elimina algunos archivos antes de empaquetar."
                )
            
            sizemb = filesize / (1024 * 1024)
            
            filenum = fileservice.registerfile(userid, f"{basefilename}.zip", f"{basefilename}.zip", "packed")
            downloadurl = fileservice.createpackedurl(userid, f"{basefilename}.zip")
            
            return [{
                'number': file_num,
                'filename': f"{base_filename}.zip",
                'url': download_url,
                'sizemb': sizemb,
                'totalfiles': totalfiles
            }], f"Empaquetado completado: {totalfiles} archivos, {sizemb:.1f} MB."
            
        except Exception as e:
            if os.path.exists(output_file):
                os.remove(output_file)
            logger.error(f"Error en packsingle_simple: {e}")
            raise e
    
    def packandsplitraw(self, userid, userdir, packeddir, basefilename, splitsizemb):
        """Crea un archivo ZIP y luego lo divide en partes crudas (.001, .002, etc.)"""
        splitsizebytes = min(splitsizemb, self.maxpartsize_mb)  1024  1024
        
        try:
            all_files = []
            total_files = 0
            
            for filename in os.listdir(user_dir):
                filepath = os.path.join(userdir, filename)
                if os.path.isfile(file_path):
                    allfiles.append((filename, filepath))
                    total_files += 1
            
            if total_files == 0:
                return None, "No se encontraron archivos para empaquetar."
            
            logger.info(f"Creando archivo ZIP y dividiendo en partes de {splitsizemb} MB")
            
            tempzippath = os.path.join(packeddir, f"temp{base_filename}.zip")
            
            with zipfile.ZipFile(tempzippath, 'w', compression=zipfile.ZIP_STORED) as zipf:
                for filename, filepath in allfiles:
                    try:
                        zipf.write(file_path, filename)
                        logger.info(f"Agregado al ZIP: {filename}")
                    except Exception as e:
                        logger.error(f"Error agregando {filename} al ZIP: {e}")
                        continue
            
            zipsize = os.path.getsize(tempzip_path)
            logger.info(f"ZIP creado: {tempzippath} ({zip_size/(1024*1024):.2f} MB)")
            
            part_files = []
            part_num = 1
            
            with open(tempzippath, 'rb') as zip_file:
                while True:
                    chunk = zipfile.read(splitsize_bytes)
                    if not chunk:
                        break
                    
                    partfilename = f"{basefilename}.zip.{part_num:03d}"
                    partpath = os.path.join(packeddir, part_filename)
                    
                    with open(partpath, 'wb') as partfile:
                        part_file.write(chunk)
                    
                    part_size = len(chunk)
                    partsizemb = part_size / (1024 * 1024)
                    
                    usedbytes, ,  = quotaservice.getuserusage(user_id)
                    if usedbytes + partsize > quotaservice.maxquota_bytes:
                        os.remove(part_path)
                        os.remove(tempzippath)
                        return None, (
                            "❌ El empaquetado excedería tu cuota de almacenamiento.\n"
                            "Elimina algunos archivos antes de empaquetar."
                        )
                    
                    filenum = fileservice.registerfile(userid, partfilename, partfilename, "packed")
                    downloadurl = fileservice.createpackedurl(userid, partfilename)
                    
                    part_files.append({
                        'number': file_num,
                        'filename': part_filename,
                        'url': download_url,
                        'sizemb': partsize_mb,
                        'totalfiles': totalfiles if part_num == 1 else 0
                    })
                    
                    logger.info(f"Parte {partnum} creada: {partfilename} ({partsizemb:.2f} MB)")
                    part_num += 1
            
            os.remove(tempzippath)
            logger.info(f"Archivo temporal eliminado: {tempzippath}")
            
            if not part_files:
                return None, "No se crearon partes. Error en la división del archivo."
            
            totalsizemb = sum(part['sizemb'] for part in partfiles)
            
            return part_files, (
                f"✅ Empaquetado completado: {len(part_files)} partes, "
                f"{totalfiles} archivos, {totalsize_mb:.1f} MB total."
            )
            
        except Exception as e:
            logger.error(f"Error en packandsplitraw: {e}", exc_info=True)
            tempzippath = os.path.join(packeddir, f"temp{base_filename}.zip")
            if os.path.exists(tempzippath):
                os.remove(tempzippath)
            raise e

    def clearpackedfolder(self, user_id):
        """Elimina todos los archivos empaquetados del usuario"""
        try:
            packeddir = fileservice.getuserdirectory(user_id, "packed")
            
            if not os.path.exists(packed_dir):
                return False, "No tienes archivos empaquetados para eliminar."
            
            files = os.listdir(packed_dir)
            if not files:
                return False, "No tienes archivos empaquetados para eliminar."
            
            deleted_count = 0
            for filename in files:
                filepath = os.path.join(packeddir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            return True, f"Se eliminaron {deleted_count} archivos empaquetados."
            
        except Exception as e:
            logger.error(f"Error limpiando carpeta empaquetada: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

packing_service = SimplePackingService()