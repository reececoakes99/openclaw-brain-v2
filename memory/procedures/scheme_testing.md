# Payment Scheme Testing Procedures

## Overview

Payment schemes (Visa, Mastercard, Amex, UnionPay) have specific test cards, endpoints, and behaviors. Testing against live schemes requires understanding test infrastructure and proper authorization scopes.

## Scheme Architecture

```
Payment scheme layers:
├── Scheme network (VisaNet, MCNet, Amex network)
│   ├── ISO8583 message switching
│   ├── Authorization routing
│   ├── Clearing and settlement
│   └── Dispute/chargeback handling
│
├── Issuer (bank that issued the card)
│   ├── Authorization decision
│   ├── Fraud detection
│   ├── PIN verification (via HSM)
│   └── Balance/checking
│
├── Acquirer (merchant's bank/processor)
│   ├── Merchant onboarding
│   ├── Authorization submission
│   ├── Settlement initiation
│   └── Chargeback handling
│
└── Merchant (accepts card payments)
    ├── POS/online checkout
    ├── Tokenization
    └── Gateway to acquirer
```

## Test Cards

### Visa Test Cards

```
Legacy test cards (3DS1 era):
4111111111111111 — Visa default, CVV 123, any expiry
4012888888881881 — Visa two-track, CVV 123
4222222222222222 — Visa six-digit BIN

3DS2 test cards:
4000000000000002 — 3DS2 frictionless pass
4000000000000003 — 3DS2 challenge required
4000000000000069 — 3DS2 unavailable

Response simulation:
4000000000000002 + amount $2000 → decline (insufficient funds)
4000000000000002 + amount $2001 → approve
4000000000000002 + any amount + postal mismatch → decline

Note: CVV must be 123 for all test cards
Expiry must be in future (any valid future date)
```

### Mastercard Test Cards

```
Default test cards:
5555555555554444 — MC default, CVV 123, any future expiry
5105105105105100 — MC two-track, CVV 123
5105105105105100 + $2000+ → decline

3DS2 test:
5200000000000005 — MC SecureCode pass
5200000000000006 — MC SecureCode challenge
5200000000000007 — MC SecureCode fail

BIN ranges for testing:
510000 (low) → 559999 (high) — all valid test range
```

### Amex Test Cards

```
378282246310005 — Amex default, CVV 1234 (4 digits), any future expiry
371449635398431 — Amex two-track
```

### Other Schemes

```
Maestro (debit):
5033960000000000 — Maestro test
6000000000000000 — Maestro international

UnionPay:
6200000000000000 — UnionPay test (CUP)
6212345678901234 — UnionPay domestic

Discover:
6011000000000000 — Discover test

Diners:
36000000000000 — Diners test
```

## Test Scenarios

### 1. Authorization Testing

```
A. Standard authorization
   1. Submit test card (4111111111111111)
   2. Amount: $100
   3. Expect: approved (00 response code)
   4. Capture: auth code, transaction ID, scheme reference

B. Decline scenarios
   Test card → Amount → Expected response
   4000000000000002 → $2000+ → Insufficient funds
   4000000000000002 → postal_code mismatch → Decline
   5105105105105100 → $2000+ → Decline
   
C. CVV validation
   Submit correct CVV (123) → approved
   Submit wrong CVV → declined or CVV mismatch

D. Expiry validation
   Valid expiry (future) → approved
   Expired card → declined
   Invalid format (non-numeric) → error
```

### 2. Token Testing (Visa Tokenization)

```
VTS (Visa Token Services):
- API endpoint: https://sandbox.api.visa.com/vts/
- Test credentials required

Token operations:
1. Get token from test PAN
2. Map token → PAN (should work in test)
3. Detokenize: token → PAN
4. Token update: update expiry on token

Test flow:
POST /vts/tokens
{ "cardNumber": "4111111111111111", "expiryMonth": "12", "expiryYear": "2027" }
→ Response: token = "vt_test_xxx"

POST /vts/tokens/vt_test_xxx
→ Response: PAN = "4111111111111111"
```

### 3. 3D Secure Testing

