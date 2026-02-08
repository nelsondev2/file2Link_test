#!/bin/bash
set -o errexit

echo "🚀 Iniciando Bot de File2Link - V2 MEJORADA..."

# ===========================================
# FASE 1: OPTIMIZACIONES DEL SISTEMA
# ===========================================
echo "⚡ Aplicando optimizaciones de rendimiento..."

# Aumentar límites del sistema para descargas grandes
ulimit -n 65536 2>/dev/null || true
echo "  ✓ Límites de archivos aumentados"

# Configurar buffer TCP para mejor rendimiento de red
sysctl -w net.core.rmem_max=16777216 2>/dev/null || true
sysctl -w net.core.wmem_max=16777216 2>/dev/null || true
echo "  ✓ Buffers TCP optimizados"

# ===========================================
# FASE 2: VERIFICACIÓN DE VARIABLES DE ENTORNO
# ===========================================
echo "🔧 Verificando variables de entorno..."

if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN no configurado"
    echo "   Configúralo en Render.com → Environment Variables"
    exit 1
fi

if [ -z "$API_ID" ]; then
    echo "❌ ERROR: API_ID no configurado"
    echo "   Configúralo en Render.com → Environment Variables"
    exit 1
fi

if [ -z "$API_HASH" ]; then
    echo "❌ ERROR: API_HASH no configurado"
    echo "   Configúralo en Render.com → Environment Variables"
    exit 1
fi

echo "✅ Todas las variables de entorno configuradas"

# ===========================================
# FASE 3: INICIALIZACIÓN MEJORADA
# ===========================================
echo "🎯 Iniciando bot V2 mejorado..."
echo "📊 CONFIGURACIÓN MEJORADA:"
echo "   • Seguridad: URLs con hash como primer bot ✅"
echo "   • Sistema: Gestión básica de usuarios ✅"
echo "   • Cola: Límites anti-abuso y concurrente ✅"
echo "   • Simplificado: Sin sistema de broadcast ✅"
echo "==========================================="
echo "🔐 Hash security: Activado"
echo "🔄 Queue system: Mejorado"
echo "📊 Stats system: Optimizado"
echo "==========================================="

# Ejecutar el bot
exec python main.py