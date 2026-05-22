# Messaging Architecture — RabbitMQ / IBM MQ

## Queue Topology

```
EXCHANGE: neopay.payments (topic)
│
├── neopay.authorization
│   ├── queue: auth.authorization.request      (core payment processing)
│   ├── queue: auth.authorization.3ds         (3D Secure)
│   ├── queue: auth.authorization.fraud       (fraud scoring)
│   └── queue: auth.authorization.callback     (PSP callbacks)
│
├── neopay.financial
│   ├── queue: financial.capture.request
│   ├── queue: financial.capture.batch         (batch capture)
│   ├── queue: financial.refund.request
│   └── queue: financial.settlement.trigger
│
├── neopay.events
│   ├── queue: events.payment.created
│   ├── queue: events.payment.status_changed
│   ├── queue: events.payment.settled
│   └── queue: events.payment.failed
│
├── neopay.settlement
│   ├── queue: settlement.reconciliation
│   ├── queue: settlement.file_generation
│   └── queue: settlement.acquirer_sync
│
├── neopay.network
│   ├── queue: network.acquirer.iso8583        (ISO8583 outbound)
│   ├── queue: network.acquirer.response       (ISO8583 response handling)
│   ├── queue: network.openbanking.psd2
│   └── queue: network.webhook.outbound
│
└── neopay.admin
    ├── queue: admin.key_ceremony
    ├── queue: admin.terminal_management
    └── queue: admin.health_check
```

## Dead Letter Queue Strategy

```python
# DLQ configuration for failed messages
DLQ_CONFIG = {
    "auth": {
        "dlx": "neopay.auth.dlx",
        "queue": "auth.authorization.dlq",
        "max_retries": 3,
        "retry_delay": [5, 30, 120],  # seconds
        "on_final_failure": "alert_ops",
    },
    "financial": {
        "dlx": "neopay.financial.dlx",
        "queue": "financial.capture.dlq",
        "max_retries": 5,
        "retry_delay": [10, 30, 60, 300, 900],
        "on_final_failure": "suspend_transaction",
    },
    "settlement": {
        "dlx": "neopay.settlement.dlx",
        "queue": "settlement.reconciliation.dlq",
        "max_retries": 10,
        "retry_delay": [30, 60, 120, 300, 600, 1800, 3600, 7200, 14400, 28800],
        "on_final_failure": "manual_reconciliation",
    }
}

# DLQ message handler
def dlq_handler(channel, method, properties, body):
    msg = json.loads(body)
    routing_key = properties.headers.get("x-original-routing-key", "unknown")
    
    # Log for investigation
    logger.error(f"DLQ message: routing_key={routing_key}, "
                 f"retry_count={properties.headers.get('x-retry-count', 0)}, "
                 f"error={msg.get('error')}")
    
    # Alert on repeated failures
    if properties.headers.get("x-retry-count", 0) >= 3:
        alert_ops(f"Message stuck in DLQ after 3 retries: {routing_key}")
    
    channel.basic_ack(delivery_tag=method.delivery_tag)
```

## Consumer Groups (Scalability)

```python
# Multiple consumers for horizontal scaling
# RabbitMQ distributes messages across consumers in same group

def setup_consumer(channel: Channel, queue: str, group_id: str):
    # Each consumer gets a unique consumer_tag
    consumer_tag = f"{group_id}-{socket.gethostname()}-{os.getpid()}"
    
    channel.basic_qos(prefetch_count=10)  # Process 10 msgs concurrently
    
    channel.basic_consume(
        queue=queue,
        consumer_tag=consumer_tag,
        on_message_callback=process_message,
        auto_ack=False  # Manual ack for reliability
    )

# For high-throughput queues (auth), use multiple consumers
for i in range(N_WORKERS):
    t = threading.Thread(target=run_consumer, args=(i,))
    t.start()

def run_consumer(worker_id: int):
    connection = pika.BlockingConnection(RABBITMQ_URL)
    channel = connection.channel()
    setup_consumer(channel, "auth.authorization.request", "auth-workers")
    channel.start_consuming()
```

## Message Schema

```python
# Base message envelope
class PaymentMessage(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    correlation_id: UUID  # Links request/response
    message_type: str      # e.g., "auth.request"
    version: str = "1.0"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str           # e.g., "pos-terminal-001"
    destination: str       # e.g., "auth-engine"
    priority: int = 5      # 1=highest, 9=lowest
    payload: dict          # The actual payload
    headers: dict = {}     # Custom headers
    retry_count: int = 0

# Authorization request message
class AuthorizationRequest(PaymentMessage):
    message_type: Literal["auth.request"]
    payload: AuthorizationPayload

class AuthorizationPayload(BaseModel):
    terminal_id: str
    merchant_id: str
    pan_encrypted: str           # Or vault token
    amount: Decimal
    currency: str
    transaction_type: str
    stan: str                    # System Trace Audit Number
    timestamp: datetime
    de_55: str | None = None    # EMV data
    de_52: str | None = None    # PIN block
```

## Publisher Patterns

