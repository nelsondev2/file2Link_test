#!/bin/bash
set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "   File2Link — Iniciando servicio"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# ── Verificar variables de entorno ────────────────────────────────────────────

fail=0
for var in BOT_TOKEN API_ID API_HASH; do
  if [ -z "${!var:-}" ]; then
    echo "✗ Falta la variable de entorno: $var"
    fail=1
  fi
done

if [ "$fail" -eq 1 ]; then
  echo ""
  echo "Configura las variables en Render.com → Environment Variables"
  exit 1
fi

echo "✓ Variables de entorno verificadas"

# ── Optimizaciones de sistema (opcionales, ignoran errores) ──────────────────

ulimit -n 65536 2>/dev/null && echo "✓ Límite de archivos ampliado" || true
sysctl -w net.core.rmem_max=16777216 2>/dev/null || true
sysctl -w net.core.wmem_max=16777216 2>/dev/null || true

echo ""
echo "Iniciando aplicación…"
exec python main.py
