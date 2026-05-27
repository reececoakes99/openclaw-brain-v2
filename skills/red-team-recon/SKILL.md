# SKILL: red-team-recon — Automated OSINT Framework

## Metadata

- **Skill Name**: red-team-recon
- **Category**: Reconnaissance / OSINT
- **Author**: openclaw-brain-v2
- **Version**: 1.0.0
- **Last Updated**: 2026-01-15

---

## Description

Automated OSINT reconnaissance framework for mapping payment infrastructure attack surface. Performs multi-source intelligence gathering across Shodan, Censys, Certificate Transparency logs, subdomain enumeration, GitHub code scanning, and dark web monitoring. Outputs structured target data to `knowledge/targets/active_targets.json`.

This skill is the **first phase** of any payment infrastructure assessment. All subsequent skills (payment-scanner, iso8583-operator, hsm-operator) depend on the output produced here.

---

## Trigger Conditions

- **When**: You receive a new target domain, IP range, ASN, or organization name to assess
- **When**: Starting a new payment gateway red-team engagement
- **When**: You need to build a target inventory before port scanning or protocol analysis
- **When**: Updating reconnaissance on a previously assessed target
- **When**: `memory/RECON.md` indicates stale or missing target data

Trigger Phrases:
- "recon on [target]"
- "OSINT scan [domain]"
- "discover payment infrastructure for [org]"
- "find exposed services"

---

## Operational Procedure

### PHASE 1: Target Registration

1. **Receive target input** — domain, IP, ASN, or org name
2. **Initialize target record** in `active_targets.json`:

```bash
# Create structure if not exists
mkdir -p /root/.nanobot/workspace/openclaw-brain-v2/knowledge/targets/

# Append or create target JSON
TARGET="example.com"
cat > /tmp/target_init.json << 'EOF'
{
  "target": "example.com",
  "discovered": [],
  "shodan_results": {},
  "censys_results": {},
  "cert_logs": [],
  "subdomains": [],
  "github_repos": [],
  "asn_info": {},
  "tech_fingerprints": [],
  "scanned_at": null,
  "status": "in_progress"
}
EOF
```

### PHASE 2: Shodan Search

3. **Query Shodan API** for payment infrastructure:

```bash
# Install shodan CLI if needed
pip install shodan 2>/dev/null

# Set API key (from environment or vault)
SHODAN_KEY="${SHODAN_API_KEY}"

# Search for payment-related exposed services
shodan search --color --key "${SHODAN_KEY}" \
  'ssl:"payment" net:1.2.3.0/24' > /tmp/shodan_payment.txt

shodan search --color --key "${SHODAN_KEY}" \
  'http.component:"Stripe" OR http.component:"Braintree" OR http.component:"Square"' \
  > /tmp/shodan_gateways.txt

shodan search --color --key "${SHODAN_KEY}" \
  'ssl.cert.subject.CN:"payment" port:443,8443' \
  > /tmp/shodan_ssl.txt

# Parse and extract IP:port pairs
cat /tmp/shodan_payment.txt | grep -E '^[0-9]' | awk '{print $1":"$2}' > /tmp/shodan_ips.txt

# Enrich with host details
while read HOST; do
  shodan host --key "${SHODAN_KEY}" "${HOST}" >> /tmp/shodan_host_detail.txt
done < /tmp/shodan_ips.txt
```

4. **Parse Shodan JSON output** for structured ingestion:

```bash
# Convert shodan CLI output to JSON
cat /tmp/shodan_host_detail.txt | python3 -c "
import sys, json
data = {}
for line in sys.stdin:
    line = line.strip()
    if ':' in line:
        k, v = line.split(':', 1)
        data[k.strip()] = v.strip()
print(json.dumps(data, indent=2))
" > /tmp/shodan_enriched.json
```

### PHASE 3: Censys TLS Certificate Enumeration

5. **Query Censys API** for TLS certificate intelligence:

