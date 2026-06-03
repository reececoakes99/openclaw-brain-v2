# Docker Swarm Deployment — Playwrights

## Architecture

```
Manager Node(s)
├── Traefik (reverse proxy, auto-discovery)
└── Swarm Services
    ├── playwrights-api (3 replicas)
    ├── playwrights-worker (2 replicas)
    ├── postgres (1 replica, named volume)
    └── redis (1 replica, named volume)
```

## docker-compose.yml (Swarm Mode)

```yaml
version: '3.8'

networks:
  playwrights_internal:
    driver: overlay
    attachable: true

configs:
  api_config:
    file: ./configs/api_config.yaml
  worker_config:
    file: ./configs/worker_config.yaml

secrets:
  api_key:
    file: ./secrets/api_key.txt
  db_password:
    file: ./secrets/db_password.txt

services:
  playwrights-api:
    image: playwrights/api:latest
    deploy:
      replicas: 3
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
      restart_policy:
        condition: on-failure
        delay: 5s
        max_attempts: 3
      resources:
        limits:
          cpus: '2'
          memory: 4G
        reservations:
          cpus: '0.5'
          memory: 1G
    ports:
      - "8000:8080"
    env_file:
      - .env
    secrets:
      - api_key
      - db_password
    configs:
      - source: api_config
        target: /app/config.yaml
    healthcheck:
      test: ["CMD", "curl", "-sf", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3
      start_period: 30s
    logging:
      driver: fluentd
      options:
        fluentd-address: localhost:24224
        tag: playwrights-api
    networks:
      - playwrights_internal

  playwrights-worker:
    image: playwrights/worker:latest
    deploy:
      replicas: 2
      update_config:
        parallelism: 1
        delay: 10s
        order: start-first
      restart_policy:
        condition: on-failure
        max_attempts: 3
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '1'
          memory: 2G
    env_file:
      - .env
    secrets:
      - api_key
    configs:
      - source: worker_config
        target: /app/config.yaml
    depends_on:
      - redis
      - postgres
    logging:
      driver: fluentd
      options:
        fluentd-address: localhost:24224
        tag: playwrights-worker
    networks:
      - playwrights_internal

  postgres:
    image: postgres:15-alpine
    deploy:
      replicas: 1
      restart_policy:
        condition: always
      resources:
        limits:
          cpus: '1'
          memory: 2G
    environment:
      POSTGRES_DB: playwrights
      POSTGRES_USER: playwrights
    secrets:
      - db_password
    volumes:
      - playwrights-db-data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U playwrights"]
      interval: 10s
      timeout: 5s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: 10m
        max-file: '3'
    networks:
      - playwrights_internal

  redis:
    image: redis:7-alpine
    deploy:
      replicas: 1
      restart_policy:
        condition: always
      resources:
        limits:
          cpus: '0.5'
          memory: 1G
    command: redis-server --appendonly yes --maxmemory 512mb --maxmemory-policy allkeys-lru
    volumes:
      - playwrights-redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: 10m
        max-file: '3'
    networks:
      - playwrights_internal

  traefik:
    image: traefik:v3.0
    command:
      - "--providers.docker"
      - "--providers.docker.swarmMode"
      - "--providers.docker.exposedbydefault=false"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.letsencrypt.acme.email=admin@playwrights.example.com"
      - "--certificatesresolvers.letsencrypt.acme.storage=/letsencrypt/acme.json"
      - "--certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - traefik-certs:/letsencrypt
    depends_on:
      - playwrights-api
    networks:
      - playwrights_internal

volumes:
  playwrights-db-data:
    driver: local
  playwrights-redis-data:
    driver: local
  traefik-certs:
    driver: local
```

## Secrets Setup

```bash
# Generate secrets before deploy
openssl rand -base64 32 > secrets/api_key.txt
openssl rand -base64 32 > secrets/db_password.txt

# Initialize swarm
docker swarm init

# Deploy
docker stack deploy -c docker-compose.yml playwrights
```

## Init SQL

```sql
-- init.sql
CREATE TABLE IF NOT EXISTS tasks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(20) NOT NULL DEFAULT 'queued',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    result JSONB,
    error TEXT,
    browser_type VARCHAR(20),
    intent TEXT
);
CREATE INDEX idx_tasks_status ON tasks(status);
CREATE INDEX idx_tasks_created_at ON tasks(created_at);

CREATE TABLE IF NOT EXISTS results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID REFERENCES tasks(id),
    status VARCHAR(20),
    data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
CREATE INDEX idx_results_task_id ON results(task_id);
```

## Health Check Endpoints

```python
# /health — liveness (is the process alive?)
@app.get("/health")
async def health():
    return {"status": "alive"}

# /ready — readiness (can handle requests?)
@app.get("/ready")
async def ready():
    try:
        r = await get_redis()
        await r.ping()
        conn = await get_db()
        await conn.execute("SELECT 1")
        return {"status": "ready", "redis": "ok", "db": "ok"}
    except Exception as e:
        return {"status": "not_ready", "error": str(e)}, 503
```

## Scaling

```bash
# Scale API replicas
docker service scale playwrights_playwrights-api=5

# Scale worker replicas
docker service scale playwrights_playwrights-worker=4

# Check service status
docker service ls
docker service ps playwrights_playwrights-api

# Rollback
docker service rollback playwrights_playwrights-api
```

## Graceful Shutdown

```python
# SIGTERM handler in API
import signal, sys
shutdown_event = asyncio.Event()

def signal_handler(signum, frame):
    print("Received SIGTERM, shutting down gracefully...")
    shutdown_event.set()

signal.signal(signal.SIGTERM, signal_handler)

# On shutdown: stop accepting new requests, finish in-flight
@app.on_event("shutdown")
async def shutdown():
    await shutdown_event.wait()
    await cleanup()  # close DB pool, Redis, browser pools
```