#!/bin/bash
set -o errexit
set -o pipefail
set -o nounset

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funciones de logging
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                 🤖 NELSON FILE2LINK PRO                  ║"
    echo "║              Sistema Profesional de Archivos             ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

# ===========================================
# FASE 0: BANNER Y VERIFICACIÓN INICIAL
# ===========================================
print_banner
log_info "🚀 Iniciando Bot de File2Link - Versión Profesional..."

# ===========================================
# FASE 1: VERIFICACIÓN DE PREREQUISITOS
# ===========================================
log_info "🔍 Verificando prerequisitos..."

# Verificar Python
if ! command -v python3 &> /dev/null; then
    log_error "Python3 no encontrado. Es requerido."
    exit 1
fi

# Función para comparar versiones de Python correctamente
compare_versions() {
    local required_major required_minor
    IFS='.' read -r required_major required_minor <<< "$1"
    
    local current_major current_minor
    IFS='.' read -r current_major current_minor <<< "$2"
    
    if [[ "$current_major" -lt "$required_major" ]]; then
        return 1  # Versión menor
    elif [[ "$current_major" -eq "$required_major" && "$current_minor" -lt "$required_minor" ]]; then
        return 1  # Mismo major, pero minor menor
    fi
    return 0  # Versión OK
}

# Obtener versión de Python
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

# Verificar que sea al menos 3.8
if compare_versions "3.8" "$PYTHON_VERSION"; then
    log_success "Python $PYTHON_VERSION detectado (mínimo requerido: 3.8)"
else
    log_error "Se requiere Python 3.8 o superior. Encontrado: $PYTHON_VERSION"
    exit 1
fi

# Verificar pip
if ! command -v pip3 &> /dev/null; then
    log_error "pip3 no encontrado. Es requerido."
    exit 1
fi

# ===========================================
# FASE 2: OPTIMIZACIONES DEL SISTEMA
# ===========================================
log_info "⚡ Aplicando optimizaciones de rendimiento..."

# Aumentar límites del sistema para descargas grandes
ulimit -n 65536 2>/dev/null || {
    log_warning "No se pudo aumentar límite de archivos. Continuando..."
}

# Configurar buffer TCP para mejor rendimiento de red
if command -v sysctl &> /dev/null; then
    sysctl -w net.core.rmem_max=16777216 2>/dev/null || true
    sysctl -w net.core.wmem_max=16777216 2>/dev/null || true
    sysctl -w net.ipv4.tcp_window_scaling=1 2>/dev/null || true
    log_success "Buffers TCP optimizados"
else
    log_warning "sysctl no disponible. Saltando optimizaciones de red."
fi

# ===========================================
# FASE 3: VERIFICACIÓN DE VARIABLES DE ENTORNO
# ===========================================
log_info "🔧 Verificando variables de entorno..."

# Variables requeridas
REQUIRED_VARS=("BOT_TOKEN" "API_ID" "API_HASH")
MISSING_VARS=()

# Verificar si estamos en entorno con variables (Render) o si están en .env
if [[ -f ".env" ]]; then
    log_info "Cargando variables desde .env file"
    set -a
    source .env
    set +a
fi

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        MISSING_VARS+=("$var")
    fi
done

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    log_error "Variables de entorno faltantes: ${MISSING_VARS[*]}"
    echo ""
    echo "📝 Configúralas en Render.com:"
    echo "   1. Ve a tu proyecto en Render.com"
    echo "   2. Haz click en 'Environment'"
    echo "   3. Agrega las siguientes variables:"
    echo ""
    for var in "${MISSING_VARS[@]}"; do
        echo "   - $var"
    done
    echo ""
    echo "O crea un archivo .env con estas variables."
    exit 1
fi

# Validar formato de variables
if [[ ! "$API_ID" =~ ^[0-9]+$ ]]; then
    log_error "API_ID debe ser numérico"
    exit 1
fi

if [[ ${#BOT_TOKEN} -lt 10 ]]; then
    log_error "BOT_TOKEN parece inválido (muy corto)"
    exit 1
fi

log_success "Todas las variables de entorno configuradas"

# ===========================================
# FASE 4: VERIFICACIÓN DE DEPENDENCIAS
# ===========================================
log_info "📦 Verificando dependencias de Python..."

# Crear virtual environment si no existe
if [[ ! -d "venv" ]]; then
    log_info "Creando virtual environment..."
    python3 -m venv venv
fi

# Activar virtual environment
source venv/bin/activate

# Instalar/verificar dependencias
REQUIREMENTS_FILE="requirements.txt"
if [[ -f "$REQUIREMENTS_FILE" ]]; then
    log_info "Instalando/actualizando dependencias..."
    pip install --upgrade pip setuptools wheel
    pip install -r "$REQUIREMENTS_FILE" --no-cache-dir
    log_success "Dependencias instaladas"
else
    log_error "No se encontró $REQUIREMENTS_FILE"
    exit 1
fi

# ===========================================
# FASE 5: PREPARACIÓN DEL ENTORNO
# ===========================================
log_info "📁 Preparando entorno de ejecución..."

# Crear directorios necesarios
mkdir -p storage logs temp sessions

# Verificar permisos de escritura
if [[ ! -w "storage" ]]; then
    log_error "Sin permisos de escritura en directorio 'storage'"
    exit 1
fi

log_success "Entorno preparado correctamente"

# ===========================================
# FASE 6: INFORMACIÓN DE CONFIGURACIÓN
# ===========================================
log_info "📊 Configuración del sistema:"
echo "   • 🤖 Bot Token: ${BOT_TOKEN:0:10}..."
echo "   • 🔑 API ID: $API_ID"
echo "   • 🌐 Puerto: ${PORT:-8080}"
echo "   • 📏 Máx. archivo: ${MAX_FILE_SIZE_MB:-2000} MB"
echo "   • ⚡ Buffer descarga: ${DOWNLOAD_BUFFER_SIZE:-131072} bytes"
echo "   • 🔄 Reintentos: ${MAX_RETRIES:-3}"
echo "   • 📦 Máx. parte: ${MAX_PART_SIZE_MB:-200} MB"
echo "⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯⎯"

# ===========================================
# FASE 7: INICIO DE LA APLICACIÓN
# ===========================================
log_info "🎯 Iniciando aplicación..."

# Limpiar archivos temporales antiguos
find temp/ -type f -mtime +1 -delete 2>/dev/null || true

# Variables de entorno para Python
export PYTHONPATH="$PWD:$PYTHONPATH"
export PYTHONUNBUFFERED=1
export PYTHONIOENCODING=UTF-8

# Ejecutar el bot
exec python main.py