```bash
# Install censys CLI
pip install censys 2>/dev/null

# Configure (from environment)
CENSYS_ID="${CENSYS_API_ID}"
CENSYS_SECRET="${CENSYS_API_SECRET}"

# Search for payment-related certificates
censys search --indexYPE certificates \
  'parsed.names: "*.payment*" OR parsed.subject.common_name: "payment*"' \
  --output json > /tmp/censys_certs.json

# Search for specific payment providers
censys search --index-type certificates \
  'parsed.names: "*stripe*" OR parsed.names: "*braintree*" OR parsed.names: "*adyen*"' \
  --output json > /tmp/censys_gateways.json

# Query specific IP for certificate chain
censys view host 1.2.3.4 --output json 2>/dev/null > /tmp/censys_host.json
```

6. **Extract certificate metadata** (issuer, validity, SAN entries):

```bash
cat /tmp/censys_certs.json | jq -r '
.[] | select(.parsed) | {
  subject: .parsed.subject.common_name,
  issuer: .parsed.issuer.common_name,
  sans: .parsed.extensions.subject_alt_name.values[],
  valid_not_before: .parsed.validity.not_before,
  valid_not_after: .parsed.validity.not_after,
  fingerprint: .parsed.fingerprint_sha256
}' > /tmp/censys_cert_analysis.txt
```

### PHASE 4: Certificate Transparency Log Scanning (crt.sh)

7. **Query crt.sh** for subdomains via certificate transparency:

```bash
TARGET_DOMAIN="example.com"

# Query crt.sh certificate transparency log
curl -s "https://crt.sh/?q=%.${TARGET_DOMAIN}&output=json" \
  -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64)" \
  > /tmp/crtsh_raw.json 2>/dev/null || \
curl -s "https://crt.sh/?q=${TARGET_DOMAIN}&output=json" \
  -H "User-Agent: Mozilla/5.0 (X11; Linux x86_64)" \
  > /tmp/crtsh_raw.json

# Parse and deduplicate subdomains
cat /tmp/crtsh_raw.json | jq -r '.[].name_value' 2>/dev/null | \
  sed 's/\*\.//g' | sort -u > /tmp/crtsh_subdomains.txt

# Also query crt.sh with wildcards for deeper discovery
curl -s "https://crt.sh/?q=%.%.${TARGET_DOMAIN}&output=json" \
  -H "User-Agent: Mozilla/5.0" > /tmp/crtsh_wildcard.json 2>/dev/null

# Combine and dedupe
cat /tmp/crtsh_wildcard.json | jq -r '.[].name_value' 2>/dev/null | \
  sed 's/\*\.//g' >> /tmp/crtsh_subdomains.txt

sort -u /tmp/crtsh_subdomains.txt -o /tmp/crtsh_subdomains.txt
```

### PHASE 5: Subdomain Enumeration

8. **DNS enumeration** using dnsdumpster, amass, and ffuf:

```bash
TARGET="example.com"

# dnsdumpster (requires API or scrape)
curl -s -X POST "https://dnsdumpster.com/" \
  -H "User-Agent: Mozilla/5.0" \
  -d "domain=${TARGET}" | grep -oP '(?<=href="/domain/)[^"]+' | \
  head -50 > /tmp/dnsdumpster_subs.txt

# amass passive enumeration
amass enum -passive -d "${TARGET}" -o /tmp/amass_subs.txt

# amass active enumeration (port scan integration)
amass enum -active -d "${TARGET}" -p 443,8443 -o /tmp/amass_active.txt

# ffuf subdomain fuzzing (if wordlist available)
# ffuf -w /usr/share/wordlists/subdomains.txt \
#   -u https://FUZZ.${TARGET}/ -mc 200,301,302,401 -t 50 \
#   -o /tmp/ffuf_subs.json

# Combine all subdomain sources
cat /tmp/amass_subs.txt /tmp/amass_active.txt /tmp/dnsdumpster_subs.txt \
  /tmp/crtsh_subdomains.txt 2>/dev/null | \
  sort -u | grep -v '^$' > /tmp/all_subdomains.txt

wc -l /tmp/all_subdomains.txt
```

### PHASE 6: Technology Fingerprinting

9. **JA3 TLS fingerprinting** for payment platform identification:

