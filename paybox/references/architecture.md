# PayBox Architecture — Full System Design

## Design Principles

1. **No single point of failure** — every critical path has a failover
2. **Idempotent by default** — every operation is safe to retry
3. **Double-entry ledger** — every movement of money is balanced
4. **Event-sourced** — state changes are journaled, not overwritten
5. **PCI DSS scope minimization** — card data never enters the main DB
6. **Observability first** — every operation emits structured logs + traces

## Component Inventory

### 1. API Gateway / BFF

Sits at the edge. Responsibilities:
- TLS termination
- API key validation (rotated every 90 days)
- IP allowlist enforcement per merchant
- Rate limiting (per merchant, per endpoint)
- Request signing verification (HMAC-SHA256)
- Schema validation (JSON Schema)
- Audit log of every request (async to Kafka)
- Route to downstream services

```yaml
# Kong / nginx config snippet
upstream paybox_api {
    server bff:8080;
}

location /v1/payments {
    limit_req zone=merchant_limit burst=20 nodelay;
    auth_jwt_optional key=Authorization;
    access_log /var/log/paybox/payments.log json;
    proxy_pass http://paybox_api;
}
```

### 2. Payments Service (BFF)

Stateless aggregation layer. Orchestrates calls to:
- Orchestration Engine
- Ledger Service
- Token Vault
- Fraud Engine
- Bank Connectors

```python
# payments/bff.py
class PaymentBFF:
    async def create_payment(self, req: CreatePaymentRequest, merchant: Merchant) -> PaymentResponse:
        # 1. Validate schema
        self.validate(req)

        # 2. Check rate limits
        await self.rate_limiter.check(merchant.id, req.amount, req.currency)

        # 3. Fraud score
        score = await self.fraud_engine.score(req, merchant)
        if score > merchant.fraud_threshold:
            return PaymentResponse(status="declined", reason="fraud_score_exceeded")

        # 4. Tokenize card (if card payment)
        token = await self.token_vault.tokenize(req.card_pan, merchant.id)

        # 5. Create orchestration task
        task = OrchestrationTask(
            merchant_id=merchant.id,
            payment_type=req.type,
            amount=req.amount,
            currency=req.currency,
            card_token=token,
            idempotency_key=req.idempotency_key,
        )
        await self.queue.enqueue(task)

        # 6. Return pending payment
        return PaymentResponse(
            payment_id=task.payment_id,
            status="pending",
            created_at=datetime.utcnow(),
        )
```

### 3. Orchestration Engine

State machine that drives the payment lifecycle:

```
PENDING → PROCESSING → AUTHORISED → CAPTURED → SETTLED
                ↓
           DECLINED / FAILED / DISPUTED
```

State transitions are atomic, journaled to Kafka, and replayable.

```python
from enum import Enum

class PaymentState(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    AUTHORISED = "authorised"
    DECLINED = "declined"
    CAPTURED = "captured"
    SETTLED = "settled"
    FAILED = "failed"
    DISPUTED = "disputed"
    REFUNDED = "refunded"

class OrchestrationEngine:
    async def process(self, task: OrchestrationTask):
        try:
            await self.transition(task.payment_id, PaymentState.PENDING, PaymentState.PROCESSING)

            # Route to appropriate connector
            connector = self.routing.get(task.payment_type, task.merchant)
            result = await connector.execute(task)

            if result.is_success():
                await self.transition(task.payment_id, PaymentState.PROCESSING, PaymentState.AUTHORISED)
                await self.ledger.post_auth(task.payment_id, result)
            else:
                await self.transition(task.payment_id, PaymentState.PROCESSING, PaymentState.DECLINED)

        except Exception as e:
            await self.transition(task.payment_id, PaymentState.PROCESSING, PaymentState.FAILED)
            await self.emit_retry(task, delay=30)  # Exponential backoff
```

### 4. Bank Connectors

Abstraction layer over bank network protocols. Each connector:
- Translates internal transaction model → bank-specific protocol
- Handles connection pooling, retries, timeouts
- Parses response, normalizes to internal format
- Logs raw request/response for dispute resolution

```python
from abc import ABC, abstractmethod

class BankConnector(ABC):
    @property
    @abstractmethod
    def bank_code(self) -> str: ...

    @property
    @abstractmethod
    def protocol(self) -> str: ...  # "iso8583" | "iso20022" | "rest" | "swift"

    @abstractmethod
    async def authorize(self, txn: Transaction) -> AuthorisationResult: ...

    @abstractmethod
    async def capture(self, txn: Transaction) -> CaptureResult: ...

    @abstractmethod
    async def refund(self, txn: Transaction) -> RefundResult: ...

    @abstractmethod
    async def reconcile(self, cutoff: datetime) -> ReconciliationReport: ...
```

