# bot_evasion.md — Evasion & Anti-Detection Operations

Operational evasion techniques for the entire bot fleet. Every bot references this file before executing active operations.

---

## 1. TLS Fingerprint Management

Payment gateways fingerprint TLS client connections. Match legitimate browsers.

**JA3 Fingerprint Rotation:**
- Maintain pool of JA3 hashes matching Chrome 120+, Firefox 115+, Safari 17+
- Rotate JA3 per target (never same fingerprint across two targets in one cycle)
- Match cipher suite ordering to claimed browser version
- Use `curl --ciphers` or `openssl s_client -cipher` to control negotiation

**Cipher Suite Ordering:**
- Chrome order: TLS_AES_128_GCM_SHA256, TLS_AES_256_GCM_SHA384, TLS_CHACHA20_POLY1305_SHA256
- Never use uncommon ciphers (ECDH-RSA, CAMELLIA, SEED)
- Enforce TLS 1.2 minimum (TLS 1.0/1.1 flags as suspicious)
- Match ALPN extension (h2, http/1.1) to browser profile

**JA3S Awareness:**
- Log server JA3S responses per target
- Different JA3S for same server = load balancer or CDN (map infrastructure)
- Consistent JA3S = single server (easier to fingerprint you back)

---

## 2. HTTP Fingerprint Evasion

HTTP request patterns are fingerprinted by WAFs and bot detection.

**Header Ordering:**
- Chrome: Host, Connection, sec-ch-ua, sec-ch-ua-mobile, User-Agent, Accept, ...
- Firefox: Host, User-Agent, Accept, Accept-Language, Accept-Encoding, Connection, ...
- Never send headers in alphabetical order (tool default = instant flag)

