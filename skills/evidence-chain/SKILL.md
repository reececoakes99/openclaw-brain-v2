# SKILL: evidence-chain

## Identity
- **Name:** evidence-chain
- **Category:** Operations Support
- **Trigger:** At the start of every engagement session, and continuously throughout operations; required for maintaining defensible evidence chain
- **Confidence requirement:** 5/10

## Overview

Every finding must be documented with a complete evidence chain. This is both operational (proof of findings) and legal (defensible chain of custody). The evidence chain skill ensures every artifact is timestamped, integrity-hashed, and stored correctly.

## Operational Procedure

### Step 1: Evidence Directory Setup

```bash
# Create per-target evidence directory
TARGET="payment-gateway-example.com"
DATE=$(date +%Y-%m-%d)
EVIDENCE_DIR="knowledge/gateway_profiles/${TARGET}/evidence/${DATE}"
mkdir -p "${EVIDENCE_DIR}/screenshots"
mkdir -p "${EVIDENCE_DIR}/logs"
mkdir -p "${EVIDENCE_DIR}/pcaps"
mkdir -p "${EVIDENCE_DIR}/poc"

# Create evidence index
cat > "${EVIDENCE_DIR}/index.json" << 'EOF'
{
  "engagement": "TARGET_PLACEHOLDER",
  "date": "DATE_PLACEHOLDER",
  "evidence_items": []
}
EOF

echo "Evidence directory ready: ${EVIDENCE_DIR}"
```

### Step 2: Screenshot Capture

```bash
# Automated screenshot with timestamp
TARGET="payment-gateway.com"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT="${EVIDENCE_DIR}/screenshots/${TARGET}_${TIMESTAMP}.png"

python3 << 'PY'
import asyncio
from playwright.async_api import async_playwright

async def screenshot(url, output):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.screenshot(path=output, full_page=True)
        await browser.close()

asyncio.run(screenshot("https://TARGET_PLACEHOLDER", "OUTPUT_PLACEHOLDER"))
PY

# Hash immediately after capture
sha256sum "$OUTPUT" >> "${EVIDENCE_DIR}/checksums.txt"
echo "Screenshot: $OUTPUT"
```

### Step 3: Log Capture

```bash
# HTTP request/response logging
TARGET="payment-gateway.com"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
LOGFILE="${EVIDENCE_DIR}/logs/${TARGET}_${TIMESTAMP}.har"

# Use mitm_proxy for HAR capture
python3 neopay/scripts/mitm_proxy.py \
  --listen-port 8080 \
  --output "$LOGFILE" &
PROXY_PID=$!

# Route traffic through proxy
curl -x http://localhost:8080 https://target.com/api/payment -o /tmp/response.json

kill $PROXY_PID 2>/dev/null

# Hash log
sha256sum "$LOGFILE" >> "${EVIDENCE_DIR}/checksums.txt"
echo "HAR log: $LOGFILE"
```

### Step 4: PCAP Capture

```bash
# Network packet capture
TARGET_IP="10.0.1.50"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
PCAP="${EVIDENCE_DIR}/pcaps/${TARGET_IP}_${TIMESTAMP}.pcap"

# Capture with tcpdump (requires root)
timeout 60 tcpdump -i eth0 -nn \
  "host ${TARGET_IP} and port 443" \
  -w "$PCAP" 2>/dev/null &

# Capture during test window
sleep 30

# Stop tcpdump
pkill tcpdump

# Hash
sha256sum "$PCAP" >> "${EVIDENCE_DIR}/checksums.txt"
echo "PCAP: $PCAP"
```

### Step 5: PoC Code Preservation

```bash
# Store exploit code with evidence
TARGET="payment-gateway.com"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
POC="${EVIDENCE_DIR}/poc/${TARGET}_sqli_${TIMESTAMP}.py"

cat > "$POC" << 'EOF'
#!/usr/bin/env python3
"""
PoC: SQL Injection in /api/order lookup parameter
Target: payment-gateway.com
Date: YYYY-MM-DD
Severity: Critical
"""
import requests

target = "https://payment-gateway.com/api/order"
payload = "' OR '1'='1"

r = requests.get(f"{target}?id={payload}", timeout=10)
if "SQL syntax" in r.text or "mysql" in r.text.lower():
    print("VULNERABLE: SQL injection confirmed")
    print(f"Response code: {r.status_code}")
    print(f"Response excerpt: {r.text[:200]}")
else:
    print("Check manually")
EOF

chmod +x "$POC"
sha256sum "$POC" >> "${EVIDENCE_DIR}/checksums.txt"
echo "PoC: $POC"
```

