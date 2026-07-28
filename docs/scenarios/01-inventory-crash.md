# Escenario 01: Inventario Fantasma

## Fallo

Se provoca la caída real de una de las dos réplicas del Servicio de Inventario. El Deployment conserva dos réplicas deseadas durante toda la demostración.

## Mecanismo de inyección

El script selecciona un pod de Inventario en ejecución y lo elimina mediante `kubectl delete pod --wait=false`. No escala el Deployment a cero ni modifica su manifiesto.

## Defensa

- Dos réplicas del Servicio de Inventario.
- `topologySpreadConstraints` para distribuir las réplicas entre nodos.
- Service `ClusterIP`, que dirige las solicitudes hacia los pods disponibles.
- Readiness y liveness probes.
- Reconciliación automática del Deployment.
- Reintentos limitados del Servicio de Reservas cuando Inventario no está disponible.

## Comportamiento esperado

### Antes

Las dos réplicas deben aparecer `Running` y `Ready`, preferentemente en nodos diferentes. Las consultas a `/api/inventory/1` deben responder correctamente.

### Durante

Uno de los pods pasa a `Terminating` y Kubernetes crea otro. La réplica restante continúa atendiendo solicitudes mediante el Service. Puede existir un fallo transitorio breve; si ocurre, debe quedar visible y controlado en la salida del script.

### Después

El Deployment vuelve a tener dos réplicas `Running` y `Ready`. El pod eliminado se reemplaza por uno nuevo y la distribución entre nodos vuelve a cumplir la restricción configurada.

## Comandos

Ejecutar el escenario:

```bash
./scripts/faults/01-inventory-crash.sh
```

Forzar la recuperación del estado esperado:

```bash
./scripts/recovery/01-inventory-recovery.sh
```

Comprobaciones manuales opcionales:

```bash
kubectl -n tickets get deployment inventory
kubectl -n tickets get pods -l app=inventory -o wide
curl --fail http://localhost:8080/api/inventory/1
```

## Evidencia requerida

Guardar en `evidence/inventory/`:

1. Estado inicial con los dos pods y sus nodos.
2. Nombre del pod seleccionado y salida de `kubectl delete pod`.
3. Estado inmediatamente posterior a la eliminación.
4. Resultados de las consultas realizadas durante la recreación.
5. Nombre del nuevo pod.
6. Estado final con dos réplicas listas y sus nodos.
7. Resumen de consultas correctas y fallidas mostrado por el script.
