# RECON Bot — 24/7 Persistent Gateway Discovery

## Mission Statement

Discover every payment gateway on the internet. Map every surface. Flag every weakness. Never stop. Run continuously. Output intelligence to knowledge base every 60 seconds.

## Architecture

```
RECON BOT
├── Layer 1: Passive Discovery (always running, 60s cycle)
├── Layer 2: Active Recon (hourly cycle)
├── Layer 3: Deep Scan (daily cycle)
└── Output: knowledge/bot_queue/recon_pending.json → INTEL BOT
```

## Layer 1: Passive Discovery (60s cycle)

### 1.1 Certificate Transparency

```
Sources:
- crt.sh: https://crt.sh/?q=%25.payment&deduplicate=y
- Censys: https://censys.io/certificates
- Google CRT: https://transparencyreport.google.com/https/certificates

Payment keywords for CRT search:
- payment, gateway, checkout, stripe, braintree,adyen
- shopify, woocommerce, magento, square, paypal
- card, transaction, merchant, pos, terminal
- acquiring, processor, iso8583, pci

Automation:
1. Poll crt.sh API every 60 seconds
2. New certs → extract domain + issuer + SAN
3. Filter: SSL cert contains payment keywords or runs on payment ports
4. Push to active targets immediately

Script: neopay/scripts/cert_scan.py
```

### 1.2 Port Discovery

```
Target ports:
443, 8443, 9443 — HTTPS (payment admin panels, gateways)
8080, 8443, 10443 — Alternative HTTPS
8443 — Common payment gateway port
8888, 8877 — POS terminal protocols (SPDH, XFlow)
5432, 1433 — Database (internal, less common)
27017 — MongoDB (some payment gateways use)

Shodan integration:
- Query: ssl:"Stripe" port:443
- Query: ssl:"Braintree" port:443
- Query: product:"Payment Gateway"
- Query: org:"Square" port:443

Censys integration:
- Query: services.ssh.banner="payment"
- Query: services.http.response.html_keywords="checkout"

Script: neopay/scripts/port_scan.py
```

### 1.3 Source Code Scanning

```
GitHub search patterns:
- "X-Payment-Version" (custom payment headers)
- "stripe.js" (Stripe integration)
- "braintree" (Braintree integration)
- "checkout.js" (generic checkout)
- "payment_gateway" (custom implementations)

GitHub dorks:
- path:.env STRIPE_SECRET_KEY
- path:.env PAYMENT_API_KEY
- filename:webhook.py payment
- filename:payment.py stripe

GitLab:
- Same searches on self-hosted GitLab instances

Leaked secrets:
- Monitor shodan for exposed .env files with payment keys
- Monitor public S3 buckets for payment config files
```

### 1.4 Technology Fingerprinting

```
Fingerprint methods:
1. JA3 TLS fingerprint — match against known payment gateway signatures
2. HTTP headers — X-Payment-Version, Server, X-Frame-Options
3. SSL certificate chain — issuer patterns (Fiserv, FIS, Global Payments)
4. JavaScript bundle analysis — Stripe, Braintree, Square signatures
5. Favicon hash — match against known payment platform hashes

Payment platform signatures:
- Stripe: js.stripe.com, api.stripe.com in page source
- Braintree: assets.braintreegateway.com, js.braintreegateway.com
- Shopify: shopify.com in JS bundles
- Square: squareup.com in JS bundles
- Adyen: checkoutshopper-live.adyen.com in JS bundles
```

### 1.5 Passive DNS

```
Sources:
- Crimeflare (mirror of DNS records)
- DNSDB (passive DNS database)
- PassiveTotal (RiskIQ)
- Shodan DNS

Payment domain patterns:
- *.payment.*, *.gateway.*, *.pay.*
- *checkout*, *cart*, *merchant*
- *acquirer*, *processor*, *switch*

Weekly: Reverse WHOIS on payment-related domains
- Identify all domains owned by same entity
- Map corporate payment infrastructure
```

## Layer 2: Active Recon (hourly)

### 2.1 Web Surface Mapping

```
Directory enumeration on payment endpoints:
/api/v1, /api/v2, /api/payment, /checkout, /payment/process
/admin, /dashboard, /gateway, /merchant/login
/webhook, /callback, /ipn, /notify
/debug, /test, /sandbox (exposed test environments)

Tools:
- gobuster: directory enumeration
- ffuf: fast fuzzing
- custom wordlist: payment-endpoints.txt

Payment-specific paths from neopay/assets/test_data/
```

### 2.2 Service Fingerprinting

