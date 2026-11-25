# RouteWise database

```mermaid
erDiagram
  LOCATION ||--o{ ROAD : starts
  LOCATION ||--o{ ROAD : ends
  LOCATION ||--o{ ROUTE : originates
  LOCATION ||--o{ ROUTE_LEG : starts
  LOCATION ||--o{ ROUTE_LEG : ends
  ROUTE ||--o{ ROUTE_LEG : contains
  LOCATION {
    INTEGER id PK
    TEXT code UK
    TEXT name
    TEXT kind
    REAL x
    REAL y
  }
  ROAD {
    INTEGER id PK
    INTEGER from_id FK
    INTEGER to_id FK
    REAL distance_km
    INTEGER is_one_way
    INTEGER is_closed
  }
  ROUTE {
    INTEGER id PK
    TEXT created_at
    TEXT mode
    INTEGER origin_id FK
    REAL total_km
    REAL avg_speed_kmh
  }
  ROUTE_LEG {
    INTEGER route_id PK,FK
    INTEGER seq PK
    INTEGER from_id FK
    INTEGER to_id FK
    REAL km
    INTEGER is_delivery_stop
  }
```

Road records have a unique ordered endpoint pair. Each two-way road is stored
once with the smaller location ID first. Deleting a route cascades to its
legs. References from roads, routes and legs restrict deletion of locations.
Routes and legs are part of the schema; the planning and history workflows
are implemented in later checkpoints.
