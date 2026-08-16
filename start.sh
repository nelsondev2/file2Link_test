#!/bin/bash
set -e

echo "Iniciando File2Link..."

# Verificar variables de entorno
for var in BOT_TOKEN API_ID API_HASH; do
    if [ -z "${!var}" ]; then
        echo "ERROR: $var no configurado"
        exit 1
    fi
done

echo "Variables de entorno OK"
echo "Limite por archivo: ${MAX_FILE_SIZE_MB:-2000} MB"

exec python main.py
