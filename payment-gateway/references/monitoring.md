# Monitoring & Observability — Payment Gateway

## Prometheus Metrics

### Core Transaction Metrics
```
# Authorization throughput
payment_authorizations_total{status="approved|declined|error", network="visa|mastercard|amex"}

# Capture and settlement
payment_captures_total{status="success|failed", merchant_id="..."}
payment_settlements_total{status="settled|failed|pending"}

# Latency histogram (buckets: 0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)
payment_processing_duration_seconds{stage="fraud|hsmmac|scheme|response", mti="0100|0200|0400"}

# Error rates
payment_errors_total{type="timeout|invalid|scheme_error|hsm_failure", code="..."}
```

### HSM Metrics
```
hsm_operations_total{op="encrypt_pin|decrypt_pin|generate_mac|verify_mac|generate_key|translate_key", status="success|failure"}
hsm_operation_duration_seconds{op="..."}
hsm_connection_pool_active{host="..."}
hsm_connection_pool_idle{host="..."}
hsm_key_check_failures_total
```

### Message Queue Metrics
```
kafka_consumer_lag{topic="payment-requests|payment-responses", group="..."}
rabbitmq_queue_depth{name="payment-switch|clearing|settlement"}
queue_publish_duration_seconds{queue="...", status="..."}
```

### JVM / Application
```
jvm_gc_pause_seconds{gc="G1 Young Generation|G1 Old Generation"}
jvm_memory_used_bytes{area="heap|nonheap"}
thread_count_active{state="runnable|blocked|waiting"}
db_connection_pool_active{pool="hikari|oracle"}
db_query_duration_seconds{database="ledger|settlement", query="select|insert|update"}
```

## Grafana Dashboards

### payment_overview.json
- TPS line graph (real-time, 1-minute window)
- Latency histogram (p50/p95/p99)
- Error rate gauge (< 1% green, > 1% red)
- Active connections table
- Top response codes pie chart
- Transaction volume by network bar chart

### hsm_metrics.json
- Key operation rate (ops/sec)
- MAC verification success/failure rate
- PIN block translation rate
- Connection pool utilization (stacked)
- Average operation latency per operation type
- HSM error frequency by error code

### scheme_interface.json
- Messages by MTI (stacked area)
- Response code distribution (pie)
- Timeout rate per scheme
- Average response time per MTI
- Message size distribution
- Scheme availability heatmap

### kubernetes_workloads.json
- Pod status count (running/pending/failed)
- CPU utilization per pod
- Memory utilization per pod
- Restart count per pod (last 24h)
- Network I/O (bytes in/out)
- HPA scale events timeline

## Alerting Rules (Prometheus)

```yaml
groups:
  - name: payment-gateway
    rules:
      - alert: TPSBelowThreshold
        expr: rate(payment_authorizations_total[5m]) < 100
        for: 5m
        labels: severity: critical
        annotations:
          summary: "TPS below minimum threshold"

      - alert: ErrorRateAbove1Percent
        expr: |
          (sum(rate(payment_errors_total[5m])) /
           sum(rate(payment_authorizations_total[5m]))) > 0.01
        for: 2m
        labels: severity: critical
        annotations:
          summary: "Error rate above 1%"

      - alert: LatencyP99Above5s
        expr: histogram_quantile(0.99, rate(payment_processing_duration_seconds_bucket[5m])) > 5
        for: 3m
        labels: severity: warning
        annotations:
          summary: "p99 latency exceeds 5 seconds"

      - alert: HSMConnectionPoolSaturated
        expr: |
          (sum(hsm_connection_pool_active) /
           sum(hsm_connection_pool_active + hsm_connection_pool_idle)) > 0.80
        for: 1m
        labels: severity: warning

      - alert: SchemeInterfaceDown
        expr: up{job="scheme-interface"} == 0
        for: 1m
        labels: severity: critical
        annotations:
          summary: "Scheme interface unreachable"

      - alert: CertificateExpiry
        expr: |
          (certify_not_after - time()) < 86400 * 30
        for: 1h
        labels: severity: warning
        annotations:
          summary: "Certificate expires in less than 30 days"
```

## SLI / SLO

| Service | Availability | Latency p99 | Error Rate |
|---------|-------------|------------|------------|
| Authorization API | 99.95% | < 2s | < 0.5% |
| HSM operations | 99.9% | < 500ms | < 0.1% |
| Message routing | 99.99% | < 100ms | < 0.01% |
| Webhook delivery | 99.5% | < 5s | < 0.5% |

## Distributed Tracing (Jaeger/X-Ray)

- Trace: incoming request → fraud check → HSM → scheme → response
- Span attributes: transaction_id, merchant_id, MTI, network
- Sampling: 10% normal, 100% on error
- Parent span propagation via W3C TraceContext headers

## Log Aggregation (EFK)

- Format: JSON structured logs
- Fields: timestamp, level, service, transaction_id, merchant_id, correlation_id
- Index pattern: `paybox-logs-YYYY.MM.DD`
- Retention: 30 days (hot), 1 year (archive)
- Log levels: DEBUG (dev), INFO (prod normal), WARN (degraded), ERROR (incident)

## Runbook Templates

### High TPS Drop
1. Check scheme interface health
2. Check HSM connection pool
3. Check message queue depth
4. Review recent deployments
5. Scale pods if needed: `kubectl scale deployment payment-engine --replicas=10`

### HSM Failures
1. Check HSM connectivity: `nc -zv hsm-host 9999`
2. Check key check values in vault
3. Verify LMK is loaded on HSM
4. Failover to standby HSM if configured
5. Alert HSM vendor if sustained

### Database Connection Exhaustion
1. Check `db_connection_pool_active` metric
2. Review long-running queries: `SELECT * FROM v$session WHERE type='USER'`
3. Kill sessions > 60s: `ALTER SYSTEM KILL SESSION 'sid,serial#' IMMEDIATE`
4. Increase pool size (temporary): `ALTER SYSTEM SET processes=300 SCOPE=SPFILE`
5. Page DBA on-call