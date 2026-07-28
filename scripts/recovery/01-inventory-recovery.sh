#!/usr/bin/env bash

set -euo pipefail

if ! command -v kubectl >/dev/null 2>&1; then
  echo "Error: se requiere kubectl y no está disponible." >&2
  exit 1
fi

namespace="tickets"
selector="app=inventory"

echo "Asegurando dos réplicas para Inventario..."
kubectl -n "$namespace" scale deployment/inventory --replicas=2

echo "Esperando el rollout de Inventario..."
kubectl -n "$namespace" rollout status deployment/inventory --timeout=120s
kubectl -n "$namespace" wait \
  --for=condition=Ready \
  pod \
  -l "$selector" \
  --timeout=120s

echo "Pods recuperados y nodos asignados:"
kubectl -n "$namespace" get pods -l "$selector" -o wide

echo "Recuperación de Inventario completada."
