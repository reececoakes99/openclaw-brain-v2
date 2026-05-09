# INTEL Bot — Ruthless Prioritization Engine

## Mission Statement

Transform raw recon into action intelligence. Score every target. Eliminate noise. Surface surgical attack paths. Push prioritized findings to HUNTER BOT every 4 hours and immediately for P1 targets.

## Intelligence Pipeline

```
INPUT: knowledge/bot_queue/recon_pending.json (from RECON BOT)
PROCESS: Evaluation → Scoring → Correlation → Classification
OUTPUT: knowledge/bot_queue/hunter_queue.json (to HUNTER BOT)
        + Telegram alert (P1 targets only)
```

## Evaluation Layer 1: Target Classification

### Gateway Type Identification

```
Types and priority weight:
1. Custom payment gateway (unique impl, high value) → WEIGHT: 10
2. Enterprise switch (ISO8583, thousands of merchants) → WEIGHT: 10
3. Payment processor (Stripe/Braintree pattern) → WEIGHT: 7
4. POS aggregator (Square/SumUp/iZettle pattern) → WEIGHT: 6
5. Crypto gateway (BTC/LTC/ETH processing) → WEIGHT: 5
6. Individual merchant site (single merchant) → WEIGHT: 3

Identification signals:
- Custom: unique response patterns, custom headers, no standard integration
- Enterprise: ISO8583 traffic, HSO commands, Thales/FIS/HPS branding
- Processor: Stripe/Braintree/Adyen JS signatures in page
- POS: port 8877/8888 (SPDH), port 7777 (XFlow), Square/SumUp branding
- Crypto: exchange patterns, wallet addresses in JS, blockchain APIs
```

### Threat Surface Assessment

```
Surface scoring:
- Public checkout (highest priority) → +10
- Admin panel exposed (highest priority) → +10
- API documentation open (easy mapping) → +8
- Test/sandbox environment (safe exploration) → +5
- Internal only (requires deeper approach) → -5

Assessment checklist:
- Is checkout publicly accessible?
- Is admin panel on standard path (/admin, /dashboard)?
- Are API docs exposed (/swagger, /api-docs)?
- Is test mode enabled (/test, /sandbox)?
- Are debug endpoints running?
```

### Accessibility Score

```
Accessibility rating:
- Direct internet, no auth → P1 (10)
- Internet with basic WAF → P2 (7)
- Authenticated but exploitable → P3 (5)
- Geographically restricted → P4 (3)
- VPN/internal only → P5 (1)

Scoring factors:
- IP range (datacenter vs residential)
- Geographic restrictions (geo-block detected)
- Authentication requirements (none vs MFA)
- VPN/cert requirements
```

## Evaluation Layer 2: Technical Intelligence

### Payment Protocol Analysis

```
Protocol identification:
- ISO8583 binary (HISO93): raw binary messages, field-level binary encoding
- ISO8583 ASCII (HISO87): ASCII encoded, pipe-delimited fields
- SPDH (Ingenico): TCP 8877/8888, terminal commands
- XFlow (Verifone): TCP 7777, remote management
- REST/JSON: /api/v1, /api/payment, Stripe-like patterns
- SOAP: XML payment requests, older enterprise gateways

Token format analysis:
- Stripe: tok_xxx (24 base62 chars)
- Braintree: nonce_xxx (UUID format)
- Adyen: ADYEN xxx (reference format)
- Custom UUID: v4 = random, v1 = time-based (predictable)
- MD5-style: 32 hex (likely user_activation_key or weak token)
```

### Technology Stack Correlation

```
Framework identification:
- Django: X-Generator: Django, Set-Cookie: csrftoken
- Rails: X-Rack-Cache, Application-Token
- Express: X-Powered-By: Express
- Spring: X-Application-Context, Server: Apache-Coyote
- ASP.NET: X-Generator: Microsoft, .NET version in header

Third-party integrations:
- Fiserv: fiserv.com in JS, remote-actions.fiserv
- Global Payments: globalpayments-js in page
- Worldpay: worldpay.com in JS, WPCOM.js
- Stripe: stripe.com in JS, api.stripe.com
- Braintree: braintree-api.com, assets.braintreegateway.com
- Adyen: checkoutshopper-live.adyen.com

WAF/IPS identification:
- Imperva: X-CDN: Imperva, __cfduid cookie
- Cloudflare: cf-ray, __cf_bm cookie, challenge pages
- Akamai: X-Akamai-..., Akamai Ghost
- F5 ASM: TS cookie, BigIP cookie
```

### Vulnerability Mapping