```bash
# Using nmap or custom ja3 tool
nmap --script tls-fingerprint -p 443 1.2.3.4 -oA /tmp/nmap_ja3.txt

# Alternative: openssl s_client for JA3 collection
echo | openssl s_client -connect 1.2.3.4:443 \
  -tls1_2 2>/dev/null | openssl x509 -noout -fingerprint -sha256

# HTTP header fingerprinting
curl -sI https://1.2.3.4:8443 | grep -iE \
  'server|x-powered-by|x-request-id|content-type|stripe|adyen|braintree' \
  > /tmp/http_headers.txt

# JS bundle analysis for payment SDK detection
curl -s https://target.com/ | grep -oE \
  '(stripe|adyen|braintree|square|paypal)[-_]?[a-z0-9.]*\.js' | \
  sort -u > /tmp/payment_js_sdk.txt

# Check for exposed configuration files
curl -s https://target.com/config.json 2>/dev/null | head -20
curl -s https://target.com/api/config 2>/dev/null | head -20
curl -s https://target.com/settings.json 2>/dev/null | head -20
```

### PHASE 7: ASN Enumeration

10. **Autonomous System enumeration** for payment host mapping:

```bash
TARGET_ORG="Example Corp"

# Query Shadowserver or Team Cymru for ASN
whois -h whois.cymru.com " -v ${TARGET_ORG}" 2>/dev/null | \
  grep -v '^$' > /tmp/asn_lookup.txt

# Use bgp.he.net for org ASN lookup
curl -s "https://bgp.he.net/search?search[query]=${TARGET_ORG}&commit=Search" \
  | grep -oP 'AS[0-9]+' | sort -u > /tmp/asns.txt

# Query Shodan by ASN
SHODAN_KEY="${SHODAN_API_KEY}"
for AS in $(cat /tmp/asns.txt); do
  shodan search --key "${SHODAN_KEY}" \
    "asn:${AS} ssl.port:443" >> /tmp/shodan_asn_results.txt
done

# Enumerate IP space from ASN
for AS in $(cat /tmp/asns.txt); do
  # Using Hurricane Electric or RIPEstat
  curl -s "https://stat.ripe.net/data/announced-prefixes/data.json?resource=${AS}" | \
    jq -r '.data.prefixes[].prefix' >> /tmp/asn_prefixes.txt
done

sort -u /tmp/asn_prefixes.txt -o /tmp/asn_prefixes.txt
```

### PHASE 8: GitHub Code Scanning

11. **Scan GitHub** for exposed configs, API keys, and hardcoded credentials:

```bash
TARGET_ORG="example-corp"
TARGET_DOMAIN="example.com"

# Use GitHub CLI
gh auth status 2>/dev/null || gh auth login

# Search for payment API keys in public repos
gh search code "payment_api_key site:github.com ${TARGET_ORG}" \
  --limit 50 --json message,repositoryName,path > /tmp/github_api_keys.json

# Search for Stripe/Braintree keys
gh search code "sk_live OR pk_live OR Stripe site:github.com ${TARGET_DOMAIN}" \
  --limit 50 > /tmp/github_stripe_keys.txt

# Search for database configs with payment data
gh search code "DB_HOST password payment site:github.com ${TARGET_ORG}" \
  --limit 50 > /tmp/github_db_configs.txt

# Search for SSH keys or private keys
gh search code "-----BEGIN RSA PRIVATE KEY----- site:github.com ${TARGET_ORG}" \
  --limit 20 > /tmp/github_private_keys.txt

# Search for .env files containing payment credentials
gh search code ".env STRIPE_API_KEY OR BRAINTREE_OR environment" \
  --repo "${TARGET_ORG}/*" --limit 50 > /tmp/github_env_files.txt

# Alternative: raw git search via API
curl -s "https://api.github.com/search/code?q=${TARGET_DOMAIN}+in:file&per_page=100" \
  -H "Authorization: token ${GITHUB_TOKEN}" | jq '.items[].html_url'
```

### PHASE 9: Dark Web Monitoring

12. **Discover payment services on Tor/I2P** (if authorized):

