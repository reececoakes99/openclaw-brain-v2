# Scaling Guide — Playwrights

## Horizontal Scaling

### API Layer
```
                          ┌─────────────┐
Client → CDN → ALB ────────┤  API Replica 1  │  (async FastAPI, gunicorn)
        (rate limit)      ├─────────────┤
        per-token         │  API Replica 2  │  (4 workers each)
        bucket            ├─────────────┤
        limiter           │  API Replica 3  │
                          └─────────────┘
```

- Add replicas behind load balancer (ALB / Traefik / nginx)
- Each replica: 4 gunicorn workers (1 per CPU core)
- Stateless: all state in Redis + PostgreSQL
- No sticky sessions required

### Worker Layer (Browser Pool)
```
Redis Queue ──┬── Worker 1 ── Browser Pool A (Chromium × N)
             ├── Worker 2 ── Browser Pool B (Chromium × M)
             ├── Worker 3 ── Browser Pool C (Chromium × K)
             └── Worker 4 ── Browser Pool D (Chromium × J)
```

- Each worker: 1 Redis consumer
- Pool size per worker: 2-4 browsers (configurable)
- Total concurrency = `workers × pool_size`
- Auto-scale workers based on queue depth:
  - `queue_depth > 100` → scale up workers
  - `queue_depth < 10` → scale down workers

### PostgreSQL Scaling
- PgBouncer connection pooling: `min=5, max=20, pool_mode=transaction`
- Read replicas for read-heavy queries (task history, reporting)
- Partition `tasks` table by `created_at` (monthly partitions)

### Redis Scaling
- Single node: sufficient for < 10K concurrent tasks
- Cluster mode: for high-throughput (partitioning by task_id hash)
- `maxmemory 512mb` with `allkeys-lru` eviction
- Pipeline bulk operations for multi-key gets/sets

## Memory Management

```python
# Restart browser after N tasks to prevent memory leaks
MAX_TASKS_PER_BROWSER = 50

class BrowserPool:
    def __init__(self, browser_type='chromium', pool_size=4):
        self.browser_type = browser_type
        self.pool_size = pool_size
        self.tasks_per_browser = {}
    
    def get_browser(self):
        for browser in self.browsers:
            if self.tasks_per_browser[browser] < MAX_TASKS_PER_BROWSER:
                return browser
        # Launch new browser
        b = self.launch()
        self.browsers.append(b)
        self.tasks_per_browser[b] = 0
        return b
    
    def release(self, browser):
        self.tasks_per_browser[browser] += 1
        if self.tasks_per_browser[browser] >= MAX_TASKS_PER_BROWSER:
            self.restart(browser)  # kill and relaunch clean
```

## Rate Limiting

```python
# Token bucket rate limiter per API key
RATE_LIMIT = {
    "free": {"requests": 100, "period": 60},      # 100 req/min
    "pro":  {"requests": 1000, "period": 60},    # 1000 req/min
    "biz":  {"requests": 10000, "period": 60},   # 10000 req/min
}
```

```python
from ratelimit import limits, sleep_and_retry

@sleep_and_retry
@limits(calls=100, period=60)
def api_endpoint():
    # Rate limited
    pass
```

## CDN for Static Assets

```nginx
# Serve static/browser binaries from CDN
location /static/ {
    expires 1y;
    add_header Cache-Control "public, immutable";
}
```

## Load Testing

```python
# locustfile.py
from locust import HttpUser, task, between

class PlaywrightsUser(HttpUser):
    wait_time = between(0.5, 2)
    
    @task
    def create_task(self):
        self.client.post("/tasks", json={"intent": "go to google.com", "browser": "chromium"})
    
    @task(3)
    def get_result(self):
        task_id = self.environment.runner.task_ids[-1] if self.environment.runner.task_ids else "test-id"
        self.client.get(f"/tasks/{task_id}/result")
```

```bash
locust -f locustfile.py --headless -t 300s -r 50 -H https://playwrights.example.com --csv results
```