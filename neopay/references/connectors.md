# Connectors Reference

Neopay's switch architecture connects multiple external systems via named connectors. Each connector type maps a FROM/TO relationship with specific protocols and configurations.

## Connector Architecture Overview

```
External System A    External System B    External System C
     │                      │                      │
     └──────────────────────┼──────────────────────┘
                            │
                     ┌──────┴──────┐
                     │   CONVERTER  │
                     │   / ROUTER   │
                     └──────┬──────┘
                            │
                  ┌─────────┼──────────┐
                  │         │          │
           ┌──────┴──┐ ┌────┴────┐ ┌──┴──────────┐
           │ Msg Broker │ │  DB     │ │   HSM      │
           │  Connector │ │Connector│ │ Connector  │
           └───────────┘ └─────────┘ └────────────┘
```

## Connector Types

### 1. Scheme Interface Connectors

**Connects FROM:** Visa / Mastercard / Amex / UnionPay / JCB
**Connects TO:** Neopay Interface Connector
**Protocol:** TCP/IP + TLS 1.2+, ISO8583

```yaml
# assets/connectors/scheme_visa.yaml
connector:
  name: "VISA_ACQUIRER"
  type: "SCHEME"
  direction: "INBOUND"
  scheme: "VISA"
  host: "visa-global-cert.acquirer.com"
  port: 8443
  protocol: "TCP_TLS"
  tls_version: "TLS_1_2"
  certificate:
    client_cert: "/certs/visa_client.pem"
    client_key: "/certs/visa_key.pem"
    ca_cert: "/certs/visa_ca.pem"
  message_format: "ISO8583_BINARY"
  heartbeat_interval: 30
  timeout: 60
  reconnect:
    max_attempts: 5
    backoff_seconds: 5
  routing:
    mti_filter:
      - "0100"  # Authorization
      - "0200"  # Financial
      - "0400"  # Reversal
    field_map:
      response_timeout: 45
```

### 2. Acquiring Connectors (POS / ATM)

**Connects FROM:** POS Devices, ATMs, Kiosks
**Connects TO:** Neopay POS Acquirer Connector
**Protocol:** TCP/IP, SPDH, HPDH, Verifone XFlow

```yaml
# assets/connectors/acquiring_pos.yaml
connector:
  name: "POS_ACQUIRING"
  type: "ACQUIRING"
  direction: "INBOUND"
  terminal_protocol: "HPDH_V2"
  listen:
    host: "0.0.0.0"
    port: 4001
  protocol_stack:
    transport: "TCP"
    session: "HPDH"
    presentation: "ISO8583"
  security:
    mac_required: true
    mac_algorithm: "ISO9797M1"
    pin_required: true
    pin_algorithm: "ISO9564F0"
    encryption: "TDES"
  heartbeat:
    interval_seconds: 30
    missed_threshold: 3
  session:
    max_idle_seconds: 300
    max_transactions_per_session: 1000
  routing:
    default_dest: "SWITCH_PROCESSOR"
    mti_map:
      "0100": "AUTHORIZATION_HOST"
      "0200": "AUTHORIZATION_HOST"
      "0400": "REVERSAL_HANDLER"
      "0800": "NETWORK_MGMT"
```

### 3. API Connectors

**Connects FROM:** Web / Mobile Apps, Merchant Portals
**Connects TO:** Neopay REST API
**Protocol:** HTTPS, JSON / XML

```yaml
# assets/connectors/api_merchant.yaml
connector:
  name: "MERCHANT_API"
  type: "API"
  direction: "INBOUND"
  framework: "FASTAPI"
  base_url: "https://api.neopay.io/v1"
  auth:
    type: "OAUTH2"  # or "API_KEY" or "JWT"
    jwt:
      algorithm: "RS256"
      public_key_path: "/keys/jwt_public.pem"
      expiry_hours: 1
    api_key:
      header: "X-API-Key"
      header_value: "${API_KEY}"
  rate_limit:
    requests_per_minute: 1000
    burst: 100
  endpoints:
    - path: "/payments"
      method: "POST"
      inbound_connector: "SWITCH_PROCESSOR"
      schema: "references/schemas/payment_create.yaml"
    - path: "/payments/{id}"
      method: "GET"
      inbound_connector: "QUERY_HOST"
    - path: "/webhooks"
      method: "POST"
      inbound_connector: "WEBHOOK_HANDLER"
      signature_header: "X-Neopay-Signature"
      signature_algo: "HMAC_SHA256"
  cors:
    allowed_origins: ["https://portal.neopay.io"]
    allowed_methods: ["GET", "POST"]
```

### 4. Message Broker Connectors

**Connects FROM:** Neopay Switch / Converter
**Connects TO:** Kafka / RabbitMQ / IBM MQ
**Protocol:** Native Broker Protocols