```bash
# Tor hidden service discovery (requires tor service running)

# Use onionscan for hidden service analysis
# onionscan -onion-dir /tmp/onion_results exampleonion123.onion

# Pastebin monitoring for leaked payment credentials
curl -s "https://pastebin.com/search?q=stripe+api" | \
  grep -oP 'https://pastebin.com/[a-zA-Z0-9]+' | \
  head -10 > /tmp/pastebin_payment_leaks.txt

# GitLab snippets and GitHub Gists
curl -s "https://api.github.com/gists/public" | jq -r \
  '.[] | select(.description | test("payment|stripe|api.key"; "i")) | .html_url' | \
  head -20 > /tmp/github_payment_gists.txt

# AlienVault OTX (Open Threat Exchange) pulse check
curl -s "https://otx.alienvault.com/api/v1/indicators/domain/${TARGET_DOMAIN}/general" | \
  jq -r '.pulse_list[] | .name' 2>/dev/null | head -20 > /tmp/otx_pulses.txt
```

### PHASE 10: Output Consolidation

13. **Write to active_targets.json**:

```bash
# Consolidate all findings into structured JSON
python3 << 'PYEOF'
import json
from datetime import datetime

target_data = {
    "target": "example.com",
    "discovered": {
        "subdomains": [],
        "ip_addresses": [],
        "ports": [],
        "payment_endpoints": [],
        "asn_ranges": []
    },
    "shodan_results": {
        "hosts": [],
        "vulnerabilities": [],
        "total_hosts": 0
    },
    "censys_results": {
        "certificates": [],
        "hosts": []
    },
    "cert_logs": {
        "crt_sh": [],
        "censys": []
    },
    "github_leaks": {
        "api_keys": [],
        "configs": [],
        "private_keys": []
    },
    "tech_fingerprints": {
        "ja3_hashes": [],
        "payment_sdks": [],
        "http_headers": [],
        "ssl_versions": []
    },
    "asn_info": {
        "asns": [],
        "prefixes": [],
        "org_name": ""
    },
    "scanned_at": datetime.now().isoformat(),
    "status": "complete",
    "tools_used": [
        "shodan", "censys", "amass", "ffuf", "nmap",
        "curl", "jq", "dnsdumpster", "gh", "onionscan"
    ]
}

# Read and merge subdomain data
try:
    with open('/tmp/all_subdomains.txt', 'r') as f:
        target_data['discovered']['subdomains'] = \
            [s.strip() for s in f if s.strip()]
except: pass

# Read Shodan results
try:
    with open('/tmp/shodan_ips.txt', 'r') as f:
        target_data['discovered']['ip_addresses'] = \
            [ip.strip() for ip in f if ip.strip()]
except: pass

# Read ASNs
try:
    with open('/tmp/asns.txt', 'r') as f:
        target_data['asn_info']['asns'] = \
            [asn.strip() for asn in f if asn.strip()]
except: pass

# Write consolidated output
output_path = '/root/.nanobot/workspace/openclaw-brain-v2/knowledge/targets/active_targets.json'
with open(output_path, 'w') as f:
    json.dump(target_data, f, indent=2)

print(f"Written to {output_path}")
print(f"Subdomains: {len(target_data['discovered']['subdomains'])}")
print(f"IPs: {len(target_data['discovered']['ip_addresses'])}")
print(f"ASNs: {len(target_data['asn_info']['asns'])}")
PYEOF
```

---

## Commands Quick Reference

| Tool | Command | Purpose |
|------|---------|---------|
| shodan | `shodan search --key $KEY 'ssl:"payment"'` | Payment SSL search |
| shodan | `shodan host --key $KEY <IP>` | Host details |
| censys | `censys search --index-type certificates '<query>'` | Cert enumeration |
| crt.sh | `curl -s "https://crt.sh/?q=<domain>&output=json"` | CT log scan |
| amass | `amass enum -passive -d <domain>` | Passive DNS enum |
| nmap | `nmap --script tls-fingerprint -p 443 <IP>` | JA3 fingerprint |
| gh | `gh search code "<query>" --repo <org>/*` | GitHub code search |
| whois | `whois -h whois.cymru.com "<org>"` | ASN lookup |
| jq | Parse and extract JSON | All tools |
| curl | HTTP inspection | All tools |

