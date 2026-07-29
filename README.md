# Tickets Chaos Lab

Práctica académica de tolerancia a fallos sobre una plataforma simplificada de reservas de entradas desplegada en Kubernetes multinodo.

## Integrantes

| Nombre |
|---|
| Rafael Prieto |
| Adrian Lazo |

## Índice

- [Objetivo](#objetivo)
- [Arquitectura](#arquitectura)
- [Tecnologías](#tecnologías)
- [Estructura](#estructura-del-repositorio)
- [Requisitos](#requisitos)
- [Instalación local](#instalación-local-para-pruebas)
- [Pruebas](#ejecución-de-pruebas)
- [Despliegue rápido](#despliegue-rápido)
- [Uso de la API](#uso-de-la-api)
- [Escenarios de fallo](#escenarios-de-fallo)
- [Evidencias](#evidencias)
- [Limpieza](#limpieza-del-entorno)
- [Limitaciones](#limitaciones-conocidas)
- [Integrantes](#integrantes)

## Objetivo

Construir la solución mínima para desplegar seis componentes en kind, provocar cuatro fallos reales y demostrar recuperación o manejo controlado mediante réplicas, retries limitados, timeout, Circuit Breaker, fallback y SQL atómico.

## Arquitectura

El Cliente accede al API Gateway, que reenvía solicitudes a Reservas o Inventario. Reservas coordina Inventario, Pagos y Notificaciones, y persiste el resultado en PostgreSQL. Inventario también utiliza PostgreSQL.

| Componente | Réplicas | Responsabilidad |
|---|---:|---|
| API Gateway | 1 | Entrada HTTP externa mediante NodePort |
| Reservas | 1 | Coordinar el flujo de reserva |
| Inventario | 2 | Gestionar asientos con actualización SQL atómica |
| Pagos | 1 | Simular pagos, latencia y fallos |
| Notificaciones | 1 | Simular notificaciones y fallos |
| PostgreSQL | 1 | Persistir inventario y reservas |

El diagrama Mermaid y la distribución física están en [docs/architecture.md](docs/architecture.md).

## Tecnologías

- Python 3.13, FastAPI, HTTPX y pytest.
- PostgreSQL 16 y SQLAlchemy.
- Docker y Docker Compose para pruebas locales.
- Kubernetes, kind y manifiestos YAML directos.

## Estructura del repositorio

```text
.
├── services/                 # Cinco servicios FastAPI
├── database/init.sql         # Esquema y datos iniciales
├── kubernetes/
│   ├── cluster/              # Configuración multinodo de kind
│   └── manifests/            # Recursos Kubernetes
├── scripts/
│   ├── faults/               # Inyección de los cuatro fallos
│   └── recovery/             # Recuperación de cada escenario
├── docs/                     # Arquitectura, mapeo y escenarios
└── evidence/                 # Evidencias por escenario
```

## Requisitos

- Docker Desktop en ejecución.
- `kubectl`.
- `kind`.
- Python 3.
- Git.

Los comandos se ejecutan desde la raíz del repositorio.

## Instalación local para pruebas

Crear un entorno virtual e instalar las dependencias declaradas por los cinco servicios:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install \
  -r services/api-gateway/requirements.txt \
  -r services/reservations/requirements.txt \
  -r services/inventory/requirements.txt \
  -r services/payments/requirements.txt \
  -r services/notifications/requirements.txt
```

## Ejecución de pruebas

Cada suite se ejecuta desde el directorio de su servicio para mantener aislado el paquete `app`:

```bash
for service in api-gateway reservations inventory payments notifications; do
  (cd "services/$service" && python3 -m pytest tests)
done
```

## Despliegue rápido

1. Crear el clúster multinodo:

```bash
kind create cluster \
  --name tickets-cluster \
  --config kubernetes/cluster/kind-config.yaml
```

2. Construir y cargar las imágenes:

```bash
./scripts/build-images.sh
./scripts/load-images.sh
```

3. Aplicar los manifiestos y esperar los rollouts:

```bash
./scripts/deploy.sh
```

4. Comprobar pods y nodos:

```bash
kubectl -n tickets get pods -o wide
./scripts/verify-cluster.sh
```

5. Acceder al Gateway:

```bash
curl --fail http://localhost:8080/health
```

kind redirige `localhost:8080` al NodePort `30080` del API Gateway.

## Uso de la API

### Consultar inventario

```bash
curl --fail http://localhost:8080/api/inventory/1
```

### Crear una reserva

```bash
curl --fail \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": 1,
    "email": "persona@example.com",
    "amount": 49.99
  }' \
  http://localhost:8080/api/reservations
```

## Escenarios de fallo

| Escenario | Inyección | Defensa | Documentación |
|---|---|---|---|
| Inventario Fantasma | Eliminar un pod de Inventario | Dos réplicas distribuidas y recuperación automática de Kubernetes | [Escenario 01](docs/scenarios/01-inventory-crash.md) |
| Pasarela Lenta | Latencia de Pagos de 20 segundos | Timeout y Circuit Breaker | [Escenario 02](docs/scenarios/02-payment-latency.md) |
| Correo Perdido | Escalar Notificaciones a cero | Fallback con `notification_status=pending` | [Escenario 03](docs/scenarios/03-notification-down.md) |
| Condición de Carrera | Dos reservas por el último asiento | Actualización SQL atómica | [Escenario 04](docs/scenarios/04-race-condition.md) |

### Ejecutar fallos

```bash
./scripts/faults/01-inventory-crash.sh
./scripts/faults/02-payment-latency.sh
./scripts/faults/03-notification-down.sh
python3 scripts/faults/04-race-condition.py
```

Ejecutar un escenario cada vez y aplicar su recuperación antes de continuar.

### Recuperar el entorno

| Escenario | Comando |
|---|---|
| Inventario Fantasma | `./scripts/recovery/01-inventory-recovery.sh` |
| Pasarela Lenta | `./scripts/recovery/02-payment-recovery.sh` |
| Correo Perdido | `./scripts/recovery/03-notification-recovery.sh` |
| Condición de Carrera | `./scripts/recovery/04-race-condition-reset.sh` |

Para restaurar el estado general de la demo:

```bash
./scripts/reset-demo.sh
```

## Evidencias

Las salidas textuales disponibles se organizan por escenario bajo `evidence/`. Las capturas utilizadas por el informe están en `docs/report/images/`.

| Escenario | Directorio |
|---|---|
| Inventario Fantasma | `evidence/inventory/pods-after-delete.txt` y Figuras 6–8 |
| Pasarela Lenta | `evidence/payments/payment-latency.txt` y Figuras 9–11.1 |
| Correo Perdido | `evidence/notifications/notification-down.txt` y Figuras 12–14 |
| Condición de Carrera | `evidence/race-condition/result.txt` y Figuras 15–16 |

## Limpieza del entorno

```bash
./scripts/cleanup.sh
```

Este comando elimina el clúster kind `tickets-cluster`, pero no borra archivos locales.

## Limitaciones conocidas

- Pagos y Notificaciones son simulados; no procesan dinero ni envían correos reales.
- PostgreSQL utiliza una sola réplica y un PVC local de laboratorio.
- El Circuit Breaker de Pagos vive en memoria y se reinicia con el pod de Reservas.
- Las notificaciones con `notification_status=pending` no se reenvían automáticamente.
- No existen frontend, autenticación, rate limiting, CI/CD ni observabilidad avanzada.
- Los escenarios de sobrecarga y conectividad intermitente con PostgreSQL solo están analizados en [docs/failure-mapping.md](docs/failure-mapping.md).
