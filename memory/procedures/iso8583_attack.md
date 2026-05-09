# ISO8583 Payment Attack Procedures

## Overview

ISO8583 is the dominant financial transaction messaging standard. Attacks target message parsing, field validation, MAC verification, and transaction flow logic.

## Message Structure

```
MTI (4) | bitmap (8/16/32) | data elements (variable)
```

**Common MTI variants:**
- `0100` — Authorization request
- `0110` — Authorization response
- `0200` — Financial transaction request
- `0210` — Financial transaction response
- `0420` — Reversal request
- `0430` — Reversal response

## Pre-Attack Recon

```
1. Identify HISO variant: HISO93 (binary) vs HISO87 (ASCII)
2. Determine bitmap length: primary only (8 bytes) vs secondary (16 bytes)
3. Map data element layout from documentation or traffic capture
4. Identify MAC algorithm: ISO9797-1 (CBC) or ISO9797-3
5. Check for field-level encryption (encrypted PIN, encrypted track data)
6. Probe response codes: send malformed messages, observe error handling
```

## Attack Vectors

### 1. MTI Manipulation

```
Test: Send reversed MTI pairs
0100 → 0110 (valid pair)
0100 → 0120 (invalid, check for bypass)
0100 → 0140 (reversal pair - may trigger adjustment)

Edge cases:
- Non-financial MTI (0800/0810 = key exchange)
- Network management MTI (0800) with financial data
- Overflow MTI (9999)
```

### 2. Bitmap Field Injection

```
Primary bitmap only (8 bytes):
- Toggle bits on/off to trigger undefined fields
- Send field 3 (processing code) with transaction type manipulation
- Field 4 (amount) integer overflow: use negative, zero, max uint64

Secondary bitmap (16 bytes):
- Trigger field 62 (POS data) for terminal compromise
- Field 63 (additional data) for custom payload injection
```

### 3. MAC Bypass Techniques

```
A. Key reuse attack
   - Capture valid transaction MAC
   - Replay same message with modified amount
   - Verify: does same MAC validate?

B. Partial message MAC
   - Send truncated message (MAC over fewer fields)
   - Some gateways validate MAC over subset of fields

C. Algorithm downgrade
   - Inject DES instead of 3DES in key exchange (0800)
   - Weak algorithm may accept known plaintext

D. Key exchange interception
   - 0800/0810 key exchange messages
   - Extract encrypted key component
   - Derive working key from captured exchanges
```

### 4. ARQC/ARPC Authentication Testing

```
ARQC (Authentication Request Cryptogram):
- Send captured ARQC with modified PAN or amount
- Test: does gateway accept ARQC replay?
- Check: expiry handling, velociy limits

ARPC (Authentication Response Cryptogram):
- ARPC generation: 80 + cryptogram from issuer
- Test: can you generate valid ARPC without issuer key?
- Verify: response code field 39 in ARPC reply
```

### 5. PIN Block Attacks

```
Format: ISO9564-1 (IBM 3624)
PIN block = TPAD ⊕ PIN ⊕ PAN

Attack: PAN oracle
- Know: encrypted PIN block, partial PAN (last 4 digits)
- Unknown: first 6-10 digits of PAN
- Attack: brute force first digits using known TPAD pattern
- Tool: use HSM simulator for bulk PIN block generation

Format: ISO9564-3 (Account-based)
PIN block = random ⊕ PIN ⊕ account_number
Attack: if account number is predictable/known, derive PIN
```

### 6. Field-Level Fuzzing

```
High-value fields to fuzz:
- Field 2 (PAN): invalid lengths, invalid check digits
- Field 3 (Processing code): transaction type switching
  - Purchase (00) → Cash (01) → Refund (02) → Balance (03)
- Field 4 (Amount): negative, zero, fractional, max uint64, overflow
- Field 14 (Expiry): past dates, invalid months, 4-digit years
- Field 22 (POS entry mode): SWIPED (021) → CHIP (051) → MANUAL (012)
- Field 35 (Track 2): modify discretionary data, expiry, PVV field
- Field 38 (Auth code): replay captured auth codes
- Field 39 (Response code): force approve (00) in response
```

### 7. Transaction Lifecycle Attacks

```
A. Pre-authorization capture
   -抓 capture pre-auth at low amount
   - Capture authorization code
   - Increment to full amount without re-authorization

B. Reversal manipulation
   - Send 0420 with legitimate PAN+amount from real transaction
   - Verify: does reversal actually reverse or does it create duplicate?
   - Check: double-reversal vulnerability

C. Timeout exploitation
   - Send slow-response transaction, don't complete
   - Observe: does gateway hold authorization indefinitely?
   - Exploit: extend timeout, duplicate authorization
```

## Testing Checklist

```
[ ] MTI pairs tested (0100/0110, 0200/0210, 0420/0430)
[ ] Primary bitmap toggled (all 64 bits)
[ ] Secondary bitmap toggled (all 128 bits)
[ ] Field 3 processing codes swapped
[ ] Field 4 amounts tested (0, negative, max, overflow)
[ ] Field 14 expiry manipulated
[ ] Field 22 POS entry mode switched
[ ] Field 38 auth code replayed
[ ] Field 39 response code forced (00 = approve)
[ ] MAC replay tested
[ ] ARQC/ARPC tested
[ ] PIN block format tested
[ ] Key exchange (0800) intercepted
[ ] Reversal injection tested
[ ] Timeout behavior mapped
```

## Evidence Preservation

- Full message hex dump for every test
- Wireshark PCAP with ISO8583 dissection
- Screenshot/record of any successful exploitation
- Hash of any captured keys or data