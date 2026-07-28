#!/usr/bin/env bash

set -euo pipefail

for tool in docker kind; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

cluster_name="tickets-cluster"
images=(
  tickets/api-gateway:1.0
  tickets/reservations:1.0
  tickets/inventory:1.0
  tickets/payments:1.0
  tickets/notifications:1.0
)

echo "Cargando cinco imágenes en el clúster $cluster_name..."
kind load docker-image --name "$cluster_name" "${images[@]}"
echo "Las imágenes se cargaron correctamente."
