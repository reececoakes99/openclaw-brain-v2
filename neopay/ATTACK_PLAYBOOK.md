# Payment Gateway Attack Playbook

## Phase 1 — Reconnaissance

### Gateway Discovery
```
1. Certificate Transparency — find payment domains
2. Shodan/Censys — port scan for payment ports
   Ports: 443, 8443, 9443, 7001, 7002, 9000, 9001, 8000
3. BuiltWith — identify payment platform (Stripe, Braintree, custom)
4. GitHub — search for exposed API keys, .env files, payment configs
```

### Tech Stack Fingerprinting
```
1. TLS fingerprinting (JA3) — match against payment gateway signatures
2. HTTP headers — X-Payment-Version, Server, X-Frame-Options
3. JavaScript analysis — Stripe.js, Braintree.js, Square.js
4. SSL certificate chain — issuer patterns (Fiserv, FIS, Global Payments)
5. API response patterns — transaction ID formats, token structures
```

### Payment Flow Mapping
```
1. Identify checkout flow — hosted vs integrated
2. Map tokenization flow — where tokens are generated
3. Identify payment processor — direct to scheme or through gateway
4. Map webhook callbacks — authentication mechanism
5. Identify HSM integration — if applicable
```

## Phase 2 — Protocol Testing

### ISO8583 Testing (for gateways with ISO8583)
```
1. MTI field testing — send malformed MTIs, observe response
2. Field length fuzzing — overflow/underflow each field
3. PAN manipulation — test card number validation
4. Amount field injection — negative values, overflow
5. MAC testing — replay MAC, forge MAC, key extraction attempt
6. ARQC/ARPC — replay authentication responses
7. PIN block testing — ISO9564 format manipulation
```

### API Testing
```
1. REST endpoint enumeration — /api/v1, /v2, /payment, /checkout
2. Parameter manipulation — type coercion, injection
3. Authentication bypass — JWT algorithm confusion, none algorithm
4. Rate limit abuse — credential stuffing, enumeration
5. Webhook exploitation — replay, signature bypass
```

## Phase 3 — Exploitation

### Checkout Injection
```
1. XSS in payment fields — name, cardholder, address
2. SQL injection — transaction IDs, order IDs
3. Command injection — callback parameters, webhooks
4. SSRF — internal service discovery via webhooks
5. GraphQL — introspection + mutation injection
```

### Token Manipulation
```
1. Token format analysis — UUID, v1/v4, MD5 patterns
2. Token reuse — test if tokens work across merchants
3. Token-to-card mapping — if vault accessible
4. Token escalation — upgrade token privileges
```

### Business Logic Attacks
```
1. Price manipulation — negative values, integer overflow
2. Currency swap — change currency without recalculation
3. Race conditions — concurrent transaction testing
4. Workflow bypass — state manipulation
```

## Phase 4 — Persistence + Exfiltration

### Persistence
```
1. Admin account creation — if admin panel found
2. API key generation — create persistent access
3. Webhook backdoor — command callback channel
4. Cron-based callback — scheduled beacon
```

### Data Extraction
```
1. Transaction data — card patterns, PII, amounts
2. Token vault — if accessible, full token mapping
3. Configuration — merchant credentials, API keys
4. Evidence — PCAP files, screenshots, logs
```

## Phase 5 — Evidence + Exit

### Evidence Preservation
```
1. Timestamped screenshots — every finding documented
2. PCAP files — full transaction captures
3. Exploit PoC code — reproducible evidence
4. Timing metadata — session IDs, timestamps
```

### Cleanup
```
1. Remove uploaded files — web shells, test scripts
2. Clear logs — if accessible, sanitize evidence
3. Close sessions — terminate all open connections
4. Preserve evidence — upload to knowledge base before exit
```