```yaml
# assets/connectors/msgbroker_kafka.yaml
connector:
  name: "KAFKA_MSG_BROKER"
  type: "MESSAGE_BROKER"
  direction: "INTERNAL"
  broker: "KAFKA"
  bootstrap_servers:
    - "kafka-1.neopay.io:9092"
    - "kafka-2.neopay.io:9092"
    - "kafka-3.neopay.io:9092"
  topics:
    - name: "iso8583-incoming"
      partitions: 16
      replication_factor: 3
      consumer_group: "switch_processor"
    - name: "iso8583-outgoing"
      partitions: 16
      replication_factor: 3
    - name: "settlement-events"
      partitions: 8
      replication_factor: 3
    - name: "authorization-requests"
      partitions: 32
      consumer_groups:
        - "auth_host_primary"
        - "auth_host_secondary"
  security:
    sasl_mechanism: "SCRAM-SHA-512"
    tls_enabled: true
  producer:
    acks: "all"
    retries: 3
    compression: "lz4"
  consumer:
    auto_offset_reset: "earliest"
    enable_auto_commit: false
    max_poll_records: 500
```

```yaml
# assets/connectors/msgbroker_rabbitmq.yaml
connector:
  name: "RABBITMQ_MSG_BROKER"
  type: "MESSAGE_BROKER"
  direction: "INTERNAL"
  broker: "RABBITMQ"
  host: "rabbitmq.neopay.io"
  port: 5672
  management_port: 15672
  vhost: "/neopay"
  tls: true
  auth:
    username: "${RABBITMQ_USER}"
    password: "${RABBITMQ_PASS}"
  exchanges:
    - name: "neopay.direct"
      type: "topic"
      durable: true
    - name: "neopay.dlx"
      type: "direct"
      durable: true  # Dead letter exchange
  queues:
    - name: "auth.requests"
      durable: true
      routing_key: "auth.request.*"
      dead_letter_exchange: "neopay.dlx"
      dead_letter_routing_key: "auth.failed"
      max_length: 100000
      message_ttl: 300000  # 5 minutes
    - name: "iso8583.switch.in"
      durable: true
      routing_key: "iso.in.#"
    - name: "iso8583.switch.out"
      durable: true
      routing_key: "iso.out.#"
```

### 5. Cloud Messaging Connectors

**Connects FROM:** Neopay Switch
**Connects TO:** AWS SQS / Google Pub/Sub
**Protocol:** Cloud Provider APIs

```yaml
# assets/connectors/cloud_sqs.yaml
connector:
  name: "AWS_SQS_CLOUD"
  type: "CLOUD_MESSAGING"
  direction: "INTERNAL"
  provider: "AWS"
  region: "eu-west-1"
  service: "sqs"
  queues:
    - name: "neopay-fifo"
      url: "https://sqs.eu-west-1.amazonaws.com/ACCOUNT/neopay-fifo"
      fifo: true
      visibility_timeout: 30
      receive_wait_time: 20
      delay_seconds: 0
      max_message_size: 262144
      message_retention_seconds: 1209600
```

```yaml
# assets/connectors/cloud_pubsub.yaml
connector:
  name: "GCP_PUBSUB_CLOUD"
  type: "CLOUD_MESSAGING"
  direction: "INTERNAL"
  provider: "GCP"
  project: "neopay-production"
  topics:
    - name: "payment-events"
      subscription: "switch-processor-sub"
      ack_deadline_seconds: 60
    - name: "settlement-trigger"
      subscription: "settlement-sub"
      retry_policy:
        minimum_backoff: "10s"
        maximum_backoff: "600s"
```

### 6. Database Connectors

**Connects FROM:** Neopay Host / Converter
**Connects TO:** Oracle / DB2 / SQL / NoSQL
**Protocol:** JDBC / Native DB Drivers

```yaml
# assets/connectors/db_oracle.yaml
connector:
  name: "ORACLE_LEDGER"
  type: "DATABASE"
  direction: "INTERNAL"
  db_type: "ORACLE"
  host: "oracle-primary.neopay.io"
  port: 1521
  service_name: "NEOPAYDB"
  pool:
    min_connections: 10
    max_connections: 100
    connection_timeout: 30
    idle_timeout: 300
    max_lifetime: 3600
  readonly: false
  jdbc_url: "jdbc:oracle:thin:@oracle-primary.neopay.io:1521:NEOPAYDB"
  credentials:
    username: "${ORACLE_USER}"
    password: "${ORACLE_PASS}"
```

```yaml
# assets/connectors/db_mongodb.yaml
connector:
  name: "MONGODB_TXLOG"
  type: "DATABASE"
  direction: "INTERNAL"
  db_type: "MONGODB"
  replica_set: "rs0"
  hosts:
    - "mongo-1.neopay.io:27017"
    - "mongo-2.neopay.io:27017"
    - "mongo-3.neopay.io:27017"
  database: "txlog"
  collection: "transactions"
  write_concern: "majority"
  read_preference: "secondaryPreferred"
```

### 7. HSM Connectors

**Connects FROM:** Neopay Host / Interface
**Connects TO:** Physical or Cloud HSM
**Protocol:** TCP/IP, Proprietary HSM API