---

## Tools & Requirements

- **Required**: shodan, censys, amass, nmap, curl, jq, gh CLI
- **Optional**: ffuf, onionscan, tor
- **APIs**: Shodan key, Censys credentials, GitHub token
- **Wordlists**: `/usr/share/wordlists/subdomains.txt`

```bash
# Install all tools
pip install shodan censys 2>/dev/null
go install github.com/owasp-amass/amass@latest 2>/dev/null
apt install nmap jq curl 2>/dev/null
gh auth login 2>/dev/null
```

---

## Cross-References

| Reference | Location | Purpose |
|-----------|----------|---------|
| BOTS.md | `/root/.nanobot/workspace/openclaw-brain-v2/BOTS.md` | RECON bot orchestration |
| memory/RECON.md | memory/RECON.md | Context memory for past recon |
| payment-scanner | `skills/payment-scanner/` | Next skill — port scan + gateway discovery |
| iso8583-operator | `skills/iso8583-operator/` | Protocol attack after recon |
| hsm-operator | `skills/hsm-operator/` | HSM attack after recon |

---

## Error Handling & Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| Shodan rate limit | API quota exceeded | Set `SHODAN_API_KEY`, add delay between queries |
| Censys 403 Forbidden | Missing credentials | Set `CENSYS_API_ID` + `CENSYS_API_SECRET` |
| crt.sh timeout | Rate limiting | Add `-H "User-Agent: Mozilla/5.0"`, retry with backoff |
| amass no output | DNS misconfiguration | Use passive mode (`-passive`), check connectivity |
| GitHub search empty | Token missing | Run `gh auth login` |
| active_targets.json missing | Phase 10 skipped | Re-run consolidation script manually |
| JSON parse error | Malformed output from tool | Pipe through `jq -c '.'` to validate |

```bash
# Test connectivity to each data source
curl -s -o /dev/null -w "%{http_code}" https://shodan.io
curl -s -o /dev/null -w "%{http_code}" https://crt.sh
curl -s -o /dev/null -w "%{http_code}" https://censys.io

# Validate active_targets.json
python3 -c "import json; json.load(open('/root/.nanobot/workspace/openclaw-brain-v2/knowledge/targets/active_targets.json'))" && echo "Valid JSON"
```

---

## Examples

### Basic Target Recon

```bash
# Full recon pipeline on example.com
export SHODAN_API_KEY="your_key_here"
export CENSYS_API_ID="your_id"
export CENSYS_API_SECRET="your_secret"
export GITHUB_TOKEN="ghp_xxx"

# Phase 2-9 in sequence
shodan search --key "$SHODAN_API_KEY" 'ssl:"payment" net:93.184.216.0/24' | \
  grep -E '^[0-9]' | awk '{print $1}' > /tmp/shodan_ips.txt

amass enum -passive -d example.com -o /tmp/amass_subs.txt

curl -s "https://crt.sh/?q=%25.example.com&output=json" | \
  jq -r '.[].name_value' | sort -u > /tmp/crtsh_subs.txt

gh search code "stripe_api example.com" --limit 20 > /tmp/gh_stripe.txt
```

### Payment Infrastructure Only

```bash
# Targeted recon for payment systems only
shodan search --key "$SHODAN_KEY" \
  'http.html:"checkout" OR http.html:"payment" OR http.html:"stripe" port:443' \
  > /tmp/payment_shodan.txt

# Extract Stripe/Braintree/Square endpoints
cat /tmp/payment_shodan.txt | grep -oE \
  'https?://[a-zA-Z0-9._-]+:[0-9]+/[a-zA-Z0-9/_-]*' | \
  sort -u > /tmp/payment_endpoints.txt
```

---

## Notes

- **Legal Notice**: Only scan targets you have explicit authorization to test
- **Rate Limits**: All APIs have quotas — add delays between batch queries
- **Staleness**: Re-scan targets every 30 days or after significant infrastructure changes
- **False Positives**: Always validate discovered hosts via payment-scanner before deeper testing
- **Naming**: Output JSON follows camelCase for brain consistency
