import os
import logging
import sys
import time
import asyncio
import concurrent.futures
from pyrogram import Client, filters
from pyrogram.types import Message

from loadmanager import loadmanager
from fileservice import fileservice
from progressservice import progressservice
from packingservice import packingservice
from downloadservice import fastdownload_service
from config import MAXFILESIZE, MAXFILESIZEMB, MAXUSERQUOTAMB
from quotaservice import quotaservice
from maintenanceservice import maintenanceservice
from logservice import logservice, system_logger

logger = logging.getLogger(name)

user_sessions = {}
user_queues = {}
usercurrentprocessing = {}
userbatchtotals = {}

def getusersession(user_id):
    if userid not in usersessions:
        usersessions[userid] = {'current_folder': 'downloads'}
    return usersessions[userid]

async def start_command(client, message):
    try:
        user = message.from_user
        
        welcometext = f"""👋 Bienvenido/a, {user.firstname}

🤖 File2Link Bot · Sistema profesional de gestión de archivos por carpetas.

📁 SISTEMA DE CARPETAS
/cd downloads · Acceder a archivos de descarga  
/cd packed · Acceder a archivos empaquetados  
/cd · Mostrar carpeta actual

📄 GESTIÓN DE ARCHIVOS
/list · Listar archivos de la carpeta actual  
/rename <número> <nuevo_nombre> · Renombrar archivo  
/delete <número> · Eliminar archivo  
/clear · Vaciar carpeta actual

📦 EMPAQUETADO
/pack · Crear un ZIP con todos tus downloads  
/pack <MB> · Crear ZIP y dividir en partes de <MB>

🔄 COLA DE PROCESO
/queue · Ver archivos en cola de procesamiento  
/clearqueue · Limpiar la cola de descargas

🔍 INFORMACIÓN
/status · Ver estado del sistema y tu uso de espacio  
/help · Mostrar ayuda completa

📏 LÍMITES
• Tamaño máximo por archivo: {MAXFILESIZE_MB} MB  
• Cuota máxima por usuario: {MAXUSERQUOTA_MB} MB

Envía un archivo para comenzar o usa /cd downloads y /list para ver tus archivos actuales.
"""
        await message.replytext(welcometext)
        logservice.loguser_action(user.id, "info", "/start ejecutado")

    except Exception as e:
        logger.error(f"Error en /start: {e}")

async def help_command(client, message):
    try:
        help_text = f"""📚 Ayuda · Sistema de Carpetas

📁 NAVEGACIÓN
/cd downloads · Ir a carpeta de descargas  
/cd packed · Ir a carpeta de empaquetados  
/cd · Ver carpeta actual

📄 GESTIÓN EN CARPETA ACTUAL
/list · Listar archivos  
/rename <número> <nuevo_nombre> · Renombrar archivo  
/delete <número> · Eliminar archivo  
/clear · Vaciar carpeta completa

📦 EMPAQUETADO
/pack · Crear un ZIP con todos los archivos de downloads  
/pack <MB> · Crear ZIP y dividir en partes de <MB> MB

🔄 COLA DE DESCARGAS
/queue · Ver archivos en cola  
/clearqueue · Limpiar la cola de descargas

🔍 INFORMACIÓN
/status · Ver estado del sistema y tu uso de espacio  
/help · Mostrar esta ayuda

📏 LÍMITES
• Tamaño máximo por archivo: {MAXFILESIZE_MB} MB  
• Cuota máxima por usuario: {MAXUSERQUOTA_MB} MB

Ejemplos:  
/cd downloads  
/list  
/rename 3 mi_documento  
/pack 100
"""
        await message.replytext(helptext)
        logservice.loguseraction(message.fromuser.id, "info", "/help ejecutado")

    except Exception as e:
        logger.error(f"Error en /help: {e}")

