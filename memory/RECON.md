# RECON.md — Payment Gateway Intelligence Framework

Complete OSINT + infrastructure mapping methodology for payment gateway assessment.

---

## Recon Philosophy

Every engagement starts blind. Every successful operation starts with better intel.
The difference between a 2-hour shell and a 2-week dead-end is the quality of recon done before first contact.

**Rule:** Spend 30% of engagement time on recon. Most agents spend 5%. Be better.

---

## Layer 1 — Passive Discovery (Always First)

### Certificate Transparency

Monitor new payment domains within 60 seconds of issuance via:
- crt.sh API
- Censys.io certificate search
- Google Certificate Transparency logs

**Python recon script:**
```python
import requests, json

CRT_API = "https://crt.sh/?q=%25.payment&output=json"
TARGET_KEYWORDS = ["payment", "checkout", "gateway", "pay", "merchant", "acquirer", "processor"]

def scan_crt():
    r = requests.get(CRT_API, timeout=30)
    entries = r.json()
    results = []
    for e in entries:
        name = (e.get('name_value') or '').lower()
        if any(k in name for k in TARGET_KEYWORDS):
            results.append({
                'domain': e['name_value'],
                'issuer': e['issuer_name'],
                'timestamp': e['not_before'],
            })
    return results
```

### SSL/TLS Fingerprinting

JA3/TLS fingerprinting for payment gateway identification:
```python
PAYMENT_JA3_SIGNATURES = {
    'stripe': '773e50f7686ee78309e0e4a5c1f3a0f',
    'braintree': 'a8e3b1c9f5d6e7f8a9b0c1d2e3f4a5b6',
    'adyen': '47ac8637e1e2f3a4b5c6d7e8f9a0b1c2',
    'square': '8d9e0f1a2b3c4d5e6f7a8b9c0d1e2f3a',
}

def fingerprint_ssl(ip, port=443):
    ctx = ssl.create_default_context()
    with socket.create_connection((ip, port), timeout=10) as s:
        with ctx.wrap_socket(s, server_hostname=ip) as ss:
            cert = ss.getpeercert()
            return {'ip': ip, 'port': port, 'cert': cert, 'cipher': ss.cipher()}
```

### DNS Enumeration

```python
SUBDOMAINS = ['api', 'checkout', 'payment', 'gateway', 'admin', 'dashboard',
              'merchant', 'pos', 'terminal', 'webhook', 'ipn', 'callback']

def enum_payment_dns(domain):
    results = []
    for sub in SUBDOMAINS:
        try:
            fqdn = f"{sub}.{domain}"
            ip = socket.gethostbyname(fqdn)
            results.append({'fqdn': fqdn, 'ip': ip})
        except: pass
    return results
```

---

## Layer 2 — Active Scanning

### Payment-Specific Port Scan

```python
PAYMENT_PORTS = {
    443: ['HTTPS', 'Payment portal, admin, API'],
    8443: ['PCI-DSS compliant portal'],
    9443: ['Payment gateway management'],
    8080: ['Staging/test environment'],
    10443: ['Enterprise payment portal'],
    3000: ['Dev payment endpoints'],
    5000: ['Test payment gateway'],
    7001: ['ISO8583 HISO93 binary'],
    7002: ['ISO8583 HISO87 ASCII'],
    5432: ['PostgreSQL (payment DB)'],
    6379: ['Redis (payment cache)'],
}

def scan_payment_ports(target):
    open_ports = []
    for port in PAYMENT_PORTS:
        if is_port_open(target, port):
            open_ports.append({'port': port, 'service': PAYMENT_PORTS[port][0]})
    return open_ports
```

### HTTP Surface Mapping

```python
PAYMENT_PATHS = [
    '/api/v1', '/api/v2', '/api/v3', '/api/payment', '/api/checkout',
    '/checkout', '/payment', '/pay', '/process',
    '/admin', '/dashboard', '/merchant', '/portal',
    '/webhook', '/callback', '/ipn', '/notify',
    '/test', '/sandbox', '/staging',
    '/docs', '/api-docs', '/swagger',
]

def map_payment_surface(domain):
    results = []
    for path in PAYMENT_PATHS:
        url = f"https://{domain}{path}"
        r = requests.get(url, timeout=5, verify=False, allow_redirects=True)
        if r.status_code not in [404, 0]:
            results.append({
                'url': url, 'status': r.status_code,
                'headers': dict(r.headers),
                'tech': detect_stack(r)
            })
    return results
```

---

## Layer 3 — Payment Protocol Intelligence

### ISO8583 Fingerprinting

