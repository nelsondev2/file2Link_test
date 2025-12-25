#!/usr/bin/env bash
set -euo pipefail

# start.sh — script de despliegue simple
# Exporta variables de entorno necesarias y arranca la app

export API_ID="${API_ID:-}"
export API_HASH="${API_HASH:-}"
export BOT_TOKEN="${BOT_TOKEN:-}"
export PORT="${PORT:-8080}"
export BASE_DIR="${BASE_DIR:-storage}"
export MAX_CONCURRENT_PROCESSES="${MAX_CONCURRENT_PROCESSES:-1}"
export MAX_FILE_SIZE_MB="${MAX_FILE_SIZE_MB:-2000}"

# Crear entornos y directorios
python3 -m venv venv || true
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

mkdir -p storage logs temp sessions

echo "Iniciando aplicación..."
exec python3 main.py