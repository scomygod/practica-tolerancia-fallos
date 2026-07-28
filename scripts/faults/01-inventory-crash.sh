#!/usr/bin/env bash

set -euo pipefail

for tool in kubectl curl; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

namespace="tickets"
selector="app=inventory"
gateway_url="http://localhost:8080"

echo "Réplicas de Inventario antes del fallo:"
kubectl -n "$namespace" get deployment inventory
kubectl -n "$namespace" get pods -l "$selector" -o wide

target_pod="$(
  kubectl -n "$namespace" get pods \
    -l "$selector" \
    --field-selector=status.phase=Running \
    -o jsonpath='{.items[0].metadata.name}'
)"

if [[ -z "$target_pod" ]]; then
  echo "Error: no se encontró un pod de Inventario en ejecución." >&2
  exit 1
fi

echo "Eliminando el pod $target_pod sin alterar las réplicas del Deployment..."
kubectl -n "$namespace" delete pod "$target_pod" --wait=false

echo "Estado inmediatamente después de inyectar el fallo:"
kubectl -n "$namespace" get pods -l "$selector" -o wide

successful_queries=0
failed_queries=0

echo "Consultando Inventario mientras Kubernetes recrea el pod..."
for attempt in {1..8}; do
  echo "Consulta $attempt a $gateway_url/api/inventory/1"
  if query_response="$(
    curl --fail --silent --show-error \
      "$gateway_url/api/inventory/1" 2>&1
  )"; then
    echo "Respuesta correcta: $query_response"
    ((successful_queries += 1))
  else
    echo "Fallo controlado durante la consulta: $query_response"
    ((failed_queries += 1))
  fi
  sleep 1
done

echo "Esperando la recuperación del Deployment de Inventario..."
kubectl -n "$namespace" rollout status deployment/inventory --timeout=120s
kubectl -n "$namespace" wait \
  --for=condition=Ready \
  pod \
  -l "$selector" \
  --timeout=120s

echo "Consultas correctas: $successful_queries"
echo "Consultas fallidas: $failed_queries"
echo "Estado y distribución final de Inventario:"
kubectl -n "$namespace" get pods -l "$selector" -o wide

echo "Escenario Inventario Fantasma completado."
