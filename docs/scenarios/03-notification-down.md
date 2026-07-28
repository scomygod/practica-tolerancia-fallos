# Escenario 03: Correo Perdido

## Fallo

El Servicio de Notificaciones queda completamente fuera de servicio al reducir su Deployment a cero réplicas. Inventario, Pagos y Reservas permanecen disponibles.

## Mecanismo de inyección

El script ejecuta:

```bash
kubectl -n tickets scale deployment/notifications --replicas=0
```

Después confirma que no queda ningún pod con la etiqueta `app=notifications` y crea una reserva a través del API Gateway.

## Defensa

Notificaciones es una dependencia no crítica. Reservas intenta enviar la notificación después de confirmar el pago, pero un fallo o indisponibilidad no cancela la reserva:

- `status` permanece como `confirmed`.
- `notification_status` se guarda como `pending`.
- La API responde HTTP 201 e informa que la notificación quedó pendiente.

No existe reenvío automático, cola ni worker para procesar posteriormente las notificaciones pendientes.

## Comportamiento esperado

### Antes

Notificaciones tiene una réplica lista. Una reserva exitosa termina con `status=confirmed` y `notification_status=sent`.

### Durante

No existen pods de Notificaciones. Inventario reserva el asiento y Pagos aprueba la operación. El intento de notificación falla, pero Reservas aplica el fallback y responde HTTP 201 con:

```json
{
  "status": "confirmed",
  "notification_status": "pending"
}
```

Los logs de Reservas deben mostrar que la reserva se confirmó con la notificación pendiente.

### Después

La recuperación restaura una réplica de Notificaciones y espera su rollout. Una nueva reserva debe responder HTTP 201 con `notification_status=sent`.

La reserva creada durante el fallo permanece en `pending`; este escenario no implementa su reenvío.

## Comandos

Ejecutar el fallo:

```bash
./scripts/faults/03-notification-down.sh
```

Ejecutar la recuperación:

```bash
./scripts/recovery/03-notification-recovery.sh
```

Comprobaciones manuales:

```bash
kubectl -n tickets get pods -l app=notifications -o wide
kubectl -n tickets logs deployment/reservations --since=10m
kubectl -n tickets logs deployment/notifications --since=10m
```

## Evidencia requerida

Guardar en `evidence/notifications/`:

1. Escalado de Notificaciones a cero.
2. Consulta que demuestre que no existen pods de Notificaciones.
3. Respuesta HTTP 201 completa durante el fallo.
4. Campos `status=confirmed` y `notification_status=pending`.
5. Logs del fallback en Reservas.
6. Escalado de recuperación a una réplica.
7. Rollout completo de Notificaciones.
8. Nueva respuesta HTTP 201 con `notification_status=sent`.
9. Logs de la notificación enviada después de la recuperación.
