# Arquitectura

```mermaid
flowchart TB
    client["Cliente"]

    subgraph logical["Arquitectura lógica"]
        gateway["API Gateway<br/>1 réplica"]
        reservations["Servicio de Reservas<br/>1 réplica"]
        inventoryService["Service Inventario<br/>ClusterIP"]
        payments["Servicio de Pagos<br/>1 réplica"]
        notifications["Servicio de Notificaciones<br/>1 réplica"]
        postgres["PostgreSQL<br/>1 réplica"]
        pvc[("PVC postgres-data<br/>1 Gi")]
    end

    client -->|"HTTP REST<br/>localhost:8080 → NodePort 30080"| gateway
    gateway -->|"REST/JSON"| reservations
    gateway -->|"REST/JSON"| inventoryService
    reservations -->|"REST/JSON"| inventoryService
    reservations -->|"REST/JSON"| payments
    reservations -->|"REST/JSON"| notifications
    reservations -->|"SQL"| postgres
    postgres ---|"persistencia"| pvc

    subgraph physical["Distribución física en tickets-cluster"]
        subgraph controlPlane["tickets-cluster-control-plane"]
            control["Kubernetes control plane"]
            gatewayExample["API Gateway<br/>ubicación solo ilustrativa<br/>sin nodeSelector"]
        end

        subgraph workerOne["tickets-cluster-worker"]
            inventoryOne["Inventario, réplica 1"]
            otherPodsOne["Otros pods<br/>según scheduler"]
        end

        subgraph workerTwo["tickets-cluster-worker2"]
            inventoryTwo["Inventario, réplica 2"]
            otherPodsTwo["Otros pods<br/>según scheduler"]
        end
    end

    inventoryService -->|"REST/JSON"| inventoryOne
    inventoryService -->|"REST/JSON"| inventoryTwo
    inventoryOne -->|"SQL"| postgres
    inventoryTwo -->|"SQL"| postgres

    gateway -.->|"posible colocación; no garantizada"| gatewayExample
    spread["topologySpreadConstraints<br/>kubernetes.io/hostname"]
    spread -.-> inventoryOne
    spread -.-> inventoryTwo
```

Las comunicaciones entre servicios son REST con JSON. El acceso desde el host llega a `localhost:8080`, que kind mapea al `NodePort 30080` del API Gateway. Las conexiones de Reservas e Inventario con PostgreSQL utilizan SQL.

Inventario es el único componente con una regla explícita de distribución: sus dos réplicas usan `topologySpreadConstraints` con `kubernetes.io/hostname`, por lo que se ubican en workers distintos. El API Gateway no tiene `nodeSelector`; su aparición en el control-plane es únicamente ilustrativa. Reservas, Pagos, Notificaciones y PostgreSQL tampoco tienen una ubicación fija y son asignados por el scheduler a un nodo disponible.

| Componente | Réplicas | Tipo de Service | Dependencia | Función |
|---|---:|---|---|---|
| API Gateway | 1 | NodePort `30080` | Reservas e Inventario | Punto de entrada externo y reenvío de solicitudes REST |
| Servicio de Reservas | 1 | ClusterIP | Inventario, Pagos, Notificaciones y PostgreSQL | Orquestar el flujo mínimo de reserva y persistir su resultado |
| Servicio de Inventario | 2 | ClusterIP | PostgreSQL | Consultar disponibilidad y reservar o liberar asientos mediante SQL atómico |
| Servicio de Pagos | 1 | ClusterIP | Ninguna | Simular la aprobación, latencia o fallo de un pago |
| Servicio de Notificaciones | 1 | ClusterIP | Ninguna | Simular el envío de una notificación |
| PostgreSQL | 1 | ClusterIP | PVC `postgres-data` de 1 Gi | Persistir inventario y reservas |
