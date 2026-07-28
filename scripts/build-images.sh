#!/usr/bin/env bash

set -euo pipefail

for tool in docker; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Error: se requiere $tool y no está disponible." >&2
    exit 1
  fi
done

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Construyendo imagen tickets/api-gateway:1.0..."
docker build -t tickets/api-gateway:1.0 "$repo_root/services/api-gateway"

echo "Construyendo imagen tickets/reservations:1.0..."
docker build -t tickets/reservations:1.0 "$repo_root/services/reservations"

echo "Construyendo imagen tickets/inventory:1.0..."
docker build -t tickets/inventory:1.0 "$repo_root/services/inventory"

echo "Construyendo imagen tickets/payments:1.0..."
docker build -t tickets/payments:1.0 "$repo_root/services/payments"

echo "Construyendo imagen tickets/notifications:1.0..."
docker build -t tickets/notifications:1.0 "$repo_root/services/notifications"

echo "Las cinco imágenes se construyeron correctamente."
