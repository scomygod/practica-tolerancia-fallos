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

echo "Restaurando una réplica de Notificaciones..."
kubectl -n "$namespace" scale deployment/notifications --replicas=1

echo "Esperando el rollout de Notificaciones..."
kubectl -n "$namespace" rollout status \
  deployment/notifications \
  --timeout=180s

echo "Enviando una nueva reserva..."
reservation_response="$(
  curl --silent --show-error \
    --max-time 15 \
    --header "Content-Type: application/json" \
    --data '{
      "event_id": 1,
      "email": "notification-recovery@example.com",
      "amount": 49.99
    }' \
    --write-out $'\n%{http_code}' \
    "$gateway_url/api/reservations"
)"

http_status="${reservation_response##*$'\n'}"
response_body="${reservation_response%$'\n'*}"

echo "Respuesta completa:"
echo "HTTP $http_status"
echo "$response_body"

if [[ "$http_status" != "201" ]]; then
  echo "Error: se esperaba HTTP 201 y se recibió HTTP $http_status." >&2
  exit 1
fi

if [[ "$response_body" != *'"status":"confirmed"'* ]]; then
  echo "Error: la reserva no quedó confirmada." >&2
  exit 1
fi

if [[ "$response_body" != *'"notification_status":"sent"'* ]]; then
  echo "Error: notification_status no quedó en sent." >&2
  exit 1
fi

echo "Reserva confirmada con notification_status=sent."
echo "Logs recientes de Notificaciones:"
kubectl -n "$namespace" logs deployment/notifications --since=10m

echo "Recuperación de Notificaciones completada."