Implementations:
- `VisaMastercardConnector` → ISO8583 via processor/acquirer
- `SepaConnector` → ISO 20022 pain.001/pain.002 via SEPA scheme
- `SwiftConnector` → MT103 for cross-border
- `OpenBankingConnector` → PSD2 REST API per ASPSP
- `NeopaySwitchConnector` → ISO8583 switch (replicating neopay.online)

### 5. Ledger Service

Double-entry bookkeeping. Every financial event creates balanced entries.

```python
# debit (merchant liability) + credit (merchant receivable) = 0
# debit (fee) + credit (merchant) = 0

async def post_auth(payment_id: str, auth_result: AuthorisationResult):
    async with self.db.transaction():
        await self.post(
            account_id=auth_result.merchant_account,
            entry_type=EntryType.CREDIT,
            amount=auth_result.amount,
            currency=auth_result.currency,
            reference=f"auth:{payment_id}",
        )
        await self.post(
            account_id="SUSPENSE",
            entry_type=EntryType.DEBIT,
            amount=auth_result.amount,
            currency=auth_result.currency,
            reference=f"auth:{payment_id}",
        )
        await self.post_event(
            event_type="AUTHORISATION",
            payment_id=payment_id,
            amount=auth_result.amount,
            entries=[...],
        )
```

### 6. Token Vault

Never stores raw PANs. Always tokenizes first.

```python
class TokenVault:
    def tokenize(self, pan: str, merchant_id: str) -> str:
        # 1. Luhn check
        assert luhn_valid(pan), "Invalid PAN"

        # 2. Format-preserving encrypt (FPG)
        encrypted = self.hsm.encrypt(pan)  # HSM-backed, never in memory plaintext

        # 3. Store mapping in vault DB (PAN hash → token, indexed by merchant)
        token = self.generate_token()  # high-entropy random
        self.db.execute("""
            INSERT INTO vault_tokens (token, pan_hash, merchant_id, created_at)
            VALUES (%s, %s, %s, NOW())
            ON CONFLICT DO NOTHING
        """, [token, sha256(pan), merchant_id])

        return token  # This is what goes into the main DB

    def detokenize(self, token: str) -> str:
        # Only permitted from HSM-attached process, never via API
        pan_hash = self.db.fetch("SELECT pan_hash FROM vault_tokens WHERE token = %s", [token])
        return self.hsm.decrypt(pan_hash)
```

### 7. Fraud Engine

Multi-layered scoring:

```python
class FraudEngine:
    def score(self, req: PaymentRequest, merchant: Merchant) -> float:
        score = 0.0

        # Velocity checks
        if self.velocity_check.count(req.card_token, window="1h") > merchant.velocity_hourly:
            score += 40
        if self.velocity_check.count(req.customer_ip, window="24h") > 10:
            score += 20

        # BIN risk scoring
        bin_risk = self.bin_risk_scores.get(req.bin_prefix)
        score += bin_risk * 0.5

        # Geolocation anomaly
        if not self.geo_utils.is_plausible(req.ip_country, req.card_country):
            score += 25

        # Card risk
        if self.card_risk_list.is_blocked(req.pan_hash):
            score = 100.0

        # Velocity of failed auths
        if self.velocity_check.count(req.card_token, window="5m", status="declined") > 3:
            score += 30

        return score
```

### 8. Webhook Manager

Guarantees delivery with retry logic:

```python
# Webhook delivery with exponential backoff
webhook_delivery:
  max_retries: 5
  backoff: "exponential"
  base_delay_seconds: 30
  retry_schedule: [30, 120, 600, 3600, 14400]

# Idempotency via event_id + merchant_id
# Merchants must handle duplicate events gracefully
```

### 9. Settlement Service

Daily batch process that:
1. Groups settled transactions by merchant
2. Calculates fees, chargebacks, reserves
3. Generates settlement files (pain.002 / CSV)
4. Triggers payout initiation
5. Updates ledger accounts

```sql
-- Settlement calculation per merchant
SELECT
    merchant_id,
    SUM(amount) as gross_volume,
    SUM(fee) as total_fees,
    SUM(amount) - SUM(fee) as net_settlement,
    COUNT(*) as txn_count
FROM transactions
WHERE status = 'settled'
  AND settled_at BETWEEN :start AND :end
GROUP BY merchant_id
```

### 10. ISO8583 Switch

Internal switch replicating ISO8583 switching logic (inspired by neopay.online):

```python
# Components of the switch:
# 1. Message Gateway — accepts TCP connections, handles framing
# 2. MTI Router — routes by MTI to appropriate handler
# 3. Field Processor — parses bitmaps, validates DE fields per MTI
# 4. Connector Pool — maintains connections to acquirer/processors
# 5. Audit Logger — stores raw messages for dispute resolution

class ISO8583Switch:
    async def handle_message(self, raw_bytes: bytes) -> bytes:
        msg = ISO8583Parser.parse(raw_bytes)
        self.audit_log.store(msg)

        # Validate MAC if present
        if msg.mac_present:
            if not self.mac_verifier.verify(msg):
                return self.build_nack("MAC verification failed")

        handler = self.mti_router.get(msg.mti)
        result = await handler.process(msg)

        return self.build_response(result, msg.mti)
```

