#!/usr/bin/env bash

set -euo pipefail

for tool in kubectl curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

namespace="tickets"

echo "Restaurando PAYMENT_DELAY_SECONDS a cero..."
kubectl -n "$namespace" patch configmap tickets-config \
  --type merge \
  -p '{"data":{"PAYMENT_DELAY_SECONDS":"0"}}'
kubectl -n "$namespace" set env \
  deployment/payments \
  PAYMENT_DELAY_SECONDS=0

echo "Restaurando réplicas de la demo..."
kubectl -n "$namespace" scale deployment/inventory --replicas=2
kubectl -n "$namespace" scale deployment/payments --replicas=1
kubectl -n "$namespace" scale deployment/notifications --replicas=1

for deployment in inventory payments notifications; do
  echo "Esperando rollout de $deployment..."
  kubectl -n "$namespace" rollout status "deployment/$deployment" --timeout=180s
done

echo "Abriendo acceso temporal a la API de Inventario..."
kubectl -n "$namespace" port-forward service/inventory 18000:8000 \
  >/dev/null 2>&1 &
port_forward_pid=$!

cleanup_port_forward() {
  kill "$port_forward_pid" >/dev/null 2>&1 || true
  wait "$port_forward_pid" 2>/dev/null || true
}
trap cleanup_port_forward EXIT

inventory_ready="false"
for _ in {1..20}; do
  if curl --fail --silent http://localhost:18000/health >/dev/null 2>&1; then
    inventory_ready="true"
    break
  fi
  sleep 0.5
done

if [[ "$inventory_ready" != "true" ]]; then
  echo "Error: no fue posible acceder a la API de Inventario." >&2
  exit 1
fi

echo "Restableciendo inventario del evento 1 a 10 asientos..."
curl --fail --silent --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"available_seats":10}' \
  http://localhost:18000/inventory/1/reset
echo

echo "La demo quedó restablecida correctamente."