async def cd_command(client, message):
    try:
        userid = message.fromuser.id
        session = getusersession(user_id)
        args = message.text.split()
        
        if len(args) == 1:
            current = session['current_folder']
            await message.reply_text(f"📂 Carpeta actual: {current}")
        else:
            folder = args[1].lower()
            if folder in ['downloads', 'packed']:
                session['current_folder'] = folder
                await message.reply_text(f"📂 Carpeta actual cambiada a: {folder}")
            else:
                await message.reply_text(
                    "❌ Carpeta no válida.\n\n"
                    "Carpetas disponibles:\n"
                    "• downloads · Archivos de descarga\n"
                    "• packed · Archivos empaquetados\n\n"
                    "Uso: /cd downloads o /cd packed"
                )

    except Exception as e:
        logger.error(f"Error en /cd: {e}")
        await message.reply_text("❌ Se produjo un error al cambiar de carpeta.")

async def list_command(client, message):
    try:
        userid = message.fromuser.id
        session = getusersession(user_id)
        currentfolder = session['currentfolder']
        
        args = message.text.split()
        page = 1
        if len(args) > 1:
            try:
                page = int(args[1])
            except ValueError:
                page = 1
        
        files = fileservice.listuserfiles(userid, current_folder)
        
        if not files:
            await message.reply_text(
                f"📂 Carpeta {current_folder} vacía.\n\n"
                "Para agregar archivos:\n"
                "• Envía archivos al bot (se guardan en downloads).\n"
                "• Usa /pack para generar archivos en packed."
            )
            return
        
        itemsperpage = 10
        totalpages = (len(files) + itemsperpage - 1) // itemsper_page
        page = max(1, min(page, total_pages))
        
        startidx = (page - 1) * itemsper_page
        endidx = startidx + itemsperpage
        pagefiles = files[startidx:end_idx]
        
        folderdisplay = "📥 DESCARGAS" if currentfolder == "downloads" else "📦 EMPAQUETADOS"
        filestext = f"{folderdisplay} · Página {page}/{total_pages}\n"
        files_text += f"Total de archivos: {len(files)}\n\n"
        
        for fileinfo in pagefiles:
            filestext += f"#{fileinfo['number']} · {file_info['name']}\n"
            filestext += f"📏 Tamaño: {fileinfo['size_mb']:.1f} MB\n"
            filestext += f"🔗 Descargar\n\n"

        if total_pages > 1:
            files_text += "Navegación:\n"
            if page > 1:
                files_text += f"• /list {page-1} · Página anterior\n"
            if page < total_pages:
                files_text += f"• /list {page+1} · Página siguiente\n"
            files_text += "• /list <número> · Ir a una página específica\n"

        files_text += "\nAcciones rápidas:\n"
        files_text += "• /delete <número> · Eliminar archivo\n"
        filestext += "• /rename <número> <nuevonombre> · Renombrar archivo\n"
        files_text += "• /clear · Vaciar carpeta completa"

        if len(files_text) > 4000:
            parts = []
            current_part = ""
            
            for line in files_text.split('\n'):
                if len(current_part + line + '\n') > 4000:
                    parts.append(current_part)
                    current_part = line + '\n'
                else:
                    current_part += line + '\n'
            
            if current_part:
                parts.append(current_part)
            
            await message.replytext(parts[0], disablewebpagepreview=True)
            
            for part in parts[1:]:
                await message.replytext(part, disablewebpagepreview=True)
        else:
            await message.replytext(filestext, disablewebpage_preview=True)

    except Exception as e:
        logger.error(f"Error en /list: {e}")
        await message.reply_text("❌ Se produjo un error al listar los archivos.")

async def delete_command(client, message):
    try:
        userid = message.fromuser.id
        session = getusersession(user_id)
        currentfolder = session['currentfolder']
        args = message.text.split()
        
        if len(args) < 2:
            await message.reply_text(
                "❌ Formato incorrecto.\n\n"
                "Uso: /delete <número>\n"
                "Ejemplo: /delete 5\n\n"
                "Usa /list para ver los números de archivo."
            )
            return
        
        try:
            file_number = int(args[1])
        except ValueError:
            await message.reply_text("❌ El número debe ser un valor numérico válido.")
            return
        
        success, resultmessage = fileservice.deletefilebynumber(userid, filenumber, currentfolder)
        
        if success:
            await message.replytext(f"✅ {resultmessage}")
        else:
            await message.replytext(f"❌ {resultmessage}")
            
    except Exception as e:
        logger.error(f"Error en /delete: {e}")
        await message.reply_text("❌ Se produjo un error al eliminar el archivo.")

