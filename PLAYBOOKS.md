# PLAYBOOKS.md — Pre-Built Engagement Templates

---

## Payment Gateway Full Assessment

Use when: Reece assigns a payment gateway target with full scope.

**Run sequence:**

```
Phase 1 — Discovery (RECON)
  1. Certificate Transparency scan for target domain + subsidiaries
  2. Shodan/Censys port scan (443, 8443, 9443, 8080)
  3. Subdomain enumeration (subfinder + amass passive)
  4. Technology fingerprinting (whatweb, wappalyzer, JA3 TLS)
  5. Web surface mapping (ffuf for /api, /admin, /payment, /checkout, /webhook)
  6. GitHub code scan for exposed credentials, API keys, misconfigs
  7. ASN enumeration + reverse WHOIS for operator identification

Phase 2 — Intel Correlation (INTEL)
  1. Load gateway profile into knowledge base
  2. CVE match against identified technology stack
  3. Score target (ThreatSurface × Exploitability × TargetValue × Exposure)
  4. If P1-P2: trigger HUNTER immediately

Phase 3 — Deep Recon (RECON)
  1. Full port scan of all discovered IPs
  2. Cloud bucket enumeration (S3, GCP, Azure)
  3. Wayback Machine historical scan
  4. Admin panel discovery + initial access testing
  5. Payment flow mapping (transaction lifecycle analysis)
  6. Token format analysis (UUID/v1/MD5 patterns)
  7. Webhook endpoint identification + testing

Phase 4 — Exploitation (HUNTER)
  1. Web injection testing (XSS, SQLi, command injection, SSRF)
  2. Authentication bypass (JWT, OAuth, session fixation)
  3. Business logic testing (price manipulation, race conditions)
  4. ISO8583 message injection (if gateway uses ISO)
  5. API fuzzing (REST, GraphQL)
  6. Webhook exploitation (replay, signature bypass)
  7. HSM interaction testing (if accessible)

Phase 5 — Persistence (HUNTER)
  1. Admin account creation where possible
  2. Backdoor placement (webhook backdoor, API key generation)
  3. Data exfiltration channels established
  4. Evidence capture (timestamps, screenshots, PCAP)

Phase 6 — Report (OPERATIONS)
  1. Compile full engagement package
  2. Write to knowledge/gateway_profiles/<target>/
  3. Full Telegram report to Reece
  4. Update TASK_QUEUE with next steps
```

---

## WordPress/WooCommerce Payment Assessment

Use when: Target is a WooCommerce store with payment processing.

**Run sequence:**

```
Phase 1 — Discovery
  1. /wp-json/wp/v2/users — user enumeration (always try first)
  2. XMLRPC multicall — credential brute-force if enabled
  3. /wp-admin/install.php — identify plugins with DB access
  4. WooCommerce REST API discovery (/wp-json/wc/v3/)
  5. Payment webhook identification (WC_Gateway webhook patterns)

Phase 2 — Tech Stack
  1. Plugin enumeration — identify payment plugins (Stripe, Braintree, PayPal, etc.)
  2. Theme fingerprinting — match against known vulnerable themes
  3. Version identification — core, plugins, PHP version
  4. Custom plugin analysis — direct DB access patterns

Phase 3 — Exploitation
  1. Plugin vulnerabilities — match against WPScan database
  2. WooCommerce-specific attacks:
     - Payment token extraction from database
     - Order manipulation (price, quantity, shipping)
     - Coupon logic bypass
     - Subscription cancellation exploit
  3. Custom plugin exploitation (high-value target)
  4. Admin panel access via plugin RCE

Phase 4 — Payment Data
  1. Database access — if achieved, extract:
     - WooCommerce payment tokens (_woocommerce_persistent_cart)
     - User activation keys (MD5 tokens — correlation target)
     - Session tokens
  2. Token correlation — match against user enumeration
  3. PCI scope identification
```

---

## API-Only Payment Gateway Assessment

Use when: Target has no web UI, API-only (Stripe Connect, Braintree Gateway pattern).

