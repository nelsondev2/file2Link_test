# 🤖 File2Link Bot

Bot de Telegram para almacenar archivos y generar enlaces de descarga directa.

## ✨ Características

- ✅ **Almacenamiento seguro**: Enlaces con tokens temporales (24h)
- ✅ **Empaquetado automático**: Crea ZIPs y divide en partes
- ✅ **Cola inteligente**: Procesamiento automático con progreso
- ✅ **Interfaz optimizada**: Mensajes concisos y claros
- ✅ **Gestión completa**: Renombrar, eliminar, listar archivos
- ✅ **Sistema asíncrono**: Máximo rendimiento sin bloqueos
- ✅ **Seguridad total**: HMAC tokens, rate limiting, quotas

## 📦 Instalación

### 1. Variables de entorno
```bash
BOT_TOKEN=tu_token_de_bot
API_ID=tu_api_id_de_telegram
API_HASH=tu_api_hash
RENDER_DOMAIN=tu_dominio.onrender.com
SECRET_KEY=$(python -c "import os; print(os.urandom(24).hex())")
PORT=8080