async def clear_command(client, message):
    try:
        userid = message.fromuser.id
        session = getusersession(user_id)
        currentfolder = session['currentfolder']
        
        success, resultmessage = fileservice.deleteallfiles(userid, currentfolder)
        
        if success:
            await message.replytext(f"✅ {resultmessage}")
        else:
            await message.replytext(f"❌ {resultmessage}")
            
    except Exception as e:
        logger.error(f"Error en /clear: {e}")
        await message.reply_text("❌ Se produjo un error al vaciar la carpeta.")

async def rename_command(client, message):
    try:
        userid = message.fromuser.id
        session = getusersession(user_id)
        currentfolder = session['currentfolder']
        args = message.text.split(maxsplit=2)
        
        if len(args) < 3:
            await message.reply_text(
                "❌ Formato incorrecto.\n\n"
                "Uso: /rename <número> <nuevo_nombre>\n"
                "Ejemplo: /rename 3 midocumentoimportante\n\n"
                "Usa /list para ver los números de archivo."
            )
            return
        
        try:
            file_number = int(args[1])
        except ValueError:
            await message.reply_text("❌ El número debe ser un valor numérico válido.")
            return
        
        new_name = args[2].strip()
        
        if not new_name:
            await message.reply_text("❌ El nuevo nombre no puede estar vacío.")
            return
        
        success, resultmessage, newurl = fileservice.renamefile(userid, filenumber, newname, currentfolder)
        
        if success:
            responsetext = f"✅ {resultmessage}\n\n"
            response_text += f"Nuevo enlace:\n"
            responsetext += f"🔗 {newname}"
            
            await message.reply_text(
                response_text,
                disablewebpage_preview=True
            )
        else:
            await message.replytext(f"❌ {resultmessage}")
            
    except Exception as e:
        logger.error(f"Error en /rename: {e}")
        await message.reply_text("❌ Se produjo un error al renombrar el archivo.")

async def status_command(client, message):
    try:
        userid = message.fromuser.id
        session = getusersession(user_id)
        
        downloadscount = len(fileservice.listuserfiles(user_id, "downloads"))
        packedcount = len(fileservice.listuserfiles(user_id, "packed"))
        totalsize = fileservice.getuserstorageusage(userid)
        sizemb = totalsize / (1024 * 1024)
        
        systemstatus = loadmanager.get_status()
        usedbytes, usedmb, percent = quotaservice.getuserusage(userid)
        
        statustext = f"""📊 Estado del Sistema · {message.fromuser.first_name}

👤 USUARIO
• ID: {user_id}  
• Carpeta actual: {session['current_folder']}  
• Archivos en downloads: {downloads_count}  
• Archivos en packed: {packed_count}  
• Espacio usado: {usedmb:.2f} MB / {MAXUSERQUOTAMB} MB ({percent:.1f}%)

📏 CONFIGURACIÓN
• Límite por archivo: {MAXFILESIZE_MB} MB  
• Cuota por usuario: {MAXUSERQUOTA_MB} MB

🖥️ SERVIDOR
• Procesos activos: {systemstatus['activeprocesses']}/{systemstatus['maxprocesses']}  
• Uso de CPU: {systemstatus['cpupercent']:.1f}%  
• Uso de memoria: {systemstatus['memorypercent']:.1f}%  
• Estado: {"✅ ACEPTANDO TRABAJO" if systemstatus['canaccept_work'] else "⚠️ SOBRECARGADO"}
"""
        await message.replytext(statustext)
        
    except Exception as e:
        logger.error(f"Error en /status: {e}")
        await message.reply_text("❌ Se produjo un error al obtener el estado del sistema.")

