# SKILL: payment-scanner

## Identity
- **Name:** payment-scanner
- **Trigger:** "scan a payment gateway", "find payment endpoints", "identify gateway type"
- **When to use:** When a new target domain is identified and needs full payment infrastructure mapping

## Description

Automated payment gateway discovery and surface analysis. Identifies gateway type, maps payment endpoints, fingerprints tech stack, and builds a complete target profile. Output feeds into knowledge/gateway_profiles/<target>/ for all subsequent stages.

---

## Operational Procedure

### Phase 1: Gateway Type Identification

```
1. Check for known gateway signatures in page source
   curl -s https://target.com/ | grep -i "stripe\|braintree\|adyen\|square\|vantiv\|fiserv\|worldpay"
   
2. Check JavaScript files for payment SDK imports
   curl -s https://target.com/ | grep -oE 'src="[^"]*\.js"' | grep -i "stripe\|braintree\|checkout\|payment"
   
3. Check for iframe patterns (hosted payment pages)
   curl -s https://target.com/ | grep -oiE '<iframe[^>]+src="[^"]*"' | head -10

4. Check meta tags and generator strings
   curl -s https://target.com/ | grep -i "payment\|gateway\|processor\|stripe\| WooCommerce\|Shopify"

5. Analyze SSL certificate for payment provider patterns
   echo | openssl s_client -connect target.com:443 2>/dev/null | openssl x509 -noout -text | grep -i "payment\|stripe\|adyen"
```

**Gateway types to identify:**
| Type | Signatures |
|---|---|
| Stripe | js.stripe.com, Stripe.js, STRIPE_KEY pattern |
| Braintree | braintree-gateway.com, PayPal Braintree SDK |
| Square | squareup.com, square-js, Square Web Payments SDK |
| Adyen | adyen.com, checkout-{env}.adyen.com |
| NMI/ConnectionGear | nmi.com, sw驰ch.com |
| FIS/Worldpay | worldpay.com, fiserv.com, ipg.com |
| Custom | No known signatures, unique implementation |

### Phase 2: Payment Endpoint Enumeration

```
6. Standard payment endpoints
   curl -s -o /dev/null -w "%{http_code}" https://target.com/api/payment
   curl -s -o /dev/null -w "%{http_code}" https://target.com/api/v1/payment
   curl -s -o /dev/null -w "%{http_code}" https://target.com/checkout
   curl -s -o /dev/null -w "%{http_code}" https://target.com/payment/process
   curl -s -o /dev/null -w "%{http_code}" https://target.com/payment/submit

7. Callback and webhook endpoints
   curl -s -o /dev/null -w "%{http_code}" https://target.com/webhook
   curl -s -o /dev/null -w "%{http_code}" https://target.com/callback
   curl -s -o /dev/null -w "%{http_code}" https://target.com/ipn
   curl -s -o /dev/null -w "%{http_code}" https://target.com/notify
   curl -s -o /dev/null -w "%{http_code}" https://target.com/api/webhook
   curl -s -o /dev/null -w "%{http_code}" https://target.com/payment/callback

8. Admin and merchant panel endpoints
   curl -s -o /dev/null -w "%{http_code}" https://target.com/admin
   curl -s -o /dev/null -w "%{http_code}" https://target.com/merchant
   curl -s -o /dev/null -w "%{http_code}" https://target.com/dashboard
   curl -s -o /dev/null -w "%{http_code}" https://target.com/portal
   curl -s -o /dev/null -w "%{http_code}" https://target.com/gateway
   curl -s -o /dev/null -w "%{http_code}" https://target.com/payment/admin
   curl -s -o /dev/null -w "%{http_code}" https://target.com/secure
   curl -s -o /dev/null -w "%{http_code}" https://target.com/myaccount/payment

9. Test and sandbox endpoints
   curl -s -o /dev/null -w "%{http_code}" https://target.com/test
   curl -s -o /dev/null -w "%{http_code}" https://target.com/sandbox
   curl -s -o /dev/null -w "%{http_code}" https://target.com/demo
   curl -s -o /dev/null -w "%{http_code}" https://target.com/staging
   curl -s -o /dev/null -w "%{http_code}" https://target.com/test-payment

10. API documentation and OpenAPI discovery
    curl -s -o /dev/null -w "%{http_code}" https://target.com/swagger
    curl -s -o /dev/null -w "%{http_code}" https://target.com/api/docs
    curl -s -o /dev/null -w "%{http_code}" https://target.com/api/swagger
    curl -s -o /dev/null -w "%{http_code}" https://target.com/api/v2
    curl -s -o /dev/null -w "%{http_code}" https://target.com/openapi.json
```

### Phase 3: Port Scanning

```
11. Masscan for payment-specific ports
    masscan -p443,8443,9443,8080,10443,11443,9000,8443 --rate=1000 -oJ target.json

12. Nmap service detection on discovered hosts
    nmap -sV -p443,8443,9443 --script=http-title,ssl-cert,http-headers target.com

13. SYN scan on entire /24 if in scope
    nmap -sS -p 1-10000 --top-ports 100 --script=http-title,http-headers target.com/24
```

### Phase 4: Tech Stack Fingerprinting

```
14. JA3 TLS fingerprinting
    # Use sslyze or custom script to extract TLS fingerprint
    sslyze --json_out=ja3.json target.com:443

15. HTTP header analysis
    curl -sI https://target.com/ | grep -i "server\|x-powered-by\|x-aspnet\|x-frame\|strict-transport"

16. WAF/IPS detection
    curl -sI https://target.com/ | grep -i "cf-ray\|x-sucuri\|x-iinfo\|x-akamai\|x-cdn\|x-edge\|x-firefox-spreoad"

17. CDN detection
    curl -sI https://target.com/ | grep -i "cloudflare\|fastly\|akamai\|cloudfront\|incapsula\|imperva"

18. Framework detection from headers
    # Django: X-Generator: Django
    # Rails: X-Rack-Cache, X-Request-Id
    # Express: X-Powered-Express
    # Spring: X-Application-Context
    # ASP.NET: X-Generator: ASP.NET, X-AspNet-Version
```