**Run sequence:**

```
Phase 1 — API Discovery
  1. /api/v1, /api/v2, /v1, /v2 endpoint discovery
  2. OpenAPI/Swagger documentation scan
  3. GraphQL introspection (POST /graphql with {__schema{types{name}}})
  4. API key identification from public code/exposure

Phase 2 — API Mapping
  1. Endpoint enumeration (GET / → enumerate supported paths)
  2. Parameter mapping (identify required vs optional)
  3. Authentication mechanism analysis (Bearer, API key, HMAC, JWT)
  4. Rate limit identification
  5. Error response fingerprinting

Phase 3 — Exploitation
  1. Authentication bypass:
     - JWT algorithm confusion (RS256 → HS256)
     - None algorithm injection
     - Token replay
  2. Mass assignment (parameter injection, type coercion)
  3. BOLA/IDOR (object-level authorization testing)
  4. Rate limit bypass (rotating IPs, header manipulation)
  5. SSRF (callback/webhook parameters)

Phase 4 — Payment Flow
  1. Payment token generation testing
  2. Webhook signature validation bypass
  3. Idempotency key exploitation
  4. Currency/amount manipulation
```

---

## ISO8583 Gateway Assessment

Use when: Target is a financial switch using ISO8583 protocol.

**Run sequence:**

```
Phase 1 — Protocol Discovery
  1. Port scan for ISO8583 endpoints (commonly 8000, 8080, 9000, 9876)
  2. TCP banner grabbing — identify HISO variant (HISO93 vs HISO87)
  3. TLS/SSL identification — most enterprise switches use TLS
  4. MTI fingerprinting — send MTI 0800 (echo test), analyze response

Phase 2 — Protocol Mapping
  1. ISO8583 variant identification (ASCII, Binary, BCD encoding)
  2. Field analysis (DE1-DE128 bitmap mapping)
  3. MAC algorithm identification (ISO9797-1, CMAC, HMAC)
  4. Key exchange protocol mapping
  5. Message flow analysis (authorization, capture, refund, reversal)

Phase 3 — Fuzzing (HUNTER)
  1. Field-length manipulation (overflow, underflow)
  2. MTI manipulation (invalid MTIs, cross-type messages)
  3. DE bitmaps — extra bits, missing required bits
  4. PAN manipulation (test card numbers, invalid lengths)
  5. Amount field fuzzing (negative, zero, overflow, currency codes)
  6. MAC bypass testing (replay, forgery)
  7. ARQC/ARPC testing (authentication response replay)

Phase 4 — HSM Interaction
  1. PIN block generation testing (ISO9564 format 0, 1, 2, 3)
  2. MAC generation/verification attack
  3. Key derivation testing (if accessible)
  4. Response code manipulation
```

---

## HSM Security Assessment

Use when: Target has Thales PayShield, Utimaco, or AWS CloudHSM.

**Run sequence:**

```
Phase 1 — Access Mapping
  1. Network access to HSM management port (typically 6666, 8443)
  2. API interface identification (PKCS#11, Thales Java SDK, custom API)
  3. Authentication method identification (key file, certificate, PIN)
  4. Firmware version identification

Phase 2 — Command Testing
  1. PKCS#11 interface fuzzing
  2. Key generation commands (C_GenerateKeyPair)
  3. PIN block operations (C_Encrypt, C_Decrypt)
  4. MAC operations (C_Sign, C_Verify)
  5. Key import/export testing (if allowed)
  6. Lazy key loading vulnerabilities

Phase 3 — Cryptographic Attacks
  1. Key extraction attempts (memory dump if accessible)
  2. PIN block format attacks (ISO9564-1 format 0/1 weak keys)
  3. MAC forgery (ISO9797-1 padding oracle)
  4. Master key derivation attacks
  5. Key diversification weakness analysis

Phase 4 — Integration Exploitation
  1. Downstream system access via compromised HSM keys
  2. PIN verification bypass
  3. Transaction authentication bypass (ARQC/ARPC)
  4. Token vault access via HSM key compromise
```