async def pack_command(client, message):
    try:
        userid = message.fromuser.id

        if maintenanceservice.ismaintenance():
            await message.replytext(maintenanceservice.get_message())
            return

        command_parts = message.text.split()
        
        systemstatus = loadmanager.get_status()
        if not systemstatus['canaccept_work']:
            await message.reply_text(
                f"⚠️ Sistema sobrecargado.\n\n"
                f"CPU: {systemstatus['cpupercent']:.1f}%\n"
                f"Procesos activos: {systemstatus['activeprocesses']}\n"
                f"Intenta nuevamente en unos minutos."
            )
            return
        
        split_size = None
        if len(command_parts) > 1:
            try:
                splitsize = int(commandparts[1])
                if split_size <= 0:
                    await message.reply_text("❌ El tamaño de división debe ser mayor a 0 MB.")
                    return
                if split_size > 200:
                    await message.reply_text("❌ El tamaño máximo por parte es 200 MB.")
                    return
            except ValueError:
                await message.reply_text("❌ Formato incorrecto. Usa: /pack o /pack 100.")
                return
        
        statusmsg = await message.replytext(
            "📦 Iniciando empaquetado...\n\n"
            "Uniendo tus archivos en un ZIP. Esto puede tardar unos minutos."
        )
        
        def runsimplepacking():
            try:
                files, statusmessage = packingservice.packfolder(userid, split_size)
                return files, status_message
            except Exception as e:
                logger.error(f"Error en empaquetado: {e}")
                return None, f"Error al empaquetar: {str(e)}"
        
        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(runsimplepacking)
            files, status_message = future.result(timeout=300)
        
        if not files:
            await statusmsg.edittext(f"❌ {status_message}")
            return
        
        if len(files) == 1:
            file_info = files[0]
            totalfilesinfo = f" ({fileinfo['totalfiles']} archivos)" if 'totalfiles' in fileinfo else ""
            
            responsetext = f"""✅ Empaquetado completado{totalfiles_info}

Archivo generado: {file_info['filename']}  
Tamaño: {fileinfo['sizemb']:.1f} MB  

Enlace de descarga:  
🔗 {fileinfo['filename']}

Usa /cd packed y /list para ver tus archivos empaquetados.
"""
            await statusmsg.edittext(
                response_text, 
                disablewebpage_preview=True
            )
            
        else:
            total_files = 0
            for file_info in files:
                if 'totalfiles' in fileinfo:
                    totalfiles = fileinfo['total_files']
                    break
            
            totalfilesinfo = f" ({totalfiles} archivos)" if totalfiles > 0 else ""
            
            responsetext = f"""✅ Empaquetado completado{totalfiles_info}

Partes generadas: {len(files)}  
Tamaño total: {sum(f['size_mb'] for f in files):.1f} MB  

Enlaces de descarga:"""
            
            for file_info in files:
                responsetext += f"\n\n• Parte {fileinfo'number']}: 🔗 [{fileinfo['filename']}"
            
            response_text += "\n\nUsa /cd packed y /list para ver tus archivos empaquetados."
            
            if len(response_text) > 4000:
                await statusmsg.edittext("✅ Empaquetado completado.\n\nLos enlaces se enviarán en varios mensajes...")
                
                for file_info in files:
                    parttext = f"• Parte {fileinfo'number']}: 🔗 [{fileinfo['filename']}"
                    await message.replytext(parttext, disablewebpage_preview=True)
            else:
                await statusmsg.edittext(
                    response_text, 
                    disablewebpage_preview=True
                )
                
        logger.info(f"Empaquetado completado para usuario {user_id}: {len(files)} archivos")
        
    except concurrent.futures.TimeoutError:
        await statusmsg.edittext("❌ El empaquetado tardó demasiado tiempo. Intenta con menos archivos.")
    except Exception as e:
        logger.error(f"Error en /pack: {e}")
        await message.reply_text("❌ Se produjo un error en el proceso de empaquetado.")

