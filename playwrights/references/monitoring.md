# Monitoring & Observability — Playwrights

## Prometheus Metrics

### HTTP API Metrics
```
# Request throughput (requests/sec)
playwrights_http_requests_total{method, endpoint, status_code}

# Request latency histogram (buckets: 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
playwrights_http_request_duration_seconds{method, endpoint, status_code}

# Request size bytes
playwrights_http_request_size_bytes{method, endpoint}
playwrights_http_response_size_bytes{method, endpoint}
```

### Browser Metrics
```
# Browser launch count
playwrights_browser_launches_total{browser_type, worker_id, status}
# status: success, crashed, timeout, error

# Active browser pool size
playwrights_browser_pool_active{browser_type, worker_id}

# Browser session duration
playwrights_browser_session_duration_seconds{browser_type}

# Browser memory usage (MB)
playwrights_browser_memory_mb{browser_type, worker_id}
```

### Queue Metrics
```
# Redis queue depth per worker
playwrights_queue_depth{worker_id}

# Queue add rate
playwrights_queue_adds_total

# Queue processed rate
playwrights_queue_processed_total{status}
```

### Database Metrics
```
# PostgreSQL query duration
playwrights_db_query_duration_seconds{query_type}
# query_type: select, insert, update, delete

# PostgreSQL connection pool
playwrights_db_connections_active{pool}
playwrights_db_connections_idle{pool}
```

## Grafana Dashboards

### playwrights_overview.json
- **Request Rate** (line graph): rate of HTTP requests over time, broken by endpoint
- **Latency** (heatmap or histogram): p50 / p95 / p99 latency per endpoint
- **Browser Health** (gauge panel): launch count vs crash count, crash rate %
- **Queue Depth** (time series): Redis queue depth over time per worker
- **Error Rate** (stat panel): HTTP 5xx / total requests as percentage
- **DB Query Duration** (histogram): average query time per query type
- **Redis Operations** (rate panel): reads/writes per second

### browser_health.json
- **Pool Utilization** (stacked area): active browsers per worker per type
- **Crash Rate Over Time** (line): crashes/launches per 5-minute window
- **Average Session Duration** (gauge): mean browser session length
- **Memory Per Browser** (time series): RSS memory in MB per process
- **Most Common Crash Reasons** (table): from structured log fields

## Health Check Endpoints

```
GET /health  — liveness probe
  Returns: {"status": "alive", "uptime": 12345}
  Response 200 if alive, 503 if shutting down

GET /ready  — readiness probe
  Checks: Redis connectivity + PostgreSQL connectivity
  Returns: {"status": "ready", "redis": "ok", "db": "ok"}
  Response 503 if any dependency down

GET /metrics  — Prometheus scrape endpoint
  Content-Type: text/plain; version=0.0.4
```

## Structured Logging

```python
import logging, json

class StructuredFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": "playwrights-api",
            "correlation_id": request.headers.get("X-Correlation-ID", "-"),
            "message": record.getMessage(),
            "logger": record.name,
        }
        if hasattr(record, "task_id"):
            log_data["task_id"] = record.task_id
        if hasattr(record, "duration_ms"):
            log_data["duration_ms"] = record.duration_ms
        return json.dumps(log_data)
```

Log fields: `ts`, `level`, `service`, `correlation_id`, `message`, `task_id`, `duration_ms`, `error`

## Alert Rules

```yaml
groups:
  - name: playwrights
    rules:
      - alert: PlaywrightAPIErrorRate
        expr: |
          (sum(rate(playwrights_http_requests_total{status_code=~"5.."}[5m])) /
           sum(rate(playwrights_http_requests_total[5m]))) > 0.05
        for: 2m
        labels: {severity: critical}
        annotations:
          summary: "API error rate above 5%"

      - alert: BrowserCrashRateHigh
        expr: |
          (sum(rate(playwrights_browser_launches_total{status="crashed"}[10m])) /
           sum(rate(playwrights_browser_launches_total[10m]))) > 0.01
        for: 5m
        labels: {severity: warning}
        annotations:
          summary: "Browser crash rate above 1%"

      - alert: QueueDepthHigh
        expr: playwrights_queue_depth > 1000
        for: 3m
        labels: {severity: warning}
        annotations:
          summary: "Redis queue depth exceeds 1000"

      - alert: DatabaseConnectionPoolSaturated
        expr: |
          (playwrights_db_connections_active /
           (playwrights_db_connections_active + playwrights_db_connections_idle)) > 0.80
        for: 2m
        labels: {severity: warning}
        annotations:
          summary: "Database connection pool > 80% utilized"

      - alert: APILatencyP95High
        expr: histogram_quantile(0.95, rate(playwrights_http_request_duration_seconds_bucket[5m])) > 10
        for: 3m
        labels: {severity: warning}
        annotations:
          summary: "p95 API latency exceeds 10 seconds"
```