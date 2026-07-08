#!/usr/bin/env bash
# Prueba integral de carga de listas contra API local.
# Uso: ./scripts/test_upload_flow.sh
set -euo pipefail

API="${API_URL:-http://localhost:8000}"
EXCEL="${1:-listas/DH 4350 COREA JUNIO 2026.xls}"
EMAIL="${ADMIN_EMAIL:-admin@preciopartes.com}"
PASS="${ADMIN_PASSWORD:-admin123}"

echo "==> API: $API"
echo "==> Excel: $EXCEL"

TOKEN=$(curl -sf -X POST "$API/auth/login" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASS\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

echo "==> Login OK"

JOB=$(curl -sf -X POST "$API/api/listas/jobs" \
  -H "Authorization: Bearer $TOKEN")
JOB_ID=$(echo "$JOB" | python3 -c "import sys,json; print(json.load(sys.stdin)['job_id'])")
echo "==> Job creado: $JOB_ID"

curl -sf -X POST "$API/api/listas/jobs/$JOB_ID/archivos" \
  -H "Authorization: Bearer $TOKEN" \
  -F "archivo=@$EXCEL" > /dev/null
echo "==> Archivo subido"

curl -sf -X POST "$API/api/listas/jobs/$JOB_ID/start" \
  -H "Authorization: Bearer $TOKEN" > /dev/null
echo "==> Procesamiento iniciado"

for i in $(seq 1 60); do
  STATUS=$(curl -sf "$API/api/listas/jobs/$JOB_ID" -H "Authorization: Bearer $TOKEN")
  ESTADO=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['estado'])")
  PCT=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin)['progreso_pct'])")
  MSG=$(echo "$STATUS" | python3 -c "import sys,json; print(json.load(sys.stdin).get('mensaje',''))")
  echo "    [$i] estado=$ESTADO progreso=${PCT}% — $MSG"
  if [ "$ESTADO" = "completed" ]; then
    echo "$STATUS" | python3 -m json.tool
    echo "==> PRUEBA OK"
    exit 0
  fi
  sleep 3
done

echo "==> TIMEOUT"
exit 1