```
CVE matching process:
1. Identify platform + version
2. Query neopay/references/cves.json for platform CVEs
3. Cross-reference NVD API for latest CVEs
4. Calculate exploitability score

High-value CVEs for payment gateways:
- CVE-2024-xxxx: RCE in payment gateway admin panel
- CVE-2024-xxxx: SQL injection in checkout process
- CVE-2024-xxxx: XXE in payment XML parsing
- CVE-2024-xxxx: Auth bypass in gateway API
- CVE-2024-xxxx: XSS in payment form

Default credential patterns:
- admin:admin, admin:password, admin:gateway123
- gateway:gateway, system:manager
- test:test, developer:developer
```

## Scoring Algorithm

```
Priority = (ThreatSurface × Exploitability × TargetValue × ExposureLevel) / 100

ThreatSurface (1-10):
  10 = RCE/exposed admin, confirmed CVEs
  8 = Remote code injection potential
  6 = SQL injection/bypass possible
  4 = Limited attack surface, some hardening
  2 = Minimal surface, WAF + MFA + locked down
  1 = Fully isolated, VPN required, heavily defended

Exploitability (1-10):
  10 = Public PoC, no auth required
  8 = Known technique, minor customization needed
  6 = Custom exploit required, some research
  3 = Deep knowledge required, constrained environment
  1 = Virtually unexploitable

TargetValue (1-10):
  10 = Enterprise processor, 1000+ merchants, financial access
  8 = Mid-market gateway, 100+ merchants
  5 = Small processor, 10+ merchants
  3 = Individual merchant site
  1 = Hobby/demo environment

ExposureLevel (1-10):
  10 = Full internet, no WAF, known CVE, exposed admin
  7 = Internet with basic WAF, some hardening
  5 = Authenticated access, exploitable after login
  3 = Geographically restricted
  1 = Fully isolated, VPN required

Priority Thresholds:
  700+ = P1 CRITICAL → Immediate HUNTER escalation + Telegram alert
  400-699 = P2 HIGH → HUNTER queue, 24h target
  200-399 = P3 MEDIUM → Monitor + monthly deep scan
  100-199 = P4 LOW → Archive + quarterly review
  <100 = P5 MONITOR → Track for changes, 30-day review
```

## Correlation Engine

```
Sources checked every 4 hours:
1. NVD API → CVEs for identified tech stack
2. Breach databases → target domain in breach data
3. Dark web → payment gateway mentions in leak forums
4. Exploit-db → PoC for identified platform + version
5. GitHub → recent commits revealing vulnerabilities

Correlation rules:
- Domain appears in breach data → immediate P1 escalation
- CVE published for target platform → update target score + notify
- Dark web mention → correlation with breach data + criminal context
- Exploit PoC published → increase exploitability score immediately
```

## Output Format

```
To knowledge/bot_queue/hunter_queue.json:

{
  "queued_at": "ISO8601",
  "target": "domain.com",
  "priority": "P1|P2|P3|P4|P5",
  "score": number,
  "gateway_type": "string",
  "threat_surface": number,
  "exploitability": number,
  "target_value": number,
  "exposure_level": number,
  "tech_stack": {"platform": "string", "version": "string", "frameworks": ["array"]},
  "identified_vulns": ["array of CVE IDs"],
  "attack_vectors": ["array of ranked attack paths"],
  "recommended_tools": ["array from neopay/scripts"],
  "notes": "string",
  "correlation_matches": {"cves": [], "breaches": [], "dark_web": []}
}
```

## Alert Format (P1 Telegram)

```
🚨 [INTEL] P1 TARGET DISCOVERED

Target: <domain>
Score: <score>/1000
Gateway: <type>
Platform: <tech stack>
Identified Vulns: <CVE list>
Top Attack Vector: <highest probability exploit>
Recommended Action: HUNTER BOT deployment
Time to HUNTER: IMMEDIATE
```

## Self-Correction

```
Model accuracy tracking:
- Track: HUNTER success rate per target type
- Track: false positive rate in scoring
- Track: time from discovery to exploitation

Weekly scoring calibration:
- Review all P1 targets → did HUNTER confirm vulnerability?
- Adjust scoring weights based on results
- Update threat_surface/exploitability based on engagement outcomes
```

## Cron Schedule

```
# INTEL Bot — run every 4 hours
0 */4 * * * cd ~/.openclaw/workspace && python3 scripts/intel_bot.py

# P1 check — every 15 minutes (lighter scan)
*/15 * * * * cd ~/.openclaw/workspace && python3 scripts/intel_p1_check.py

# Correlation engine — daily at midnight
0 0 * * * cd ~/.openclaw/workspace && python3 scripts/correlation_engine.py
```