### Phase 5: SSL Certificate Analysis

```
19. Extract certificate chain
    echo | openssl s_client -connect target.com:443 -showcerts 2>/dev/null | openssl x509 -noout -text

20. Check for payment provider证书
    # Look for: Stripe, Inc, Braintree, PayPal, Adyen, Worldpay as issuer

21. Certificate transparency logs
    curl -s "https://crt.sh/?q=target.com&output=json" | jq -r '.[].name_value' | sort -u

22. Wildcard cert discovery
    # Common payment subdomains in certs
    for sub in api staging sandbox test gateway admin portal; do
      echo | openssl s_client -connect $sub.target.com:443 2>/dev/null | openssl x509 -noout -subject 2>/dev/null
    done
```

### Phase 6: Write Results to Knowledge Base

```
23. Create gateway profile directory if not exists
    mkdir -p knowledge/gateway_profiles/<target>/

24. Write surface_scan.json
25. Write tech_stack.json
26. Write payment_flow_mapping.json (if payment flow discovered)
27. Update knowledge/targets/active_targets.json
```

---

## Output Format

Writes to: `knowledge/gateway_profiles/<target>/`

```json
{
  "target": "target.com",
  "scan_date": "2026-05-09T00:00:00Z",
  "gateway_type": "custom|stripe|braintree|square|adyen",
  "confidence": "high|medium|low",
  "endpoints": [...],
  "tech_stack": {...},
  "ssl_info": {...},
  "admin_panels": [...],
  "misconfigs": [...]
}
```

---

## Cross-References

- Uses: BOTS.md (RECON bot), memory/RECON.md
- Feeds into: bot_intel.md (scoring), bot_hunter.md (exploitation)
- Related skills: red-team-recon (for deeper OSINT), web-inject (for found endpoints)

---

## Error Handling

- If curl fails: retry 3 times with exponential backoff, then skip endpoint
- If port scan is slow: prioritize 443/8443, skip low-value ports if time-constrained
- If target blocks requests: switch to passive recon only, flag in findings
- If SSL cert unreadable: note as potential issue, skip certificate analysis

---

## Example Invocation

```
scan a payment gateway for example.com
→ triggers: gateway type detection → endpoint enumeration → tech fingerprint → write to knowledge/gateway_profiles/example.com/
```
---

## Extended Detection Techniques

### JavaScript SDK Fingerprinting
Payment gateways inject JS SDKs that reveal their identity:
```javascript
// Stripe
window.Stripe && Stripe.version  // e.g., "3.x"
document.querySelector('script[src*="js.stripe.com"]')

// Braintree
window.braintree && braintree.VERSION

// PayPal
window.paypal && paypal.version

// Square
window.SqPaymentForm || window.Square

// Adyen
window.AdyenCheckout

// Worldpay
window.Worldpay

// Checkout.com
window.Frames
```

### Network Request Fingerprinting
Intercept payment form submissions to identify gateway:
| Endpoint Pattern | Gateway |
|---|---|
| `api.stripe.com/v1/tokens` | Stripe |
| `api.braintreegateway.com` | Braintree |
| `api.paypal.com/v2/checkout` | PayPal |
| `connect.squareup.com` | Square |
| `checkout.adyen.com` | Adyen |
| `secure.worldpay.com` | Worldpay |
| `api.checkout.com` | Checkout.com |
| `payment.hosted-page.com` | Hosted Page (generic) |
| `secure.authorize.net` | Authorize.Net |
| `api.paymentcloud.com` | PaymentCloud |

### ISO8583 Gateway Detection
For direct TCP/IP payment connections:
```bash
# Probe common ISO8583 ports
nmap -p 5000,7000,8000,8080,8443,9000,9999 <target>

# Send ISO8583 echo/network management request
python3 neopay/scripts/parse_iso8583.py --probe <host>:<port>

# Identify dialect from response header format
# HISO93: 2-byte binary length
# HISO87: 4-byte ASCII length  
# VBI: Variable length indicator
```

### Gateway Profile Database
After identification, load the gateway profile:
```bash
cat knowledge/gateway_profiles/<gateway_name>/profile.json
```

Profiles include:
- Supported card types and BIN ranges
- Tokenization format (Stripe tok_, Braintree opaque, etc.)
- 3DS version (1.0, 2.0, 2.2)
- Fraud detection vendor (Kount, Sift, Signifyd, in-house)
- API versioning and authentication method
- Known CVEs and misconfigurations

### Automated Full Scan Workflow
```bash
# 1. Identify gateway type
python3 pipeline/stages/stage1_recon.py --target <url>

# 2. Load gateway-specific attack profile
cat knowledge/gateway_profiles/<type>/attack_surface.md

# 3. Run payment-specific nuclei templates
nuclei -t nuclei-templates/payment/ -u <url>

# 4. Fuzz payment endpoints
python3 skills/api-fuzzer/fuzz_payment.py --target <url> --gateway <type>
```

## Integration with Bot Fleet
- **RECON bot**: Calls payment-scanner as first step on any web target
- **INTEL bot**: Enriches gateway profile with CVE data from cve-tracker
- **HUNTER bot**: Uses gateway profile to select appropriate exploit chain
- **OPERATIONS bot**: Uses gateway type to select correct exfiltration method