async def queue_command(client, message):
    try:
        userid = message.fromuser.id
        
        if userid not in userqueues or not userqueues[userid]:
            await message.reply_text("📭 Cola vacía\n\nNo hay archivos en cola de procesamiento.")
            return
        
        queuesize = len(userqueues[user_id])
        currentprocessing = "Sí" if userid in usercurrentprocessing else "No"
        
        queuetext = f"📋 Estado de la cola · {queuesize} archivo(s)\n\n"
        
        for i, msg in enumerate(userqueues[userid]):
            file_info = "Desconocido"
            if msg.document:
                fileinfo = f"📄 {msg.document.filename or 'Documento sin nombre'}"
            elif msg.video:
                fileinfo = f"🎥 {msg.video.filename or 'Video sin nombre'}"
            elif msg.audio:
                fileinfo = f"🎵 {msg.audio.filename or 'Audio sin nombre'}"
            elif msg.photo:
                file_info = f"🖼️ Foto"
            
            queuetext += f"#{i+1} · {fileinfo}\n"
        
        queuetext += f"\nProcesando actualmente: {currentprocessing}"
        
        await message.replytext(queuetext)
        
    except Exception as e:
        logger.error(f"Error en /queue: {e}")
        await message.reply_text("❌ Se produjo un error al obtener el estado de la cola.")

async def clearqueuecommand(client, message):
    try:
        userid = message.fromuser.id
        
        if userid not in userqueues or not userqueues[userid]:
            await message.reply_text("📭 La cola ya está vacía.")
            return
        
        queuesize = len(userqueues[user_id])
        userqueues[userid] = []
        
        if userid in usercurrent_processing:
            del usercurrentprocessing[user_id]
        
        if userid in userbatch_totals:
            del userbatchtotals[user_id]
        
        await message.reply_text(
            f"🗑️ Cola limpiada.\n\nSe removieron {queue_size} archivos de la cola."
        )
        
    except Exception as e:
        logger.error(f"Error en /clearqueue: {e}")
        await message.reply_text("❌ Se produjo un error al limpiar la cola.")

async def cleanup_command(client, message):
    try:
        statusmsg = await message.replytext("🧹 Ejecutando limpieza de archivos temporales y verificación de espacio...")
        
        totalsize = fileservice.getuserstorageusage(message.fromuser.id)
        sizemb = totalsize / (1024 * 1024)
        
        await statusmsg.edittext(
            f"✅ Limpieza completada.\n\n"
            f"Espacio usado actualmente: {size_mb:.2f} MB."
        )
        
    except Exception as e:
        logger.error(f"Error en /cleanup: {e}")
        await message.reply_text("❌ Se produjo un error durante la limpieza.")

async def handle_file(client, message):
    try:
        user = message.from_user
        user_id = user.id

        if maintenanceservice.ismaintenance():
            await message.replytext(maintenanceservice.get_message())
            return

        logger.info(f"📥 Archivo recibido de {user_id} - Agregando a cola")

        file_size = 0
        if message.document:
            filesize = message.document.filesize or 0
        elif message.video:
            filesize = message.video.filesize or 0
        elif message.audio:
            filesize = message.audio.filesize or 0
        elif message.photo:
            filesize = message.photo[-1].filesize or 0

        if filesize > MAXFILE_SIZE:
            await message.reply_text(
                "❌ Archivo demasiado grande.\n\n"
                f"Tamaño máximo permitido: {MAXFILESIZE_MB} MB\n"
                f"Tu archivo: {fileservice.formatbytes(file_size)}\n\n"
                "Por favor, divide el archivo en partes más pequeñas."
            )
            return

        canstore, warning = quotaservice.canstore(userid, file_size)
        if not can_store:
            await message.reply_text(warning)
            return
        if warning:
            await message.reply_text(warning)

        if userid not in userqueues:
            userqueues[userid] = []
        
        userqueues[userid].append(message)
        
        if len(userqueues[userid]) == 1:
            await processfilequeue(client, user_id)
        
    except Exception as e:
        logger.error(f"Error procesando archivo: {e}", exc_info=True)
        try:
            await message.reply_text("❌ Se produjo un error al procesar el archivo.")
        except:
            pass

