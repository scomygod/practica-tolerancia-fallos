#!/usr/bin/env bash

set -euo pipefail

for tool in kubectl curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

namespace="tickets"

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

echo "Restableciendo el evento 1 a 10 asientos..."
curl --fail --silent --show-error \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"available_seats":10}' \
  http://localhost:18000/inventory/1/reset
echo

echo "Inventario restablecido correctamente."
