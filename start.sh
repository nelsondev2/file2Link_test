#!/bin/bash
set -o errexit

# ===========================================
# FASE 1: VERIFICACIÓN DE VARIABLES DE ENTORNO
# ===========================================
echo "🔧 Verificando variables de entorno..."

# Variables requeridas
REQUIRED_VARS=("BOT_TOKEN" "API_ID" "API_HASH")
MISSING_VARS=()

for var in "${REQUIRED_VARS[@]}"; do
    if [[ -z "${!var:-}" ]]; then
        MISSING_VARS+=("$var")
    fi
done

if [[ ${#MISSING_VARS[@]} -gt 0 ]]; then
    echo "❌ Variables de entorno faltantes: ${MISSING_VARS[*]}"
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
    exit 1
fi

# ===========================================
# FASE 2: CREAR DIRECTORIOS NECESARIOS
# ===========================================
echo "📁 Creando directorios..."
mkdir -p storage logs temp sessions

# ===========================================
# FASE 3: INICIAR LA APLICACIÓN
# ===========================================
echo "🚀 Iniciando Nelson File2Link Bot..."
exec python main.py