```yaml
# assets/connectors/hsm_thales.yaml
connector:
  name: "THALES_PAYSHIELD_HSM"
  type: "HSM"
  direction: "INTERNAL"
  hsm_type: "THALES_PAYSHIELD_9000"
  host: "hsm-primary.neopay.io"
  port: 8888
  connection_pool:
    min_connections: 5
    max_connections: 50
  timeout_ms: 5000
  retry:
    max_attempts: 3
    backoff_ms: 100
  commands_enabled:
    - "NC"   # PIN translation
    - "KQ"   # ARQC verify
    - "KV"   # ARPC generate
    - "QA"   # MAC generate
    - "QB"   # MAC verify
    - "KA"   # Generate key
    - "KC"   # Import key
    - "KD"   # Export key
  failover:
    host: "hsm-secondary.neopay.io"
    port: 8888
    health_check_interval: 10
```

### 8. Clearing Connectors

**Connects FROM:** Neopay Clearing Module
**Connects TO:** Scheme Settlement Systems
**Protocol:** FTP/SFTP, HTTP, Batch Files (CTF, IPM)

```yaml
# assets/connectors/clearing_visa.yaml
connector:
  name: "VISA_CLEARING"
  type: "CLEARING"
  direction: "OUTBOUND"
  settlement_type: "NET_SETTLEMENT"
  file_format: "CTF"  # or "IPM"
  protocols:
    - type: "SFTP"
      host: "settlement.visa.com"
      port: 22
      username: "${VISA_SETTLE_USER}"
      key_path: "/keys/visa_sftp_key.pem"
      inbound_dir: "/inbound/"
      outbound_dir: "/outbound/"
    - type: "HTTP_API"
      url: "https://settlement-api.visa.com/v1/clearing"
      method: "POST"
  schedule:
    frequency: "DAILY"
    cutoff_hour: 21
    timezone: "UTC"
  reconciliation:
    enabled: true
    match_fields: ["amount", "currency", "card_last4"]
```

### 9. SIEM Connectors

**Connects FROM:** Neopay Alerts / Data Warehouse
**Connects TO:** Enterprise SIEM (Splunk / ELK)
**Protocol:** Syslog, CEF, LEEF, Webhooks

```yaml
# assets/connectors/siem_splunk.yaml
connector:
  name: "SPLUNK_SIEM"
  type: "SIEM"
  direction: "OUTBOUND"
  provider: "SPLUNK"
  hec_url: "https://splunk.neopay.io:8088/services/collector/event"
  token: "${SPLUNK_HEC_TOKEN}"
  index: "neopay_security"
  source: "neopay_switch"
  sourcetype: "neopay:iso8583"
  batch_size: 100
  flush_interval_seconds: 5
```

### 10. Threat Intel Connectors

**Connects FROM:** External Threat Feeds
**Connects TO:** Neopay Switch Router
**Protocol:** REST API, JSON

```yaml
# assets/connectors/threat_intel.yaml
connector:
  name: "THREAT_INTEL_FEED"
  type: "THREAT_INTEL"
  direction: "INBOUND"
  sources:
    - name: "THREATSTREAM"
      api_url: "https://api.anomali.com/v2/intel"
      api_key: "${THREATSTREAM_KEY}"
      poll_interval_minutes: 15
      indicator_types: ["ip", "domain", "md5", "sha256"]
    - name: "IBM_X_FORCE"
      api_url: "https://api.xforce.ibmcloud.com"
      api_key: "${IBM_XFORCE_KEY}"
  rules:
    - name: "BLOCK_CARD_RANGE"
      action: "BLOCK_TXN"
      priority: "HIGH"
    - name: "BLOCK_SUSPICIOUS_IP"
      action: "FLAG_AND_REVIEW"
      priority: "MEDIUM"
```

## Connector Configuration Template

```yaml
# assets/connectors/_template.yaml
connector:
  name: "<CONNECTOR_NAME>"
  type: "<TYPE>"
  direction: "<INBOUND|OUTBOUND|INTERNAL>"
  priority: <1-10>
  enabled: true
  
  # Connection
  host: "<hostname>"
  port: <port>
  tls: <true|false>
  
  # Protocol
  protocol: "<PROTOCOL_NAME>"
  message_format: "<FORMAT>"
  
  # Security
  auth:
    type: "<NONE|BASIC|OAUTH2|CLIENT_CERT|JWT>"
  
  # Routing
  routing:
    default_dest: "<DEFAULT_CONNECTOR>"
    mti_filter:
      - "<MTI>"
    field_conditions:
      - field: "<FIELD_NUM>"
        operator: "eq|ne|in|regex"
        value: "<VALUE>"
        dest: "<CONNECTOR>"
  
  # Failover
  failover:
    enabled: <true|false>
    strategy: "<FAILOVER_STRATEGY>"
    dest: "<FAILOVER_CONNECTOR>"
```
