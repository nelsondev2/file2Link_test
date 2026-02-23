#!/bin/bash
set -o errexit

echo "🚀 Iniciando Bot de File2Link - Versión Optimizada..."

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
# FASE 3: INICIO DE LA APLICACIÓN
# ===========================================

echo "🎯 Iniciando bot optimizado..."
echo "📊 Configuración de descarga:"
echo "   • Buffer: 128KB"
echo "   • Timeout: 1 hora"
echo "   • Reintentos: 3"
echo "==========================================="

# Ejecutar el bot
exec python main.py
