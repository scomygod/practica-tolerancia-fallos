# Guion de demo técnica

Duración objetivo: **12–14 minutos**. Participantes: **Adrian** y **Rafael**.

## Preparación previa

Estado requerido antes de compartir pantalla:

- [ ] Docker Desktop abierto y estable.
- [ ] Clúster `tickets-cluster` creado.
- [ ] Cinco imágenes cargadas en kind.
- [ ] Todos los pods en estado `Running` y `Ready`.
- [ ] Inventario del evento 1 restaurado a 10.
- [ ] `PAYMENT_DELAY_SECONDS=0`.
- [ ] Pagos y Notificaciones con una réplica.
- [ ] Circuit Breaker en estado inicial mediante un pod nuevo de Reservas.
- [ ] Terminales abiertas en la raíz del repositorio.
- [ ] Comandos de cada sección copiados.
- [ ] Evidencias de respaldo disponibles.

Restablecimiento inicial:

```bash
kubectl -n tickets set env deployment/payments PAYMENT_DELAY_SECONDS=0
kubectl -n tickets rollout restart deployment/reservations
kubectl -n tickets rollout status deployment/reservations --timeout=180s
./scripts/reset-demo.sh
./scripts/verify-cluster.sh
```

Distribución de ventanas:

| Ventana | Contenido |
|---|---|
| Terminal 1 | Ejecución de escenarios y recuperaciones |
| Terminal 2 | `kubectl get pods -n tickets -o wide --watch` |
| Evidencias | `docs/architecture.md` y archivos bajo `evidence/` |

## Cronograma

| Tiempo | Integrante | Sección |
|---:|---|---|
| 0:00–1:00 | Adrian | Introducción y objetivo |
| 1:00–2:00 | Adrian | Arquitectura |
| 2:00–3:00 | Adrian | Clúster y distribución |
| 3:00–5:00 | Adrian | Inventario Fantasma |
| 5:00–7:30 | Rafael | Pasarela Lenta |
| 7:30–9:00 | Rafael | Correo Perdido |
| 9:00–11:00 | Adrian | Condición de Carrera |
| 11:00–12:30 | Rafael | Logs y recuperación final |
| 12:30–13:30 | Rafael | Conclusiones |

## 1. Introducción y arquitectura — Adrian

Mostrar `docs/architecture.md`.

Explicación:

> El sistema tiene cinco servicios FastAPI y PostgreSQL. El cliente entra por el API Gateway; Reservas coordina Inventario, Pagos y Notificaciones. Inventario tiene dos réplicas distribuidas entre workers y PostgreSQL conserva el estado en un PVC.

## 2. Clúster y distribución — Adrian

**Ventana:** Terminal 1 y Terminal 2.

```bash
kubectl get nodes -o wide
kubectl -n tickets get pods -o wide
curl --fail http://localhost:8080/health
```

Señalar los tres nodos, las dos réplicas de Inventario en workers distintos y el resto de pods asignados por el scheduler.

## 3. Inventario Fantasma — Adrian

1. **Estado inicial**

   ```bash
   kubectl -n tickets get pods -l app=inventory -o wide
   ```

2. **Comando exacto**

   ```bash
   ./scripts/faults/01-inventory-crash.sh
   ```

3. **Ventana:** Terminal 1 para el script y Terminal 2 para observar la recreación.

4. **Resultado esperado:** un pod se elimina, la otra réplica continúa atendiendo y Kubernetes crea un reemplazo hasta recuperar dos pods listos.

5. **Evidencia:** señalar el pod eliminado, las consultas durante el fallo, el nuevo nombre de pod y `evidence/inventory/`.

6. **Recuperación**

   ```bash
   ./scripts/recovery/01-inventory-recovery.sh
   ./scripts/reset-demo.sh
   ```

7. **Frase técnica**

   > El Deployment reconcilia la réplica perdida y el Service mantiene tráfico hacia la instancia saludable; la distribución por hostname evita concentrar ambas réplicas en un worker.

8. **Duración:** aproximadamente 2 minutos.

## 4. Pasarela Lenta — Rafael

1. **Estado inicial**

   ```bash
   kubectl -n tickets get deployment payments
   kubectl -n tickets get configmap tickets-config \
     -o jsonpath='{.data.PAYMENT_TIMEOUT_SECONDS}'; echo
   ```

2. **Comando exacto**

   ```bash
   ./scripts/faults/02-payment-latency.sh
   ```

