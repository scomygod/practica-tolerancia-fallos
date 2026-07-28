#!/usr/bin/env bash

set -euo pipefail

for tool in kubectl curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

gateway_url="http://localhost:8080"

echo "Nodos del clúster:"
kubectl get nodes -o wide

echo "Pods del namespace tickets y nodo asignado:"
kubectl -n tickets get pods -o wide

echo "Comprobando health del API Gateway..."
curl --fail --silent --show-error "$gateway_url/health"
echo

echo "Comprobando inventario del evento 1..."
curl --fail --silent --show-error "$gateway_url/api/inventory/1"
echo

echo "Verificación del clúster completada correctamente."
