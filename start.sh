#!/bin/bash
set -o errexit

echo "🚀 Iniciando Bot de File2Link - PRODUCCIÓN"

# ===========================================
# FASE 1: SEGURIDAD Y OPTIMIZACIONES
# ===========================================

echo "🔒 Configurando seguridad..."

# Configurar directorio seguro
mkdir -p storage
chmod 700 storage

# Configurar ulimits
ulimit -n 100000 2>/dev/null || true
ulimit -u 10000 2>/dev/null || true

echo "  ✓ Configuración de seguridad aplicada"

# ===========================================
# FASE 2: VERIFICACIÓN CRÍTICA
# ===========================================

echo "🔍 Verificando variables críticas..."

REQUIRED_VARS=("BOT_TOKEN" "API_ID" "API_HASH")
MISSING_VARS=()

for VAR in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!VAR}" ]; then
        MISSING_VARS+=("$VAR")
    fi
done

if [ ${#MISSING_VARS[@]} -gt 0 ]; then
    echo "❌ ERROR: Variables faltantes:"
    printf '   • %s\n' "${MISSING_VARS[@]}"
    exit 1
fi

echo "✅ Variables verificadas"

# ===========================================
# FASE 3: LIMPIEZA Y PREPARACIÓN
# ===========================================

echo "🧹 Preparando entorno..."

# Limpiar archivos temporales viejos
find storage -name "temp_*" -type f -mtime +1 -delete 2>/dev/null || true

# Asegurar permisos
find storage -type d -exec chmod 700 {} \;
find storage -type f -exec chmod 600 {} \;

echo "  ✓ Entorno preparado"

# ===========================================
# FASE 4: INICIO DEL BOT
# ===========================================

echo "🎯 Iniciando servicios..."
echo "================================"
echo "📊 Configuración:"
echo "   • Límite archivo: ${MAX_FILE_SIZE_MB:-2000}MB"
echo "   • Buffer: 64KB"
echo "   • Procesos: ${MAX_CONCURRENT_PROCESSES:-2}"
echo "   • Seguridad: Token temporal"
echo "================================"

# Ejecutar con logging detallado
exec python -u main.py 2>&1 | tee -a bot.log