3. **Ventana:** Terminal 1 para códigos y tiempos; Terminal 2 para el rollout de Pagos.

4. **Resultado esperado:** las tres primeras reservas responden HTTP 503 cerca de 3 segundos; la cuarta responde 503 rápidamente porque el Circuit Breaker está abierto.

5. **Evidencia:** comparar duraciones y señalar `evidence/payments/payment-latency.txt` junto con las Figuras 9–11.1 de `docs/report/images/`.

6. **Recuperación**

   ```bash
   ./scripts/recovery/02-payment-recovery.sh
   ./scripts/reset-demo.sh
   ```

7. **Frase técnica**

   > El timeout limita cuánto espera cada reserva y el Circuit Breaker evita repetir llamadas costosas después de tres fallos consecutivos.

8. **Duración:** aproximadamente 2 minutos y 30 segundos, incluida la espera de recuperación.

## 5. Correo Perdido — Rafael

1. **Estado inicial**

   ```bash
   kubectl -n tickets get pods -l app=notifications -o wide
   ```

2. **Comando exacto**

   ```bash
   ./scripts/faults/03-notification-down.sh
   ```

3. **Ventana:** Terminal 1 para la respuesta completa; Terminal 2 para confirmar que no quedan pods de Notificaciones.

4. **Resultado esperado:** la reserva responde HTTP 201 con `status=confirmed` y `notification_status=pending`.

5. **Evidencia:** señalar la ausencia de pods, la respuesta completa, `evidence/notifications/notification-down.txt` y las Figuras 12–14 de `docs/report/images/`.

6. **Recuperación**

   ```bash
   ./scripts/recovery/03-notification-recovery.sh
   ```

7. **Frase técnica**

   > Notificaciones es una dependencia no crítica: su caída no revierte una reserva pagada y el fallback registra `notification_status=pending`.

8. **Duración:** aproximadamente 1 minuto y 30 segundos.

## 6. Condición de Carrera — Adrian

1. **Estado inicial:** Pagos y Notificaciones disponibles; el propio script prepara un único asiento.

   ```bash
   kubectl -n tickets get pods
   ```

2. **Comando exacto**

   ```bash
   python3 scripts/faults/04-race-condition.py
   ```

3. **Ventana:** Terminal 1 mostrando simultáneamente ambas respuestas.

4. **Resultado esperado:** exactamente una respuesta HTTP 201, una HTTP 409 e inventario final igual a cero.

5. **Evidencia:** señalar correos diferentes, códigos, duraciones, inventario final y `evidence/race-condition/result.txt`.

6. **Recuperación**

   ```bash
   ./scripts/recovery/04-race-condition-reset.sh
   ./scripts/reset-demo.sh
   ```

7. **Frase técnica**

   > La condición y el descuento ocurren en un único UPDATE atómico; PostgreSQL permite que solo una solicitud consuma el último asiento.

8. **Duración:** aproximadamente 2 minutos.

## 7. Logs y recuperación final — Rafael

**Ventana:** Terminal 1.

```bash
kubectl -n tickets logs deployment/reservations --since=15m
kubectl -n tickets logs deployment/payments --since=15m
kubectl -n tickets logs deployment/notifications --since=15m
./scripts/reset-demo.sh
./scripts/verify-cluster.sh
```

Señalar el timeout de Pagos, el Circuit Breaker, el fallback de Notificaciones y las reservas confirmadas. Confirmar al final dos réplicas de Inventario y una de Pagos y Notificaciones.

## 8. Conclusiones — Rafael

> La demo muestra cuatro anomalías reales con defensas pequeñas y observables: réplica distribuida, timeout con Circuit Breaker, fallback no crítico y actualización SQL atómica. El alcance es académico: Pagos y Notificaciones son simulados, PostgreSQL tiene una sola réplica y no existe observabilidad avanzada.

## Plan de contingencia

- Si una prueba en vivo falla, mostrar primero los logs y después la evidencia guardada del escenario.
- No reconstruir imágenes durante la demo.
- No editar YAML durante la exposición.
- Ejecutar `./scripts/reset-demo.sh` entre escenarios.
- Si un pod no recupera a tiempo, mostrar `kubectl -n tickets get pods -o wide` y continuar con la evidencia de respaldo.
- Mantener `docs/architecture.md` abierto para explicar el comportamiento sin depender de una animación en vivo.
