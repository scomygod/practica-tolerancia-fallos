#!/usr/bin/env bash

set -euo pipefail

for tool in kubectl curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

namespace="tickets"
selector="app=notifications"
gateway_url="http://localhost:8080"

echo "Escalando Notificaciones a cero réplicas..."
kubectl -n "$namespace" scale deployment/notifications --replicas=0

echo "Esperando a que desaparezcan los pods de Notificaciones..."
notification_pods=""
for _ in {1..30}; do
  notification_pods="$(
    kubectl -n "$namespace" get pods \
      -l "$selector" \
      -o jsonpath='{.items[*].metadata.name}'
  )"
  if [[ -z "$notification_pods" ]]; then
    break
  fi
  sleep 1
done

if [[ -n "$notification_pods" ]]; then
  echo "Error: todavía existen pods de Notificaciones: $notification_pods" >&2
  exit 1
fi

echo "Confirmado: no existen pods de Notificaciones."
kubectl -n "$namespace" get pods -l "$selector" -o wide

echo "Enviando una reserva con Notificaciones fuera de servicio..."
reservation_response="$(
  curl --silent --show-error \
    --max-time 15 \
    --header "Content-Type: application/json" \
    --data '{
      "event_id": 1,
      "email": "notification-down@example.com",
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

if [[ "$response_body" != *'"notification_status":"pending"'* ]]; then
  echo "Error: notification_status no quedó en pending." >&2
  exit 1
fi

echo "Reserva confirmada con notification_status=pending."
echo "Logs del fallback en Reservas:"
kubectl -n "$namespace" logs deployment/reservations --since=10m

echo "Escenario Correo Perdido completado."