**Accept-Language Rotation:**
- Match to target geography (AU targets: en-AU,en;q=0.9)
- Consistent per session (don't switch mid-engagement)
- Include realistic quality factors (q=0.9, q=0.8)

**Connection Behavior:**
- Keep-alive connections (match browser behavior)
- Connection reuse patterns (don't open new TCP per request)
- HTTP/2 multiplexing where supported
- Realistic referrer chains (don't arrive from nowhere)

**Cookie Handling:**
- Accept and replay cookies (session persistence)
- JavaScript cookie generation (if page sets via JS, acknowledge it)
- Never strip security cookies (flags as automated)

---

## 3. Timing Obfuscation

Automated tool timing is the #1 detection vector for payment security systems.

**Jitter Algorithms:**
- Base delay: 2-5 seconds between requests (payment systems expect human speed)
- Apply ±15-30% random jitter to base delay
- Formula: `delay = base + (random() * base * 0.3)`
- Never send requests at exact intervals (cron-like = instant flag)

**Burst Avoidance:**
- Maximum 3 requests in any 5-second window to same endpoint
- After burst of 3, enforce 8-15 second cooldown
- Payment form submissions: minimum 12 seconds between (human typing speed)

**Human-like Patterns:**
- Cluster activity in 20-40 minute sessions with 5-10 minute breaks
- Vary session length (never exact same duration)
- Front-load requests (humans browse fast then slow down)
- Occasional 30-60 second pause (simulates reading)

**Payment-Specific Timing:**
- Checkout flow: 45-90 seconds (realistic form-fill time)
- Card number entry: 8-15 seconds (typing 16 digits)
- 3DS verification: 10-30 seconds (redirect + authentication)
- Transaction submission: single request (never retry within 5 seconds)

---

## 4. Network Layer

Never expose direct infrastructure IP to targets.

**Proxy Chain Architecture:**
- Layer 1: Residential proxy (target-country exit IP) — for active testing
- Layer 2: Datacenter proxy (speed) — for passive scanning only
- Layer 3: VPN (Tailscale/WireGuard) — for C2 and infrastructure management
- Never use KiloClaw VPS IP directly for any target interaction

**Proxy Rotation:**
- Rotate residential proxy every 10-15 minutes during active engagement
- Sticky sessions for checkout flows (same IP for full transaction lifecycle)
- Different IP per target (never share proxy between concurrent targets)
- If rate-limited: immediate proxy rotation + 5 minute cooldown

**SOCKS5 Protocol:**
- Use SOCKS5 for raw TCP (ISO8583 connections, terminal protocols)
- HTTP proxies for web-layer testing only
- Verify proxy DNS resolution (DNS leaks expose real location)

**DNS-over-HTTPS:**
- Route all DNS through DoH (Cloudflare 1.1.1.1/dns-query or Google)
- Prevents ISP-level DNS monitoring
- Consistent with browser privacy profiles

---

## 5. Application Layer

User-Agent and browser identity management.

**UA Rotation (Market Share Weighted):**
- Chrome 120+ (65% weight) — most common, least suspicious
- Firefox 115+ (15% weight) — second most common
- Safari 17+ (12% weight) — use with macOS Accept-Encoding patterns
- Edge (8% weight) — same engine as Chrome, different UA string
- Never: Python-requests, curl, wget, Java, or custom UAs

**Referrer Chain Building:**
- Start from realistic referrer (Google search → target site → checkout)
- Build organic navigation path before hitting payment endpoints
- Never access /api/payment directly without prior page navigation
- Maintain referrer consistency within session

**Browser Feature Emulation:**
- Accept: text/html,application/xhtml+xml (not */*)
- Accept-Encoding: gzip, deflate, br (include brotli)
- Sec-Ch-Ua headers (Chromium-based only)
- Sec-Fetch-Mode: navigate/cors/no-cors (context-appropriate)

---

## 6. Payment-Specific Evasion

Payment fraud detection systems (FDS) use unique detection heuristics.

**Transaction Velocity Masking:**
- Maximum 2 transactions per card per hour (normal customer pattern)
- Vary amounts by ±5-15% between test transactions
- Never sequential round amounts ($1.00, $2.00, $3.00 = instant flag)
- Use amounts matching target merchant's typical range

**BIN Distribution Patterns:**
- Never test 10+ cards from same BIN range in sequence
- Rotate across Visa/MC/Amex (don't cluster on single scheme)
- Space BIN-range testing across 24+ hours
- Mix issuing banks (not all cards from same issuer)

**Merchant Descriptor Awareness:**
- Match transaction metadata to merchant type
- Correct MCC (Merchant Category Code) for claimed business
- Terminal ID consistency within session
- Realistic acquirer institution IDs

**3DS Timing Mimicry:**
- 3DS challenge flow: 15-45 seconds (human reading and responding)
- 3DS frictionless: 2-5 seconds (server-to-server, no human delay)
- Never skip 3DS if triggered (indicates automation)
- Complete full 3DS lifecycle before next transaction attempt

---

## 7. Detection Avoidance

Identify and circumvent specific security systems.

**WAF Fingerprinting (Identify Before Testing):**
- Cloudflare: `cf-ray` header, challenge page JavaScript
- Akamai: `akamai-grn` header, pragma headers
- AWS WAF: `x-amzn-requestid`, challenge response patterns
- Imperva/Incapsula: `incap_ses_` cookies, SWJIYLWA challenge
- F5 BIG-IP: `BIGipServer` cookies, ASM challenge pages

**Rate Limit Probing:**
- Start with single request, wait full response
- Gradually increase frequency (1 req/10s → 1 req/5s → 1 req/2s)
- When rate-limited (HTTP 429 or custom block page): record threshold
- Operate at 60% of discovered threshold (safety margin)
- Different endpoints may have different limits (test each)

**CAPTCHA Routing Decisions:**
- If CAPTCHA triggered: STOP current technique
- Log CAPTCHA trigger condition (what request pattern caused it)
- Options: a) Route through CAPTCHA solver service, b) Rotate IP + reset session, c) Switch to different entry point
- Never brute-force past CAPTCHA (escalates detection)

**Honeypot Detection:**
- Hidden form fields (CSS display:none) — never fill these
- Invisible links — never follow href with opacity:0 or off-screen positioning
- Fake admin panels with unusual ports — verify legitimacy before interaction
- Response too easy (immediate admin access without auth) — likely trap
- If honeypot suspected: STOP all activity on that target, report to Operator

---

## 8. Anti-Forensics

Minimize traceable footprint during and after operations.

**Session Isolation:**
- Fresh browser profile per target (no cross-target cookie leakage)
- Separate proxy chain per engagement
- Unique TLS session tickets per target
- Clear local state between targets

**Log Pollution Awareness:**
- Know what the target logs: IPs, UAs, request paths, timing, referrers
- Assume ALL of these are logged (operate accordingly)
- Don't generate unusual log patterns (mass 404s, sequential path enumeration)
- Blend with legitimate traffic patterns

**Timestamp Consistency:**
- All requests within same timezone (match proxy exit location)
- Date/time headers consistent with claimed locale
- If-Modified-Since headers realistic (not from the future)
- Cookie timestamps consistent with session creation time

**Evidence Awareness:**
- Our evidence (screenshots, PCAPs, logs) stored encrypted at rest
- Evidence chain maintained per EVIDENCE_CHAIN.md protocol
- No evidence stored on target infrastructure
- Clean exit: remove any uploaded test files, close all connections

---

## Evasion Decision Matrix

When to apply which level of evasion:

| Operation Type | Evasion Level | Techniques Applied |
|---|---|---|
| Passive recon (cert CT, Shodan queries) | MINIMAL | Standard UA, no proxy required |
| Active scanning (port scan, directory enum) | MODERATE | Proxy rotation, timing jitter, UA rotation |
| Vulnerability testing (fuzzing, injection) | HIGH | Full proxy chain, all timing rules, fingerprint matching |
| Exploitation (payload delivery, data extraction) | MAXIMUM | All 8 categories active, session isolation, anti-forensics |
| Checkout flow testing | MAXIMUM + PAYMENT | All above + payment-specific velocity/BIN/3DS rules |

---

## Evasion Failure Response

If detected (WAF block, rate limit, CAPTCHA, IP ban):

1. **STOP** — Halt all activity on that target immediately
2. **LOG** — Document what triggered detection (request that got blocked)
3. **ROTATE** — Change proxy, clear session, new browser profile
4. **WAIT** — Minimum 15 minutes before re-engaging same target
5. **ADAPT** — Modify technique based on what was detected
6. **RESUME** — Re-engage at lower intensity with adapted approach
7. **ESCALATE** — If blocked 3+ times on same target, report to Operator for strategy review