async def processfilequeue(client, user_id):
    try:
        totalfilesinbatch = len(userqueues[user_id])
        userbatchtotals[userid] = totalfilesinbatch
        
        current_position = 0
        
        while userqueues.get(userid) and userqueues[userid]:
            message = userqueues[userid][0]
            current_position += 1
            
            logger.info(f"🔄 Procesando archivo {currentposition}/{totalfilesinbatch} para usuario {user_id}")
            
            await processsinglefile(client, message, userid, currentposition, totalfilesin_batch)
            
            await asyncio.sleep(1)
        
        if userid in userbatch_totals:
            del userbatchtotals[user_id]
                
    except Exception as e:
        logger.error(f"Error en processfilequeue: {e}", exc_info=True)
        if userid in userqueues:
            userqueues[userid] = []
        if userid in userbatch_totals:
            del userbatchtotals[user_id]

async def processsinglefile(client, message, userid, currentposition, total_files):
    start_time = time.time()
    
    try:
        file_obj = None
        file_type = None
        original_filename = None
        file_size = 0

        if message.document:
            file_obj = message.document
            file_type = "Documento"
            originalfilename = message.document.filename or "archivosinnombre"
            filesize = fileobj.file_size or 0
        elif message.video:
            file_obj = message.video
            file_type = "Video"
            originalfilename = message.video.filename or "videosinnombre.mp4"
            filesize = fileobj.file_size or 0
        elif message.audio:
            file_obj = message.audio
            file_type = "Audio"
            originalfilename = message.audio.filename or "audiosinnombre.mp3"
            filesize = fileobj.file_size or 0
        elif message.photo:
            file_obj = message.photo[-1]
            file_type = "Foto"
            originalfilename = f"foto{message.id}.jpg"
            filesize = fileobj.file_size or 0
        else:
            logger.warning(f"Mensaje no contiene archivo manejable: {message.media}")
            if userid in userqueues and userqueues[userid]:
                userqueues[userid].pop(0)
            return

        if not file_obj:
            logger.error("No se pudo obtener el objeto de archivo")
            if userid in userqueues and userqueues[userid]:
                userqueues[userid].pop(0)
            await message.reply_text("❌ Error: No se pudo identificar el archivo.")
            return

        userdir = fileservice.getuserdirectory(user_id, "downloads")
        
        sanitizedname = fileservice.sanitizefilename(originalfilename)
        
        storedfilename = sanitizedname
        counter = 1
        basename, ext = os.path.splitext(sanitizedname)
        filepath = os.path.join(userdir, stored_filename)
        
        while os.path.exists(file_path):
            storedfilename = f"{basename}_{counter}{ext}"
            filepath = os.path.join(userdir, stored_filename)
            counter += 1

        filenumber = fileservice.registerfile(userid, originalfilename, storedfilename, "downloads")
        logger.info(f"📝 Archivo registrado: #{filenumber} - {originalfilename} -> {stored_filename}")

        initialmessage = progressservice.createprogressmessage(
            filename=original_filename,
            current=0,
            total=file_size,
            speed=0,
            userfirstname=message.fromuser.firstname,
            process_type="Subiendo",
            currentfile=currentposition,
            totalfiles=totalfiles
        )
        
        progressmsg = await message.replytext(initial_message)
        
        usercurrentprocessing[userid] = progressmsg.id

        progressdata = {'lastupdate': 0, 'last_speed': 0}

        async def progress_callback(current, total):
            try:
                elapsedtime = time.time() - starttime
                speed = current / elapsedtime if elapsedtime > 0 else 0
                
                progressdata['lastspeed'] = (
                    0.7  progressdata.get('lastspeed', 0) + 0.3  speed
                )
                smoothedspeed = progressdata['last_speed']

                current_time = time.time()
                lastupdate = progressdata.get('last_update', 0)

                if currenttime - lastupdate >= 0.5 or current == total:
                    progressmessage = progressservice.createprogressmessage(
                        filename=original_filename,
                        current=current,
                        total=total,
                        speed=smoothed_speed,
                        userfirstname=message.fromuser.firstname,
                        process_type="Subiendo",
                        currentfile=currentposition,
                        totalfiles=totalfiles
                    )

                    try:
                        await progressmsg.edittext(progress_message)
                        progressdata['lastupdate'] = current_time
                    except Exception as edit_error:
                        logger.warning(f"No se pudo editar mensaje de progreso: {edit_error}")

            except Exception as e:
                logger.error(f"Error en progress callback: {e}")

        try:
            logger.info(f"⚡ Iniciando descarga rápida: {original_filename}")
            
            success, downloaded = await fastdownloadservice.downloadwithretry(
                client=client,
                message=message,
                filepath=filepath,
                progresscallback=progresscallback
            )

            if not success or not os.path.exists(file_path):
                await progressmsg.edittext("❌ Error: El archivo no se descargó correctamente.")
                if userid in userqueues and userqueues[userid]:
                    userqueues[userid].pop(0)
                return

            finalsize = os.path.getsize(filepath)
            if filesize > 0 and finalsize < file_size * 0.95:
                logger.warning(f"⚠️ Posible descarga incompleta: esperado {filesize}, obtenido {finalsize}")
                await progressmsg.edittext("⚠️ Advertencia: El archivo podría estar incompleto.")
            
            sizemb = finalsize / (1024 * 1024)

            downloadurl = fileservice.createdownloadurl(userid, storedfilename)
            logger.info(f"🔗 URL generada: {download_url}")

            fileslist = fileservice.listuserfiles(user_id, "downloads")
            currentfilenumber = None
            for fileinfo in fileslist:
                if fileinfo['storedname'] == stored_filename:
                    currentfilenumber = file_info['number']
                    break

            queue_info = ""
            nextfilescount = len(userqueues[userid]) - 1 if userid in userqueues and userqueues[userid] else 0
            
            if nextfilescount > 0:
                queueinfo = f"\n\n⏭️ Siguiente archivo en cola... ({nextfiles_count} restante(s))"

            successtext = f"""✅ Archivo #{currentfilenumber or filenumber} almacenado correctamente

Nombre: {original_filename}  
Tipo: {file_type}  
Tamaño: {size_mb:.2f} MB  

Enlace de descarga:  
🔗 {originalfilename}

Ubicación: Carpeta downloads{queue_info}
"""

            await progressmsg.edittext(successtext, disablewebpagepreview=True)
            
            logger.info(f"✅ Archivo guardado exitosamente: {storedfilename} para usuario {userid}")

        except Exception as download_error:
            logger.error(f"❌ Error en descarga: {downloaderror}", excinfo=True)
            await progressmsg.edittext("❌ Se produjo un error durante la descarga del archivo.")
        finally:
            if userid in userqueues and userqueues[userid]:
                userqueues[userid].pop(0)
            if userid in usercurrent_processing:
                del usercurrentprocessing[user_id]
            
    except Exception as e:
        logger.error(f"Error en processsinglefile: {e}", exc_info=True)
        if userid in userqueues and userqueues[userid]:
            userqueues[userid].pop(0)

def setup_handlers(app: Client):
    app.addhandler(filters.command("start") & filters.private, startcommand)
    app.addhandler(filters.command("help") & filters.private, helpcommand)
    app.addhandler(filters.command("cd") & filters.private, cdcommand)
    app.addhandler(filters.command("list") & filters.private, listcommand)
    app.addhandler(filters.command("delete") & filters.private, deletecommand)
    app.addhandler(filters.command("clear") & filters.private, clearcommand)
    app.addhandler(filters.command("rename") & filters.private, renamecommand)
    app.addhandler(filters.command("status") & filters.private, statuscommand)
    app.addhandler(filters.command("pack") & filters.private, packcommand)
    app.addhandler(filters.command("queue") & filters.private, queuecommand)
    app.addhandler(filters.command("clearqueue") & filters.private, clearqueue_command)
    app.addhandler(filters.command("cleanup") & filters.private, cleanupcommand)

    @app.on_message(filters.private & (filters.document | filters.video | filters.audio | filters.photo))
    async def filehandler(client, message):
        await handle_file(client, message)