```
3DS1 test flow:
1. Consumer enters card → redirect to ACS (Access Control Server)
2. ACS presents: Visa Verify, MC SecureCode page
3. Enter password → ACS returns success/fail
4. Merchant receives: ECI (Electronic Commerce Indicator)
   - ECI 5 = successful 3DS
   - ECI 6 = attempted 3DS
   - ECI 7 = failed/no 3DS

3DS2 test flow:
1. Merchant sends: 3RI (3DS Requestor Initiated) transaction
2. Issuer frictionless: returns authenticated
3. No challenge presented to consumer
4. Merchant receives: ECI 5 (frictionless pass)

Test:
4000000000000002 → Visa directory server → frictionless auth → ECI 5
4000000000000003 → Visa directory server → challenge → consumer enters OTP
```

### 4. Refund/Reversal Testing

```
A. Full refund
   1. Authorize: $100 → approved
   2. Refund: $100 → refund approved
   3. Verify: original transaction credited
   
B. Partial refund
   1. Authorize: $100 → approved
   2. Partial refund: $50 → partial refund approved
   3. Remaining: $50 available

C. Reversal (issuer-initiated)
   1. Authorize: $100 → approved
   2. Issuer reverses within window → debit reversed
   3. Merchant receives reversal notification

D. Timeout refund
   1. Do not capture within auth window (typically 7-30 days)
   2. After window: auto-void or manual void
   3. Test: does gateway handle expired auth gracefully?
```

### 5. Chargeback Testing

```
Chargeback reason codes (Visa):
- 10.1 — EMV liability shift (fraud)
- 12.1 — Card absent environment (fraud)
- 13.1 — Merchant perf (services not rendered)
- 13.2 — merchandise not as described

Test flow:
1. Capture legitimate transaction
2. Issue chargeback via scheme
3. Merchant receives: pre-arbitration, arbitration
4. Test: how does processor handle chargeback response?

Documentation required:
- Transaction record
- Authorization proof
- Delivery/completion proof
- Chargeback reason match
```

### 6. Clearing and Settlement Testing

```
Settlement testing:
1. Submit multiple auth transactions
2. Run end-of-day batching
3. Verify: settlement file contains correct amounts
4. Confirm: funds transferred to merchant account

Dispute testing:
1. Consumer disputes transaction
2. Acquirer receives dispute notification
3. Merchant responds with documentation
4. Test: end-to-end dispute resolution flow
```

## Scheme API Testing

### Visa Developer Platform

```
Sandbox: https://sandbox.api.visa.com/
Test credentials: Visa Dashboard → Projects → Credentials

APIs:
- Visa Direct (push payments)
- Visa Token Service (tokenization)
- Payment Account Validation Service (PAVS)
- Customer Billing Address Verification Service (CBAVS)
```

### Mastercard Developers

```
Sandbox: https://sandbox.mastercard.com/
Test keys: Mastercard Developer Hub

APIs:
- Mastercard Payment Gateway Service
- Mastercard Tokenization
- Mastercard Engage (3DS)
```

## Testing Checklist

```
[ ] Visa test cards authorized (4111, 4012, 4222)
[ ] Visa 3DS2 test cards (frictionless, challenge, unavailable)
[ ] MC test cards authorized (5555, 5105)
[ ] MC 3DS2 test cards (pass, challenge, fail)
[ ] Amex test cards authorized (3782, 3714)
[ ] Maestro test cards authorized
[ ] UnionPay test cards authorized
[ ] CVV validation tested (correct, wrong)
[ ] Expiry validation tested (valid, expired, invalid)
[ ] Decline scenarios tested
[ ] Tokenization: get token, detokenize
[ ] 3DS1: authorization, password
[ ] 3DS2: frictionless, challenge flows
[ ] Full refund tested
[ ] Partial refund tested
[ ] Reversal tested
[ ] Chargeback flow tested
[ ] Settlement batch tested
[ ] ECI codes verified
[ ] Visa sandbox API tested
[ ] MC sandbox API tested
```

## Evidence Preservation

- Transaction records for all test authorizations
- Scheme response codes captured
- 3DS challenge screenshots
- Settlement file samples
- Chargeback notification samples