## API Design

### Base URL
`https://api.paybox.io/v1`

### Authentication
- `Authorization: Bearer <api_key>` — merchant API key
- `X-Signature: <hmac_sha256>` — request signature
- `X-Idempotency-Key: <uuid>` — required for POSTs

### Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/payments` | Create payment |
| GET | `/payments/{id}` | Get payment status |
| POST | `/payments/{id}/capture` | Capture authorised payment |
| POST | `/payments/{id}/refund` | Full or partial refund |
| GET | `/payments` | List payments (filterable) |
| POST | `/payment-links` | Create payment link |
| GET | `/payment-links/{id}` | Get payment link |
| POST | `/customers` | Create customer |
| GET | `/customers/{id}` | Get customer |
| POST | `/webhooks/endpoints` | Register webhook |
| GET | `/settlements` | List settlements |
| GET | `/balance` | Merchant balance |
| POST | `/payouts` | Initiate payout |

### Request/Response Format

```json
// POST /payments
{
  "type": "card",
  "amount": 4999,
  "currency": "EUR",
  "customer": {
    "email": "john@example.com",
    "country": "FR"
  },
  "card": {
    "token": "tok_xxxxxxxxxxxx"
  },
  "reference": "ORDER-12345",
  "callback_url": "https://merchant.com/callback",
  "idempotency_key": "unique-key-123"
}

// Response
{
  "payment_id": "pay_abc123",
  "status": "pending",
  "requires_3ds": true,
  "3ds_url": "https://acs.paybox.io/challenge",
  "created_at": "2026-05-05T22:56:00Z"
}
```

## Database Schema Overview

```
merchants
  ├── id, name, legal_name, api_keys (hashed), tiers, limits
  ├── PCI DSS scope: SAQ-A, SAQ-A-EP, PCI DSS compliance
  └── risk_score, fraud_threshold

accounts (ledger)
  ├── id, merchant_id, type (operating/reserve/fee)
  └── currency, balance

transactions
  ├── id, merchant_id, type, state machine
  ├── amount, currency, fee, settled_amount
  ├── card_token (no PAN), customer_id, reference
  ├── acquirer_ref, network_ref
  └── raw_request_log (encrypted), raw_response_log (encrypted)

vault_tokens
  ├── token, pan_hash, merchant_id (encrypted at rest)
  └── accessed_at (for audit)

webhook_events
  ├── id, merchant_id, event_type, payload
  ├── delivery_status, retry_count, last_attempt

settlements
  ├── id, merchant_id, period, gross, fees, net
  └── status (pending/processing/settled), payout_id
```

See `references/database.md` for full schema.

## Security Controls

| Control | Implementation |
|---------|---------------|
| Encryption at rest | AES-256-GCM for all PII, card data in vault |
| Encryption in transit | TLS 1.3, mTLS for bank connections |
| Key management | AWS CloudHSM / Thales Luna — keys never in code |
| PCI DSS scope | Minimal — token vault in isolated network segment |
| Rate limiting | Redis-based, per merchant + per endpoint |
| Audit trail | Every state transition logged to immutable Kafka topic |
| Secret rotation | API keys rotated every 90 days |
| Network segmentation | DMZ for API, internal for processing, HSM network |

## Failover & Resilience

- Bank connectors: primary + secondary acquirer routes
- Kafka: 3x replication factor, 7-day retention
- PostgreSQL: primary + read replica, PITR via WAL
- Redis: sentinel mode, 3 nodes
- ISO8583 switch: active-standby, heartbeat every 10s

## Deployment

```yaml
# docker-compose.yml (reference)
services:
  api_bff:
    image: paybox/api:latest
    deploy:
      replicas: 3
    depends_on:
      - orchestration
      - ledger
      - fraud

  orchestration:
    image: paybox/orchestration:latest
    depends_on:
      - iso8583_switch
      - sepa_connector

  iso8583_switch:
    image: paybox/switch:latest
    ports:
      - "5015:5015"
    volumes:
      - /dev/shm:/dev/shm  # For low-latency memory ops

  ledger:
    image: paybox/ledger:latest
    volumes:
      - pgdata:/var/lib/postgresql/data

  token_vault:
    image: paybox/vault:latest
    devices:
      - /dev/hsm  # HSM passthrough
    privileged: true

  fraud:
    image: paybox/fraud:latest
    environment:
      ML_MODEL_PATH: /models/scoring-v2.pkl

  kafka:
    image: confluent/cp-kafka:latest
    environment:
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_NUM_PARTITIONS: 12
      KAFKA_DEFAULT_REPLICATION_FACTOR: 3
```