```
Identify payment platform:
1. Capture SSL certificate
2. JA3 hash matching (neopay/references/tls_fingerprints.json)
3. HTTP headers fingerprinting
4. JS bundle hash matching
5. Response body patterns

Platform identification:
- Stripe: /v1/payment_intents, Stripe-Version header
- Braintree: /api_version param, braintree.js
- Adyen: /checkout, Adyen-ApiVersion header
- Custom: unique response patterns

Write to: knowledge/gateway_profiles/<domain>/tech_stack.json
```

### 2.3 Version Enumeration

```
Version detection:
1. Check /CHANGELOG, /README for version info
2. HTTP headers: X-Version, Server, X-Payment-Version
3. JS source maps: reveal internal versions
4. SSL certificate issue date: approximate age
5. BuiltWith: technology version history

Cross-reference: neopay/references/cves.json for known CVEs
If platform + version identified:
→ Check NVD for known vulnerabilities
→ Push to INTEL BOT immediately if critical CVE found
```

## Layer 3: Deep Scan (daily)

### 3.1 Full Port Scan

```
Nmap scan on high-priority targets:
nmap -sS -sV -O -p- -T4 -oA <target>

Banner grab on all open ports:
Identify: payment admin panel, database, API, management interface

Protocol detection:
- HTTP/HTTPS on all ports
- SPDH on 8877/8888 (POS terminals)
- XFlow on 7777 (Verifone)
- Custom protocols on unknown ports
```

### 3.2 Cloud Bucket Enumeration

```
AWS S3:
- {domain}.s3.amazonaws.com
- {domain}-assets.s3.amazonaws.com
- {domain}-static.s3.amazonaws.com
- Common patterns: payments, checkout, merchant-data

GCP:
- {domain}.storage.googleapis.com

Azure:
- {domain}.blob.core.windows.net

If open bucket found:
→ List all objects
→ Search for: payment config, API keys, customer data, transaction logs
→ Push as HIGH PRIORITY to INTEL BOT
```

### 3.3 Historical Recon

```
Wayback Machine:
1. Query: https://web.archive.org/web/*/https://{domain}/*
2. Identify: historical payment endpoints, exposed credentials
3. Map: how payment system evolved over time

Shodan history:
- Show all historical scans of domain
- Identify: new endpoints, security improvements, regressions

GitHub historical:
- Search for archived repos containing target domain
- Historical leaks of API keys, configs
```

## Output Format

```
Every discovery → push to knowledge/bot_queue/recon_pending.json

Format:
{
  "discovered_at": "ISO8601",
  "domain": "string",
  "ports": ["array of open ports"],
  "tech_stack": {"platform": "string", "version": "string"},
  "surface": {"endpoints": ["array"], "admin_panel": "bool"},
  "cert_info": {"issuer": "string", "sans": ["array"]},
  "threat_level": "LOW|MEDIUM|HIGH|CRITICAL",
  "notes": "string",
  "scan_layer": "PASSIVE|ACTIVE|DEEP"
}
```

## Aggression Configuration

```
MAXIMUM aggression by default:
- No rate limiting on public sources
- Fast scan cycles (60s passive, hourly active, daily deep)
- Retry failed scans 3x with exponential backoff
- Expand search parameters on each retry

Rate limit exceptions:
- GitHub API: max 60 requests/hour (authenticated)
- Shodan: respect API limits
- crt.sh: no limits

Never stop scanning. Every hour of silence is a missed target.
```

## Cron Schedule

```
# RECON Bot — Layer 1 (60 second cycle)
* * * * * cd ~/.openclaw/workspace && python3 neopay/scripts/cert_scan.py

# RECON Bot — Layer 2 (hourly)
0 * * * * cd ~/.openclaw/workspace && python3 neopay/scripts/active_recon.py

# RECON Bot — Layer 3 (daily at 3AM UTC)
0 3 * * * cd ~/.openclaw/workspace && python3 neopay/scripts/deep_scan.py
```

## Self-Correction

```
If target disappears:
- Re-scan 3x over 24 hours
- If still gone: move to archived/ with note

If scan fails:
- Log error to knowledge/bot_activity_logs/recon_errors.md
- Retry with different method
- Escalate to INTEL BOT if all methods fail

If new payment platform discovered:
- Add fingerprint to neopay/references/tech_signatures.json
- Next scan cycle uses updated fingerprints
```

## Metrics

Track per scan cycle:
- Targets discovered
- New endpoints found
- CVE matches found
- Critical findings (immediate push)
- Scan duration