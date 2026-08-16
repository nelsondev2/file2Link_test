# File2Link

Bot de Telegram que guarda archivos y genera enlaces de descarga directa.

## Requisitos

- Python 3.10+
- Cuenta de Telegram con API_ID y API_HASH de [my.telegram.org](https://my.telegram.org)

## Configuracion

Variables de entorno:

| Variable | Descripcion | Requerida |
|----------|-------------|-----------|
| `BOT_TOKEN` | Token del bot de Telegram | Si |
| `API_ID` | API ID de Telegram | Si |
| `API_HASH` | API Hash de Telegram | Si |
| `RENDER_DOMAIN` | Dominio del servidor (ej: https://file2link.onrender.com) | No |
| `PORT` | Puerto del servidor web | No (default: 8080) |
| `MAX_FILE_SIZE_MB` | Limite de tamaño por archivo en MB | No (default: 2000) |

## Instalacion

```bash
pip install -r requirements.txt
```

## Uso

```bash
python main.py
```

O con el script de inicio:

```bash
chmod +x start.sh
./start.sh
```

## Comandos del bot

| Comando | Descripcion |
|---------|-------------|
| `/start` | Menu principal |
| `/cd downloads \| packed` | Cambiar carpeta |
| `/list [pagina]` | Ver archivos |
| `/delete N` | Eliminar archivo #N |
| `/rename N nombre` | Renombrar archivo #N |
| `/clear` | Vaciar carpeta actual |
| `/pack` | Comprimir en ZIP |
| `/pack MB` | ZIP dividido en partes |
| `/queue` | Ver cola de descargas |
| `/clearqueue` | Cancelar cola |
| `/status` | Estado del sistema |
| `/cleanup` | Analizar almacenamiento |

## Endpoints

- `GET /` — Pagina principal
- `GET /health` — Health check
- `GET /system-status` — Estado del sistema
- `GET /files` — Explorador de archivos
- `GET /storage/<uid>/downloads/<file>` — Descargar archivo
- `GET /storage/<uid>/packed/<file>` — Descargar empaquetado

## Licencia

MIT
