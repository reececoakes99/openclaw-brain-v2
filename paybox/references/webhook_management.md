# Webhook Management

## Event System

Webhooks deliver real-time event notifications to merchant systems. Paybox emits events for every state transition in the payment lifecycle.

## Event Types

| Event | Trigger | Payload Fields |
|-------|---------|----------------|
| `payment.completed` | Authorization + capture successful | transaction_id, amount, currency, merchant_id, card_type |
| `payment.failed` | Authorization declined or capture error | transaction_id, reason_code, merchant_id |
| `payment.pending` | Async processing (e.g., 3D Secure) | transaction_id, status, next_action |
| `refund.created` | Refund initiated | refund_id, original_transaction_id, amount |
| `refund.completed` | Refund settled | refund_id, settled_amount |
| `refund.failed` | Refund rejected | refund_id, reason |
| `chargeback.created` | Dispute filed by cardholder | chargeback_id, transaction_id, amount, reason, evidence_deadline |
| `chargeback.resolved` | Resolution (won or lost) | chargeback_id, outcome, resolved_amount |
| `fraud.blocked` | Transaction rejected by fraud engine | transaction_id, fraud_score, triggered_rules |
| `token.updated` | Card updated (network token refresh) | token, exp_month, exp_year |
| `payout.processed` | Settlement payout sent | merchant_id, amount, currency, bank_reference |

## Delivery Guarantees

**At-least-once delivery:**
- Events are persisted to a durable queue (Redis Streams or Kafka)
- Delivery retried with exponential backoff on HTTP 4xx/5xx
- Retry schedule: 1min, 5min, 30min, 2hr, 8hr (5 attempts total)
- After 5 failures: moved to dead letter queue, alert triggered

**Retry backoff:**
```
Attempt 1: immediate
Attempt 2: wait 1 minute
Attempt 3: wait 5 minutes
Attempt 4: wait 30 minutes
Attempt 5: wait 2 hours
→ Dead letter: alert + manual retry option
```

**Idempotency:**
- Each event has a unique `event_id` (UUID v4)
- Merchants can deduplicate using `event_id` — store processed IDs
- Idempotency window: 24 hours per event
- Response to duplicate delivery: HTTP 200 (not 409)

## Signature Verification

**HMAC-SHA256 signature:**
```
signature = HMAC-SHA256(timestamp + "." + payload, secret_key)
```

**Headers sent:**
```
X-Paybox-Signature: t=1747200000,v1=abc123...
X-Paybox-Timestamp: 1747200000
X-Paybox-Event-ID: evt_xxxxxxxxxxxx
X-Paybox-Webhook-ID: wh_xxxxxxxxxxxx
```

**Verification code (Python):**
```python
import hmac, hashlib, time

def verify_webhook(payload_body, signature_header, secret):
    parts = dict(kv.split('=') for kv in signature_header.split(','))
    timestamp = parts['t']
    expected_sig = parts['v1']
    # Reject if timestamp > 5 minutes old
    if abs(time.time() - int(timestamp)) > 300:
        raise ValueError("Webhook timestamp too old")
    sig_payload = f"{timestamp}.{payload_body}"
    computed = hmac.new(secret.encode(), sig_payload.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, expected_sig):
        raise ValueError("Invalid signature")
```

## Payload Schema

**payment.completed:**
```json
{
  "id": "evt_123456",
  "type": "payment.completed",
  "created": "2026-05-07T10:30:00Z",
  "data": {
    "object": {
      "id": "txn_abc123",
      "amount": 10000,
      "currency": "EUR",
      "merchant_id": "mer_xyz",
      "card_type": "visa",
      "last4": "4242",
      "auth_code": "123456",
      "rrn": "987654321",
      "settled": false
    }
  }
}
```

**chargeback.created:**
```json
{
  "id": "evt_789012",
  "type": "chargeback.created",
  "created": "2026-05-07T10:30:00Z",
  "data": {
    "object": {
      "id": "cb_456",
      "transaction_id": "txn_abc123",
      "amount": 5000,
      "currency": "EUR",
      "reason": "fraud",
      "reason_code": "4837",
      "evidence_deadline": "2026-05-17T23:59:59Z",
      "cardholder_name": "Jane Doe",
      "cardholder_email": "jane@example.com"
    }
  }
}
```

## Ordering Guarantees

- Events for the same `transaction_id` maintain order
- Different transactions may arrive out of order (acceptable)
- Use `created` timestamp for sequencing if ordering matters

## Endpoint Requirements

- HTTPS only (TLS 1.2+)
- Respond with HTTP 2xx within 30 seconds
- Slow processing? Return 200 immediately, process async
- Invalid signature? Return 401 (don't retry)
- Rate limit awareness: back off if 429 received

## Monitoring

- Delivery rate: should be > 99.5%
- Dead letter queue depth: alert if > 10
- Average delivery latency: < 5s
- See Grafana dashboard `webhook_delivery.json`

## Testing

Use the test webhook endpoint:
```bash
curl -X POST https://api.paybox.test/v1/webhooks/test \
  -H "Authorization: Bearer $API_KEY" \
  -d '{"event": "payment.completed", "endpoint": "https://your-endpoint.com/hook"}'
```