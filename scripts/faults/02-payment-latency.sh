#!/usr/bin/env bash

set -euo pipefail

for tool in kubectl curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

namespace="tickets"
gateway_url="http://localhost:8080"

send_reservation() {
  local attempt="$1"

  curl --silent --show-error \
    --max-time 12 \
    --header "Content-Type: application/json" \
    --data "{
      \"event_id\": 1,
      \"email\": \"payment-latency-${attempt}@example.com\",
      \"amount\": 49.99
    }" \
    --write-out $'\nHTTP %{http_code} - tiempo total: %{time_total} s\n' \
    "$gateway_url/api/reservations"
}

echo "Configurando PAYMENT_DELAY_SECONDS=20 en Pagos..."
kubectl -n "$namespace" set env \
  deployment/payments \
  PAYMENT_DELAY_SECONDS=20

echo "Esperando el rollout de Pagos..."
kubectl -n "$namespace" rollout status deployment/payments --timeout=180s

echo "Enviando tres reservas; cada una debe terminar cerca del timeout de 3 s."
for attempt in 1 2 3; do
  echo "Reserva $attempt:"
  send_reservation "$attempt"
done

echo "Enviando una cuarta reserva con el Circuit Breaker ya abierto."
echo "La respuesta debe ser considerablemente más rápida que 3 s."
send_reservation 4

echo "Logs recientes de Reservas:"
kubectl -n "$namespace" logs deployment/reservations --since=10m

echo "Logs recientes de Pagos:"
kubectl -n "$namespace" logs deployment/payments --since=10m

echo "Escenario Pasarela Lenta completado."
