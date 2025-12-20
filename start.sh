#!/bin/bash

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║         🚀 FILE2LINK - SISTEMA OPTIMIZADO           ║"
echo "╠══════════════════════════════════════════════════════╣"
echo "║ • CPU Render: 0.1 (0% uso real)                     ║"
echo "║ • Almacenamiento: 0MB en servidor                   ║"
echo "║ • Todo en Telegram: ☁️ 100% nube                    ║"
echo "║ • URLs: 🔗 Permanentes, sobreviven reinicios        ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

# Verificar variables críticas
echo "🔍 Verificando configuración..."
if [ -z "$BOT_TOKEN" ]; then
    echo "❌ ERROR: BOT_TOKEN no configurado"
    echo "   Configúralo en Render.com → Environment"
    exit 1
fi

if [ -z "$API_ID" ]; then
    echo "❌ ERROR: API_ID no configurado"
    exit 1
fi

if [ -z "$API_HASH" ]; then
    echo "❌ ERROR: API_HASH no configurado"
    exit 1
fi

if [ -z "$DB_CHANNEL_ID" ]; then
    echo "⚠️  ADVERTENCIA: DB_CHANNEL_ID no configurado"
    echo "   Los metadatos no persistirán después de reinicios"
fi

if [ -z "$STORAGE_CHANNEL_ID" ]; then
    echo "⚠️  ADVERTENCIA: STORAGE_CHANNEL_ID no configurado"
    echo "   Las referencias a archivos no persistirán"
fi

echo "✅ Configuración verificada"

# Optimizaciones básicas del sistema
echo "⚡ Aplicando optimizaciones..."
ulimit -n 65536 2>/dev/null || true

# Iniciar la aplicación
echo ""
echo "🎯 Iniciando sistema optimizado..."
echo "📡 Servidor: Render Free Tier"
echo "🤖 Bot: Telegram"
echo "💾 Backend: Telegram Cloud"
echo ""

exec python main.py