```python
# Reliable publishing with publisher confirms
class ReliablePublisher:
    def __init__(self, channel: Channel):
        self.channel = channel
        self.channel.confirm_delivery()  # Enable confirms
    
    def publish(self, routing_key: str, message: PaymentMessage, 
                mandatory: bool = True, immediate: bool = False):
        properties = pika.BasicProperties(
            delivery_mode=2,           # Persistent
            content_type="application/json",
            message_id=str(message.message_id),
            correlation_id=str(message.correlation_id),
            timestamp=int(message.timestamp.timestamp()),
            headers=message.headers,
            priority=message.priority,
            reply_to="neopay.payments.auth.response"  # For RPC pattern
        )
        
        try:
            self.channel.publish(
                exchange="neopay.payments",
                routing_key=routing_key,
                body=message.model_dump_json(),
                properties=properties,
                mandatory=mandatory,
                immediate=immediate
            )
        except NackError:
            # Handle failed publish (retry or DLQ)
            handle_publish_failure(message, routing_key)
```

## IBM MQ Configuration

```yaml
# For IBM MQ (when connecting to legacy acquirers)
ibm_mq:
  connection:
    host: "acquirer.ibm-mq.example.com"
    port: 1414
    channel: "NEOPAY.CHANNEL"
    queue_manager: "ACQ_QM"
    
  security:
    cipher_suite: "TLS_AES_256_GCM_SHA384"
    verify_mode: "REQUIRE"
    client_auth: true
    
  queues:
    outbound: "NEOPAY.OUTBOUND.Q"
    inbound: "NEOPAY.INBOUND.Q"
    dlq: "NEOPAY.DLQ"
    
  tuning:
    concurrent_puts: 10
    sync_point: true  # Exactly-once delivery
    read_ahead: 50
```

## RabbitMQ Clustering

```
┌─────────────────────────────────────────────────────────────┐
│  RabbitMQ Cluster (3 nodes)                                 │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   node-1     │  │   node-2     │  │   node-3     │       │
│  │  (master)    │◄─│  (mirror)    │◄─│  (mirror)    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                 │                 │               │
│  HAProxy / AWS LB (Client connections)                        │
│         │                 │                 │               │
└─────────┼─────────────────┼─────────────────┼───────────────┘
          │                 │                 │
          ▼                 ▼                 ▼
      Publishers          Consumers        Management UI
```

```yaml
# RabbitMQ cluster config
rabbitmq:
  cluster:
    nodes:
      - host: rabbit-1.neopay.internal
        port: 5672
      - host: rabbit-2.neopay.internal
        port: 5672
      - host: rabbit-3.neopay.internal
        port: 5672
    
    ha_policy:
      mode: "exactly"
      ha-sync-mode: "automatic"
      ha-sync-batch-size: 1
      promotion_policy: "prefer-master"
  
  memory:
    vm_memory_high_watermark: 0.7  # Alert at 70%
    disk_space_low_watermark: 1GB
  
  logging:
    level: warning
    log_file: "/var/log/rabbitmq/rabbitmq.log"
    file_handler_rotation: daily
  
  monitoring:
    prometheus_port: 15692
    metrics_interval: 30s
```

## Rate Limiting & Backpressure

```python
# Consumer-side rate limiting
class RateLimitedConsumer:
    def __init__(self, max_rps: int):
        self.rate_limiter = TokenBucket(capacity=max_rps, refill_rate=max_rps)
    
    def on_message(self, channel, method, properties, body):
        # Wait for rate limit token
        self.rate_limiter.wait_for_token()
        
        try:
            result = self.process(body)
            channel.basic_ack(delivery_tag=method.delivery_tag)
        except Exception as e:
            # Requeue with delay
            channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)
            self.handle_error(e)

# Backpressure: slow down producers when consumer is overwhelmed
class BackpressurePublisher:
    def publish(self, routing_key: str, message: PaymentMessage):
        queue_depth = get_queue_depth(routing_key)
        
        if queue_depth > HIGH_WATER_MARK:
            # Apply backpressure
            logger.warning(f"Queue {routing_key} has {queue_depth} messages, slowing down")
            sleep(QUEUE_DEPTH / MAX_RPS)
        
        self._do_publish(routing_key, message)
```

## Health Monitoring

```python
# RabbitMQ health checks
HEALTH_CHECK_INTERVAL = 30  # seconds

def rabbitmq_health_check():
    try:
        # Check connection
        connection = pika.BlockingConnection(RABBITMQ_URL)
        
        # Check each critical queue
        queues = [
            "auth.authorization.request",
            "financial.capture.request",
            "settlement.reconciliation",
        ]
        
        for queue in queues:
            result = connection.channel().queue_declare(
                queue=queue, durable=True, passive=True
            )
            message_count = result.method.message_count
            
            if message_count > CRITICAL_THRESHOLD:
                alert_ops(f"Queue {queue} has {message_count} messages (critical)")
        
        connection.close()
        return True
    except Exception as e:
        alert_ops(f"RabbitMQ health check failed: {e}")
        return False
```