### Step 6: Evidence Index Update

```bash
# Update evidence index with new item
python3 << 'PY'
import json, os
from datetime import datetime

evidence_dir = os.environ.get('EVIDENCE_DIR', '/tmp/evidence')
index_file = os.path.join(evidence_dir, 'index.json')

# Load existing index
if os.path.exists(index_file):
    with open(index_file) as f:
        index = json.load(f)
else:
    index = {"engagement": "unknown", "date": datetime.now().isoformat(), "evidence_items": []}

# Add new evidence item
new_item = {
    "timestamp": datetime.now().isoformat(),
    "type": "screenshot",  # screenshot, log, pcap, poc
    "filename": os.environ.get('EVIDENCE_FILE', 'unknown'),
    "sha256": os.environ.get('EVIDENCE_HASH', 'unknown'),
    "tool_used": os.environ.get('TOOL', 'manual'),
    "finding_id": os.environ.get('FINDING_ID', 'unknown')
}
index["evidence_items"].append(new_item)

# Write updated index
with open(index_file, 'w') as f:
    json.dump(index, f, indent=2)

print(f"Evidence index updated: {len(index['evidence_items'])} items")
PY

echo "Evidence index updated"
```

### Step 7: Evidence Sanitization

Before pushing to GitHub, sanitize:

```bash
# Remove PII from Reece
# Remove internal IPs (10.x.x.x, 192.168.x.x)
# Remove internal hostnames
# Remove API keys and tokens

EVIDENCE_DIR="knowledge/gateway_profiles/<target>/evidence"
python3 << 'PY'
import os, re

sanitize_patterns = [
    (r'10\.\d+\.\d+\.\d+', '[INTERNAL_IP]'),
    (r'192\.168\.\d+\.\d+', '[INTERNAL_IP]'),
    (r'reece@\S+', '[OPERATOR_EMAIL]'),
    (r'ghp_[A-Za-z0-9]+', '[GITHUB_TOKEN]'),
    (r'[A-Za-z0-9+/]{40,}', '[REDACTED_KEY]'),  # long base64 keys
]

for root, dirs, files in os.walk(os.environ.get('EVIDENCE_DIR', '/tmp')):
    for fn in files:
        if fn.endswith(('.md', '.json', '.txt', '.log')):
            fp = os.path.join(root, fn)
            content = open(fp).read()
            for pattern, replacement in sanitize_patterns:
                content = re.sub(pattern, replacement, content)
            with open(fp, 'w') as f:
                f.write(content)

print("Sanitization complete")
PY

echo "Evidence sanitized for GitHub push"
```

## Evidence Types Reference

| Type | Format | Tool | Hash |
|---|---|---|---|
| Screenshot | PNG | playwright, selenium | SHA256 |
| HAR log | JSON | mitm_proxy, Burp | SHA256 |
| Packet capture | PCAP | tcpdump, wireshark | SHA256 |
| API response | JSON | curl, requests | SHA256 |
| Exploit code | PY/SH | manual | SHA256 |
| Network trace | TXT | nmap, dig | SHA256 |

## Output

All evidence goes to:
- `knowledge/gateway_profiles/<target>/evidence/YYYY-MM-DD/`
- `knowledge/gateway_profiles/<target>/evidence/YYYY-MM-DD/index.json` — evidence catalog
- `knowledge/gateway_profiles/<target>/evidence/YYYY-MM-DD/checksums.txt` — integrity log

## Cross-References

- `EVIDENCE_CHAIN.md` — evidence chain protocol
- `OPSEC.md` — sanitization rules
- `bot_hunter.md` — integrate into HUNTER bot output

## Troubleshooting

| Problem | Solution |
|---|---|
| Screenshot captures blank page | Wait for JavaScript to render, increase timeout |
| PCAP too large | Use BPF filter to limit capture scope |
| Evidence pushed with PII | Always run sanitization before git add |
| Hash mismatch on re-check | File was modified — document discrepancy |