# Escenario 02: Pasarela Lenta

## Fallo

El Servicio de Pagos introduce una latencia artificial de 20 segundos. El Servicio de Reservas solo espera 3 segundos antes de considerar que el pago no está disponible.

## Mecanismo de inyección

El script establece `PAYMENT_DELAY_SECONDS=20` en el Deployment `payments` mediante `kubectl set env` y espera a que termine su rollout. Después envía cuatro reservas a través del API Gateway.

## Por qué se utiliza timeout

Sin timeout, cada solicitud de reserva permanecería bloqueada durante los 20 segundos de latencia de Pagos. El límite de 3 segundos permite liberar rápidamente la solicitud, registrar `payment_failed` y ejecutar la compensación del asiento.

El timeout del cliente no garantiza que el procesamiento remoto se cancele. Una solicitud ya recibida por Pagos puede continuar ejecutándose hasta que el pod termine el trabajo o sea reiniciado.

## Por qué se utiliza Circuit Breaker

Cuando un servicio falla repetidamente, seguir enviándole solicitudes consume conexiones y obliga a cada cliente a esperar el mismo timeout. El Circuit Breaker abre después de tres fallos consecutivos y rechaza llamadas posteriores de inmediato mientras Pagos se recupera.

## Estados del Circuit Breaker

- `CLOSED`: las llamadas llegan a Pagos. Cada éxito reinicia el contador de fallos.
- `OPEN`: no se llama a Pagos y la reserva recibe una respuesta HTTP 503 rápida.
- `HALF_OPEN`: después del período de recuperación se permite una llamada de prueba. Un éxito devuelve el circuito a `CLOSED`; un fallo vuelve a abrirlo.

## Comportamiento esperado

### Antes

Pagos tiene latencia cero, el Circuit Breaker está `CLOSED` y una reserva válida responde HTTP 201.

### Durante

Las tres primeras reservas esperan aproximadamente 3 segundos y responden HTTP 503 por timeout. Cada asiento reservado se intenta compensar mediante `release`. Tras el tercer fallo, el circuito pasa a `OPEN`.

La cuarta reserva responde HTTP 503 mucho más rápido porque no realiza una llamada a Pagos.

### Después

La recuperación restaura la latencia a cero y espera el período configurado más dos segundos. La siguiente reserva actúa como llamada de prueba en `HALF_OPEN`; si Pagos responde correctamente, la reserva termina con HTTP 201 y el circuito vuelve a `CLOSED`.

## Comandos

Ejecutar el fallo:

```bash
./scripts/faults/02-payment-latency.sh
```

Ejecutar la recuperación:

```bash
./scripts/recovery/02-payment-recovery.sh
```

Comprobaciones manuales:

```bash
kubectl -n tickets get deployment payments
kubectl -n tickets logs deployment/reservations --since=10m
kubectl -n tickets logs deployment/payments --since=10m
```
