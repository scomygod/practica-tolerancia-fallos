#!/usr/bin/env bash

set -euo pipefail

if ! command -v kubectl >/dev/null 2>&1; then
  echo "Error: se requiere kubectl y no está disponible." >&2
  exit 1
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
manifests_dir="$repo_root/kubernetes/manifests"
namespace="tickets"
deployments=(
  postgres
  inventory
  payments
  notifications
  reservations
  api-gateway
)

echo "Aplicando manifiestos Kubernetes..."
kubectl apply -f "$manifests_dir"

for deployment in "${deployments[@]}"; do
  echo "Esperando rollout de $deployment..."
  kubectl -n "$namespace" rollout status "deployment/$deployment" --timeout=180s
done

echo "Despliegue completado correctamente."
