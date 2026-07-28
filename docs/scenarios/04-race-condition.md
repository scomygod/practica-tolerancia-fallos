# Escenario 04: Condición de Carrera

## Fallo

Dos clientes intentan comprar simultáneamente el último asiento disponible del evento 1. El escenario comprueba que solo una reserva puede confirmarse.

## Operación check-then-act

Una implementación insegura separaría la decisión y la modificación:

1. Ejecutar `SELECT available_seats`.
2. Comprobar en la aplicación que el valor sea mayor que cero.
3. Ejecutar después un `UPDATE`.

Esto es una operación *check-then-act*: se comprueba un estado y se actúa más tarde. Entre ambos pasos, otra solicitud puede leer el mismo valor.

## Por qué SELECT seguido de UPDATE es inseguro

Con un solo asiento, dos transacciones podrían ejecutar el `SELECT` antes de que ninguna realice el `UPDATE`. Ambas observarían un asiento disponible y ambas intentarían confirmar la compra, provocando sobreventa o un valor incoherente.

La concurrencia no se evita por tener una sola instancia de la aplicación: FastAPI puede procesar solicitudes simultáneas y existen dos réplicas de Inventario.

## Defensa: actualización SQL atómica

Inventario realiza la comprobación y el descuento en una sola sentencia:

```sql
UPDATE inventory
SET available_seats = available_seats - 1
WHERE event_id = :event_id
  AND available_seats > 0
RETURNING available_seats;
```

PostgreSQL serializa las actualizaciones concurrentes sobre la misma fila. Solo una solicitud puede cumplir la condición `available_seats > 0`; la otra no actualiza filas y recibe HTTP 409.

No se utilizan locks distribuidos, Redis ni coordinación externa.

## Comportamiento esperado

### Preparación

El script abre temporalmente un port-forward al Service de Inventario y usa `POST /inventory/1/reset` para dejar exactamente un asiento.

### Durante

Dos tareas `asyncio` esperan el mismo evento de inicio y envían reservas concurrentes mediante HTTPX, usando correos diferentes.

### Resultado

- Exactamente una solicitud responde HTTP 201.
- Exactamente una solicitud responde HTTP 409.
- El inventario final es cero.
- El script termina con código distinto de cero si cualquiera de estas condiciones falla.

## Comandos

Ejecutar el escenario:

```bash
python3 scripts/faults/04-race-condition.py
```

Restablecer diez asientos:

```bash
./scripts/recovery/04-race-condition-reset.sh
```

Comprobaciones manuales:

```bash
curl --fail http://localhost:8080/api/inventory/1
kubectl -n tickets logs deployment/inventory --since=10m
kubectl -n tickets logs deployment/reservations --since=10m
```

## Evidencia requerida

Guardar en `evidence/race-condition/`:

1. Respuesta del reset que muestra un asiento disponible.
2. Correos distintos utilizados por las dos solicitudes.
3. Código HTTP, cuerpo y duración de cada solicitud.
4. Una respuesta HTTP 201.
5. Una respuesta HTTP 409.
6. Inventario final con `available_seats=0`.
7. Mensaje de verificación automática exitosa.
8. Respuesta del script de recuperación con diez asientos.