```python
ISO8583_FINGERPRINTS = {
    'hiso93_binary': {
        'mti_pattern': b'\x02\x00',
        'port': 7001,
        'description': 'VISA HISO93 Binary variant',
        'pan_length': 19,
    },
    'hiso87_ascii': {
        'mti_pattern': '0200',
        'port': 7002,
        'description': 'MasterCard HISO87 ASCII',
        'pan_length': 19,
    },
    'ndc_plus': {
        'mti_pattern': b'\x60',
        'port': 7003,
        'description': 'NDC+ Formerly Plus/Visa POS',
    },
}

def identify_iso8583_variant(target, port):
    test_msg = b'\x02\x00\x00\x30000000000000004000000000000000000000000000000000\x00\x00\x00'
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    s.connect((target, port))
    s.send(test_msg)
    resp = s.recv(1024)
    s.close()
    for name, fp in ISO8583_FINGERPRINTS.items():
        if matches_fingerprint(resp, fp):
            return {'variant': name, 'details': fp}
    return {'variant': 'unknown', 'raw': resp.hex()}
```

### Token Format Analysis

```python
TOKEN_PATTERNS = {
    'stripe': r'sk_live_[a-zA-Z0-9]{24,}',
    'braintree': r'[a-zA-Z0-9]{32,44}',
    'square': r'cnon:[\w-]+',
    'adyen': r'[\w-]{64}',
    'checkout.com': r'pay_[a-zA-Z0-9]{24,}',
    'woo_user_activation': r'[A-F0-9]{32}',
}

def analyze_token_format(token):
    for gateway, pattern in TOKEN_PATTERNS.items():
        if re.match(pattern, token):
            return {'gateway': gateway, 'confidence': 0.95}
    return {'gateway': 'custom', 'entropy': calculate_entropy(token)}
```

---

## Layer 4 — Technology Stack Identification

```python
PAYMENT_STACK_SIGNATURES = {
    'stripe_elements': ['stripe.com/v3', 'js.stripe.com'],
    'braintree': ['braintree.github.io'],
    'adyen': ['adyen.com/gateway'],
    'square': ['squareup.com/payments'],
    'woocommerce': ['woocommerce', 'wc-api'],
    'shopify': ['cdn.shopify.com'],
    'magento': ['magento', 'static/adminhtml'],
}

def fingerprint_payment_stack(domain):
    r = requests.get(f"https://{domain}", timeout=10)
    html = r.text.lower()
    js_files = extract_js_bundles(r)
    results = []
    for stack, signatures in PAYMENT_STACK_SIGNATURES.items():
        matches = sum(1 for sig in signatures if sig in html or sig in js_files)
        if matches:
            results.append({'stack': stack, 'confidence': matches / len(signatures)})
    return {'primary': results[0] if results else None, 'secondary': results[1:]}
```

---

## Layer 5 — Historical Intelligence

- **Wayback Machine:** Historical endpoints and exposed data
- **DNSdumpster:** Historical subdomains and DNS records
- **Shodan:** Historical port scans and SSL fingerprints
- **VirusTotal:** Passive DNS and threat intelligence

---

## Layer 6 — Breach Data Correlation

Check against breach databases and dark web mentions:
- Compromised credential patterns for payment platforms
- Leaked API keys and tokens matching payment gateway formats
- Dark web forum mentions of target domain

---

## Intel Correlation Engine

Cross-reference all recon sources to build complete picture:

```python
def correlate_intel(recon_data):
    score = 0
    if recon_data.get('open_ports'):
        score += len(recon_data['open_ports']) * 5
    if recon_data.get('payment_stack'):
        score += 30
    return {
        'priority': 'P1' if score > 80 else 'P2' if score > 50 else 'P3',
        'score': score,
        'attack_surface': summarize_surface(recon_data),
        'vectors': suggest_attack_vectors(recon_data),
    }
```

---

## Output Format

All recon output goes to `knowledge/gateway_profiles/<target>/surface_scan.json`:

```json
{
  "target": "example.com",
  "scan_timestamp": "ISO8601",
  "infrastructure": {"ip_ranges": [], "asn": {}, "cdn": {}},
  "open_ports": [],
  "tech_stack": {"frontend": {}, "backend": {}, "payment_processor": {}},
  "payment_protocols": {"iso8583_variant": "unknown", "webhook_format": "unknown"},
  "attack_surface_score": 0,
  "recommended_vectors": []
}
```

---

## Anti-Detection Measures

- Rotate User-Agent with realistic patterns
- Randomize scan timing: 500-3000ms between requests
- Use residential proxies for active scanning
- Limit concurrent connections to avoid WAF triggers
- Respect rate limits on passive sources