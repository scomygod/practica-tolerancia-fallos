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

echo "Restableciendo PAYMENT_DELAY_SECONDS=0 en Pagos..."
kubectl -n "$namespace" set env \
  deployment/payments \
  PAYMENT_DELAY_SECONDS=0

echo "Esperando el rollout de Pagos..."
kubectl -n "$namespace" rollout status deployment/payments --timeout=180s

recovery_seconds="$(
  kubectl -n "$namespace" get configmap tickets-config \
    -o jsonpath='{.data.CIRCUIT_BREAKER_RECOVERY_SECONDS}'
)"

if [[ ! "$recovery_seconds" =~ ^[0-9]+$ ]]; then
  echo "Error: CIRCUIT_BREAKER_RECOVERY_SECONDS no es un entero válido." >&2
  exit 1
fi

wait_seconds=$((recovery_seconds + 2))
echo "Esperando ${wait_seconds} s para permitir la transición a HALF_OPEN..."
sleep "$wait_seconds"

echo "Enviando una reserva de prueba para cerrar el Circuit Breaker..."
curl --fail --silent --show-error \
  --max-time 12 \
  --header "Content-Type: application/json" \
  --data '{
    "event_id": 1,
    "email": "payment-recovery@example.com",
    "amount": 49.99
  }' \
  --write-out $'\nHTTP %{http_code} - tiempo total: %{time_total} s\n' \
  "$gateway_url/api/reservations"

echo "Logs de recuperación de Reservas:"
kubectl -n "$namespace" logs deployment/reservations --since=10m

echo "Logs de recuperación de Pagos:"
kubectl -n "$namespace" logs deployment/payments --since=10m

echo "Recuperación de Pagos completada."
