import os
import urllib.parse
import hashlib
import json
import time
import logging
import sys
from config import BASEDIR, RENDERDOMAIN

logger = logging.getLogger(name)

class FileService:
    def init(self):
        self.file_mappings = {}
        self.metadatafile = "filemetadata.json"
        self.load_metadata()
    
    def load_metadata(self):
        """Carga la metadata de archivos desde JSON"""
        try:
            if os.path.exists(self.metadata_file):
                with open(self.metadata_file, 'r', encoding='utf-8') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {}
        except Exception as e:
            logger.error(f"Error cargando metadata: {e}")
            self.metadata = {}
    
    def save_metadata(self):
        """Guarda la metadata de archivos en JSON"""
        try:
            with open(self.metadata_file, 'w', encoding='utf-8') as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Error guardando metadata: {e}")
    
    def getnextfilenumber(self, userid, file_type="downloads"):
        """Obtiene el siguiente número de archivo para el usuario (PERSISTENTE)"""
        userkey = f"{userid}{filetype}"
        if user_key not in self.metadata:
            self.metadata[userkey] = {"nextnumber": 1, "files": {}}
        
        nextnum = self.metadata[userkey]["next_number"]
        self.metadata[userkey]["nextnumber"] += 1
        self.save_metadata()
        return next_num
    
    def sanitize_filename(self, filename):
        """Limpia el nombre de archivo para que sea URL-safe"""
        invalid_chars = '<>:"/\\|?*'
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        if len(filename) > 100:
            name, ext = os.path.splitext(filename)
            filename = name[:100-len(ext)] + ext
        return filename

    def format_bytes(self, size):
        """Formatea bytes a formato legible"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"

    def createdownloadurl(self, user_id, filename):
        """Crea una URL de descarga válida"""
        safefilename = self.sanitizefilename(filename)
        encodedfilename = urllib.parse.quote(safefilename)
        return f"{RENDERDOMAIN}/storage/{userid}/downloads/{encoded_filename}"

    def createpackedurl(self, user_id, filename):
        """Crea una URL para archivos empaquetados"""
        safefilename = self.sanitizefilename(filename)
        encodedfilename = urllib.parse.quote(safefilename)
        return f"{RENDERDOMAIN}/storage/{userid}/packed/{encoded_filename}"

    def getuserdirectory(self, userid, filetype="downloads"):
        """Obtiene el directorio del usuario"""
        userdir = os.path.join(BASEDIR, str(userid), filetype)
        os.makedirs(userdir, existok=True)
        return user_dir

    def getuserstorageusage(self, userid):
        """Calcula el uso de almacenamiento por usuario"""
        downloaddir = self.getuserdirectory(userid, "downloads")
        packeddir = self.getuserdirectory(userid, "packed")
        
        total_size = 0
        for directory in [downloaddir, packeddir]:
            if not os.path.exists(directory):
                continue
            for file in os.listdir(directory):
                file_path = os.path.join(directory, file)
                if os.path.isfile(file_path):
                    totalsize += os.path.getsize(filepath)
        
        return total_size

    def createfilehash(self, user_id, filename):
        """Crea un hash único para el archivo"""
        data = f"{userid}{filename}_{time.time()}"
        return hashlib.md5(data.encode()).hexdigest()[:12]

    def listuserfiles(self, userid, filetype="downloads"):
        """Lista archivos del usuario con numeración PERSISTENTE"""
        userdir = self.getuserdirectory(userid, file_type)
        if not os.path.exists(user_dir):
            return []
        
        files = []
        userkey = f"{userid}{filetype}"
        
        if user_key in self.metadata:
            existing_files = []
            for filenum, filedata in self.metadata[user_key]["files"].items():
                filepath = os.path.join(userdir, filedata["storedname"])
                if os.path.exists(file_path):
                    existingfiles.append((int(filenum), file_data))
            
            existing_files.sort(key=lambda x: x[0])
            
            for filenumber, filedata in existing_files:
                filepath = os.path.join(userdir, filedata["storedname"])
                if os.path.isfile(file_path):
                    size = os.path.getsize(file_path)
                    if file_type == "downloads":
                        downloadurl = self.createdownloadurl(userid, filedata["storedname"])
                    else:
                        downloadurl = self.createpackedurl(userid, filedata["storedname"])
                    
                    files.append({
                        'number': file_number,
                        'name': filedata["originalname"],
                        'storedname': filedata["stored_name"],
                        'size': size,
                        'size_mb': size / (1024 * 1024),
                        'url': download_url,
                        'filetype': filetype
                    })
        
        return files

    def registerfile(self, userid, originalname, storedname, file_type="downloads"):
        """Registra un archivo en la metadata con número PERSISTENTE"""
        userkey = f"{userid}{filetype}"
        if user_key not in self.metadata:
            self.metadata[userkey] = {"nextnumber": 1, "files": {}}
        
        filenum = self.metadata[userkey]["next_number"]
        self.metadata[userkey]["nextnumber"] += 1
        
        self.metadata[userkey]["files"][str(filenum)] = {
            "originalname": originalname,
            "storedname": storedname,
            "registered_at": time.time()
        }
        self.save_metadata()
        
        logger.info(f"✅ Archivo registrado: #{filenum} - {originalname} para usuario {user_id}")
        return file_num

    def getfilebynumber(self, userid, filenumber, filetype="downloads"):
        """Obtiene información de archivo por número (PERSISTENTE)"""
        userkey = f"{userid}{filetype}"
        if user_key not in self.metadata:
            return None
        
        filedata = self.metadata[userkey]["files"].get(str(file_number))
        if not file_data:
            return None
        
        userdir = self.getuserdirectory(userid, file_type)
        filepath = os.path.join(userdir, filedata["storedname"])
        
        if not os.path.exists(file_path):
            return None
        
        if file_type == "downloads":
            downloadurl = self.createdownloadurl(userid, filedata["storedname"])
        else:
            downloadurl = self.createpackedurl(userid, filedata["storedname"])
        
        return {
            'number': file_number,
            'originalname': filedata["original_name"],
            'storedname': filedata["stored_name"],
            'path': file_path,
            'url': download_url,
            'filetype': filetype
        }

    def getoriginalfilename(self, userid, storedfilename, file_type="downloads"):
        """Obtiene el nombre original del archivo basado en el nombre almacenado"""
        userkey = f"{userid}{filetype}"
        if user_key not in self.metadata:
            return stored_filename
        
        for filedata in self.metadata[userkey]["files"].values():
            if filedata["storedname"] == stored_filename:
                return filedata["originalname"]
        
        return stored_filename

    def renamefile(self, userid, filenumber, newname, file_type="downloads"):
        """Renombra un archivo"""
        try:
            userkey = f"{userid}{filetype}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado", None
            
            fileinfo = self.getfilebynumber(userid, filenumber, file_type)
            if not file_info:
                return False, "Archivo no encontrado", None
            
            filedata = self.metadata[userkey]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado en metadata", None
            
            newname = self.sanitizefilename(new_name)
            
            userdir = self.getuserdirectory(userid, file_type)
            oldpath = os.path.join(userdir, filedata["storedname"])
            
            if not os.path.exists(old_path):
                return False, "Archivo físico no encontrado", None
            
            , ext = os.path.splitext(filedata["stored_name"])
            newstoredname = new_name + ext
            
            counter = 1
            basenewstoredname = newstored_name
            while os.path.exists(os.path.join(userdir, newstored_name)):
                namenoext = os.path.splitext(basenewstored_name)[0]
                ext = os.path.splitext(basenewstored_name)[1]
                newstoredname = f"{namenoext}_{counter}{ext}"
                counter += 1
            
            newpath = os.path.join(userdir, newstoredname)
            
            os.rename(oldpath, newpath)
            
            filedata["originalname"] = new_name
            filedata["storedname"] = newstoredname
            self.save_metadata()
            
            if file_type == "downloads":
                newurl = self.createdownloadurl(userid, newstoredname)
            else:
                newurl = self.createpackedurl(userid, newstoredname)
            
            return True, f"Archivo renombrado a: {newname}", newurl
            
        except Exception as e:
            logger.error(f"Error renombrando archivo: {e}")
            return False, f"Error al renombrar: {str(e)}", None

    def deletefilebynumber(self, userid, filenumber, filetype="downloads"):
        """Elimina un archivo por número y reasigna números"""
        try:
            userkey = f"{userid}{filetype}"
            if user_key not in self.metadata:
                return False, "Usuario no encontrado"
            
            fileinfo = self.getfilebynumber(userid, filenumber, file_type)
            if not file_info:
                return False, "Archivo no encontrado"
            
            filedata = self.metadata[userkey]["files"].get(str(file_number))
            if not file_data:
                return False, "Archivo no encontrado en metadata"
            
            userdir = self.getuserdirectory(userid, file_type)
            filepath = os.path.join(userdir, filedata["storedname"])
            
            if os.path.exists(file_path):
                os.remove(file_path)
            
            del self.metadata[userkey]["files"][str(filenumber)]
            
            remaining_files = sorted(
                [(int(num), data) for num, data in self.metadata[user_key]["files"].items()],
                key=lambda x: x[0]
            )
            
            self.metadata[user_key]["files"] = {}
            
            new_number = 1
            for oldnum, filedata in remaining_files:
                self.metadata[userkey]["files"][str(newnumber)] = file_data
                new_number += 1
            
            self.metadata[userkey]["nextnumber"] = new_number
            self.save_metadata()
            
            return True, f"Archivo #{filenumber} '{filedata['original_name']}' eliminado y números reasignados"
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False, f"Error al eliminar archivo: {str(e)}"

    def deleteallfiles(self, userid, filetype="downloads"):
        """Elimina todos los archivos del usuario de un tipo específico"""
        try:
            userdir = self.getuserdirectory(userid, file_type)
            
            if not os.path.exists(user_dir):
                return False, f"No hay archivos {file_type} para eliminar"
            
            files = os.listdir(user_dir)
            if not files:
                return False, f"No hay archivos {file_type} para eliminar"
            
            deleted_count = 0
            for filename in files:
                filepath = os.path.join(userdir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
                    deleted_count += 1
            
            userkey = f"{userid}{filetype}"
            if user_key in self.metadata:
                self.metadata[userkey] = {"nextnumber": 1, "files": {}}
                self.save_metadata()
            
            return True, f"Se eliminaron {deletedcount} archivos {filetype} y se resetearon los números"
            
        except Exception as e:
            logger.error(f"Error eliminando todos los archivos: {e}")
            return False, f"Error al eliminar archivos: {str(e)}"

file_service = FileService()