#!/usr/bin/env bash

set -euo pipefail

if ! command -v kind >/dev/null 2>&1; then
  echo "Error: se requiere kind y no está disponible." >&2
  exit 1
fi

cluster_name="tickets-cluster"

echo "Eliminando el clúster kind $cluster_name..."
kind delete cluster --name "$cluster_name"
echo "Clúster eliminado correctamente. No se borraron archivos locales."
