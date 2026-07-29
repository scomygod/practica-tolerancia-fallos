# Mapeo de fallos y mecanismos de resiliencia

| Fallo | Tipo de anomalía | Componente afectado | Mecanismo de inyección en Kubernetes | Patrón o solución | Estado |
|---|---|---|---|---|---|
| Inventario Fantasma | Caída de instancia e indisponibilidad parcial | Servicio de Inventario | Eliminación de un pod de Inventario | Dos réplicas distribuidas y recuperación automática del Deployment | Implementado |
| Pasarela Lenta | Latencia excesiva de una dependencia | Servicio de Pagos y Servicio de Reservas | Variable de latencia de 20 segundos y rollout del Deployment de Pagos | Timeout y Circuit Breaker | Implementado |
| Diluvio de Peticiones | Sobrecarga por volumen de solicitudes | API Gateway | k6 o script de carga | Rate limiting, HPA, límites de recursos y bulkhead | Analizado |
| Base de Datos Intermitente | Pérdida o degradación intermitente de conectividad | PostgreSQL y servicios que acceden a la base de datos | Toxiproxy, NetworkPolicy compatible o reglas de red | Retries limitados, Circuit Breaker, idempotencia y alta disponibilidad | Analizado |
| Correo Perdido | Indisponibilidad total de una dependencia no crítica | Servicio de Notificaciones | Escalado del Deployment de Notificaciones a cero réplicas | Fallback no crítico | Implementado |
| Condición de Carrera | Concurrencia sobre un recurso limitado | Servicio de Inventario | Dos solicitudes concurrentes por el último asiento | Actualización SQL atómica | Implementado |

## Justificación de los fallos implementados

Inventario Fantasma, Pasarela Lenta, Correo Perdido y Condición de Carrera no requieren infraestructura adicional y se relacionan directamente con los mecanismos incluidos en el laboratorio. Sus efectos pueden observarse mediante respuestas HTTP, estado de pods y logs.

## Justificación de los fallos analizados

Diluvio de Peticiones y Base de Datos Intermitente se limitaron al análisis porque una simulación controlada requiere infraestructura adicional para carga o manipulación de red. La Parte V documenta sus mecanismos, límites y decisiones de diseño sin presentarlos como implementados.
