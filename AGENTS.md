# Contexto del proyecto

Este repositorio corresponde a una práctica académica de tolerancia a fallos en Kubernetes. El sistema representa una plataforma simplificada de reservas de entradas.

# Objetivo

Construir la solución mínima necesaria para cumplir el enunciado, desplegarla en Kubernetes multinodo, provocar cuatro fallos reales y demostrar recuperación o manejo controlado.

# Tecnologías obligatorias

- Python 3.13.
- FastAPI.
- Comunicación REST con JSON.
- HTTPX para llamadas entre servicios.
- PostgreSQL.
- SQLAlchemy.
- Docker.
- Docker Compose únicamente para pruebas locales.
- Kubernetes con kind.
- YAML directo, sin Helm.
- pytest para pruebas básicas.

# Componentes permitidos

El sistema tendrá exactamente estos seis componentes:

1. API Gateway.
2. Servicio de Reservas.
3. Servicio de Inventario.
4. Servicio de Pagos simulado.
5. Servicio de Notificaciones simulado.
6. PostgreSQL.

# Restricciones

- No crear frontend.
- No implementar autenticación.
- No añadir usuarios, roles o permisos.
- No utilizar Kafka, RabbitMQ, Redis ni otros brokers.
- No utilizar Prometheus, Grafana, Jaeger o ELK.
- No utilizar service mesh.
- No utilizar Terraform.
- No utilizar Helm.
- No utilizar múltiples bases de datos.
- No crear servicios adicionales.
- No añadir patrones, capas o abstracciones que no sean necesarias.
- No modificar archivos que no estén relacionados con la tarea actual.
- Mantener cada servicio pequeño y fácil de explicar.
- Preferir funciones simples sobre arquitecturas complejas.
- No avanzar a una etapa diferente de la solicitada.

# Fallos implementados

1. Caída del Servicio de Inventario.
2. Latencia de 20 segundos en Pagos.
3. Caída del Servicio de Notificaciones.
4. Condición de carrera por el último asiento.

# Mecanismos de resiliencia

1. Inventario: dos réplicas, distribución entre nodos, retries limitados y respuesta controlada.
2. Pagos: timeout y Circuit Breaker.
3. Notificaciones: fallback no crítico.
4. Condición de carrera: actualización SQL atómica.

# Fallos analizados teóricamente

1. Sobrecarga del API Gateway.
2. Conectividad intermitente con PostgreSQL.

# Forma de trabajo

Antes de modificar archivos:

1. Inspeccionar el repositorio.
2. Indicar brevemente qué archivos se crearán o modificarán.
3. Limitarse a la tarea actual.

Después de modificar archivos:

1. Ejecutar las pruebas relacionadas.
2. Mostrar un resumen de cambios.
3. Informar cualquier error pendiente.
4. No iniciar la siguiente etapa automáticamente.
