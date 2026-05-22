# Fraud Bypass Procedures

## Overview

Payment fraud engines use ML models, velocity checks, geolocation, and behavioral analysis to detect fraud. Bypassing these systems means understanding the detection logic and systematically exploiting blind spots.

## Fraud Detection Stack

```
Fraud detection layers:
├── Rule engine (velocity, amount limits, blacklist)
│   ├── Transaction velocity (card/merchant/IP)
│   ├── Amount thresholds (single + daily)
│   ├── Geographic restrictions
│   ├── BIN restrictions (high-risk BINs)
│   └── Velocity burst detection
│
├── ML model (behavioral analysis)
│   ├── Device fingerprinting (browser, OS, canvas)
│   ├── Session behavior (mouse movement, typing patterns)
│   ├── Purchase pattern (normal vs anomalous)
│   └── Historical transaction analysis
│
├── 3D Secure (authentication)
│   ├── Visa Secure (3DS1/2)
│   ├── Mastercard Identity Check
│   └── Challenge flow (OTP, biometrics)
│
└── Human review queue
    ├── High-value transactions flagged
    ├── Pattern match on known fraud
    └── Manual review of anomalies
```

## Attack Vectors

### 1. Velocity Bypass

```
A. Slow fraud (below threshold)
   - Make purchases below velocity threshold
   - Example: limit = 5 transactions/hour → spend 4/hour
   - Over time: same card + same IP = large total spend

B. Distributed fraud (spread across IPs/cards)
   - Use multiple cards (darker card pool)
   - Use multiple IPs (VPN, proxy, botnet)
   - Spread transactions across multiple merchants
   - Total fraud value same, detection spread across many checks

C. Time-based evasion
   - Transactions during low-fraud periods (3AM UTC)
   - Avoid human review queue hours
   - Match normal traffic patterns of merchant
```

### 2. Geolocation Bypass

```
A. IP geolocation spoofing
   - Use VPN with residential IP (not datacenter)
   - Rotate IPs from target country
   - Proxy chains: hide true origin

B. GPS/Location header manipulation
   - Many mobile apps send GPS location
   - Spoof GPS to match billing address
   - Set location to target country

C. Billing/Shipping mismatch bypass
   - Use billing address of cardholder
   - Ship to nearby address (different from billing)
   - Many systems flag mismatch → use adjacent addresses

D. Timezone matching
   - Transaction timezone must match IP geolocation
   - If IP = UK, timezone must = GMT/BST
   - Rotate to match
```

### 3. ML Model Evasion

```
A. Input perturbation
   - Slightly modify input to change ML score
   - Add small amounts to price (avoid round numbers)
   - Vary shipping address slightly each time
   - Change device fingerprint slightly

B. Benign baseline establishment
   - Make small legitimate purchases first
   - Build "normal" behavior profile
   - After 30+ clean transactions: start fraud
   - ML model trained on clean baseline: lower suspicion

C. Transfer learning attack
   - If fraud model is known (leaked, published):
   - Generate adversarial inputs that score below threshold
   - Craft transactions to match model weaknesses

D. Feature collision
   - Two legitimate transactions: each below threshold
   - Combine features across multiple transactions
   - Exploit: detection looks at single transaction, not sequence
```

### 4. 3D Secure Bypass

```
A. 3DS1 weakness (MPI exploit)
   - 3DS1: authentication happens at merchant redirect
   - Merchant MPI sends auth request → issuer responds
   - If merchant doesn't validate response properly:
   - Attacker sends fake AUTH_RESP (authentication bypass)

B. Liability shift exploitation
   - 3DS protects issuer from fraud liability
   - Some merchants disable 3DS to reduce friction
   - Target merchants without 3DS (liability shift = merchant)

C. Soft decline exploitation
   - Soft decline = issuer can't authenticate, try again
   - Send multiple attempts on soft decline
   - If merchant doesn't block after N attempts: exploit

D. 3DS2 friction bypass
   - 3DS2 sends 10+ data elements (device info, browser, etc.)
   - If fraud engine only checks authentication result:
   - Attack: generate fake 3DS2 with valid auth + fake device data
```

### 5. Device Fingerprint Evasion

```
A. Fresh device each transaction
   - Rotate: browser fingerprint, canvas hash, WebGL renderer
   - Use clean browser profiles (undetectable)
   - Tools: FraudFox, MULTIdevice, Custom browser automation

B. Browser spoofing
   - Spoof: User-Agent, Accept-Language, screen resolution
   - Match legitimate user profiles exactly
   - Rotate with realistic variation

C. Canvas fingerprint randomization
   - Many fraud engines hash canvas fingerprint
   - If fingerprint is known: rotate canvas hash each time
   - Use: fingerprintjs, canvas blocker browser extensions

D. IP + fingerprint correlation
   - Fraud engine correlates IP → device fingerprint
   - If IP changes but fingerprint same: flagged
   - Must rotate both IP and fingerprint together
```

### 6. BIN/Rule Bypass

```
A. High-risk BIN identification
   - Some BINs flagged by fraud engine (high fraud rates)
   - Avoid: test cards, prepaid cards, certain countries
   - Use: premium card BINs with low fraud history

B. Amount rule exploitation
   - Some rules: daily amount limit = $X
   - Strategy: split large fraud across multiple days below limit
   - Over 30 days: same card + different IPs + small amounts = large total

C. Blacklist avoidance
   - If card is blacklisted: avoid specific merchants
   - Rotate: merchant, IP, device, time
   - Most blacklists are per-merchant, not cross-merchant
```

## Testing Checklist

```
[ ] Velocity bypass tested (below threshold spending)
[ ] Slow fraud tested (distributed over time)
[ ] IP geolocation spoofing tested (residential VPN)
[ ] GPS/Location spoofing tested
[ ] Billing/shipping address mismatch tested
[ ] Timezone matching tested
[ ] ML model evasion: input perturbation
[ ] ML model evasion: benign baseline establishment
[ ] 3DS bypass: 3DS1 MPI exploit
[ ] 3DS bypass: soft decline exploitation
[ ] Device fingerprint rotation tested
[ ] Canvas fingerprint randomization tested
[ ] IP + fingerprint correlation tested
[ ] High-risk BIN avoidance tested
[ ] Amount rule exploitation (split across days)
[ ] Blacklist avoidance tested
```

## Data Exfiltration

```
Fraud bypass exfil:
1. Use stolen card on merchant A (under threshold)
2. Rotate IP + device + merchant
3. Repeat 100+ times across weeks
4. Accumulate $50,000+ in fraudulent purchases
5. Card flagged by issuer → fraud detected
6. By then: goods purchased, card replaced, fraud complete
```

## Evidence Preservation

- Full transaction logs with IP, device fingerprint, timestamps
- Screenshot of fraud engine decision (if accessible)
- Screenshot of 3DS bypass confirmation
- PCAP of fraud engine decision-making traffic