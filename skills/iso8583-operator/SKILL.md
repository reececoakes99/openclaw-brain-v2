# SKILL: iso8583-operator

## Identity
- **Name:** iso8583-operator
- **Category:** Protocol Analysis
- **Trigger:** When working with any payment gateway that speaks ISO8583, or when evaluating card network protocol security
- **Confidence requirement:** 7/10 before operational use

## Overview

ISO8583 is the dominant message format for payment card transactions worldwide. Almost every payment switch, acquirer gateway, and card processor speaks some dialect of ISO8583. This skill gives the agent the ability to craft, send, parse, and manipulate ISO8583 messages for testing purposes.

ISO8583 has two main dialects in use:
- **HISO93** (ASCII) — Human-readable, field data as readable ASCII characters
- **HISO87 (binary)** — Compact, field data encoded in binary with BCD for numeric fields

Understanding which dialect a gateway uses is the first step.

## Operational Procedure

### Step 1: Identify the Gateway's ISO8583 Dialect

Before sending any messages, determine what variant the target uses.

```bash
# Send a TCP probe to the gateway port
nc -v target-gateway.com 7000
# Look for HISO93 (ASCII printable chars) vs HISO87 (binary/non-printable)

# Use the fingerprinter tool
python3 neopay/scripts/fingerprinter.py target-gateway.com 7000

# Check for known HISO93 patterns in response
echo -n "0200" | nc target-gateway.com 7000  # HISO93 starts with ASCII MTI
```

Dialect indicators:
- ASCII printable characters in response → HISO93
- Non-printable binary bytes in response → HISO87
- Field 0 (MTI) is always first 4 digits of any message

### Step 2: Craft an Authorization Message

Standard authorization request (MTI 0100):

**HISO93 format (ASCII):**
```
MTI     0100          (4 chars)
DE1     000           (1 char: position indicator)
DE2     4111111111111111  (PAN - 19 chars max)
DE3     000000          (partial translation code)
DE4     000000000100    (transaction amount - 12 chars)
DE7     0110091530      (transmission datetime MMDDhhmmss)
DE11    000001          (STAN - 6 chars)
DE12    1530091011      (local transaction datetime)
DE13    0110           (local date MMDD)
DE14    2512           (card expiry YYMM)
DE18    0000           (merchant category code)
DE22    001             (point of entry code - swiped)
DE32    19230001       (acquiring institution ID)
DE35    4111111111111111=2512  (track 2 data)
DE37    RRN123456        (reference number - 12 chars)
DE41    TERM12345       (terminal ID - 8 chars)
DE42    MERCHANT001     (merchant ID - 15 chars)
DE49    840             (currency code - 840=USD)
DE63    001             (settlement code)
```

**HISO87 format (binary):** Use `neopay/scripts/parse_iso8583.py` to construct:
```bash
python3 neopay/scripts/parse_iso8583.py \
  --dialect hiso87 \
  --mti 0100 \
  --pan 4111111111111111 \
  --amount 1000 \
  --datetime 2026-05-09T15:30:00 \
  --terminal TERM001 \
  --merchant MERCH001 \
  --output /tmp/auth_msg.bin
```

### Step 3: Transmit and Receive

```bash
# Send raw ISO8583 message
cat /tmp/auth_msg.bin | nc target-gateway.com 7000 -w 5 > /tmp/response.bin

# Parse response
python3 neopay/scripts/parse_iso8583.py \
  --dialect auto \
  --input /tmp/response.bin \
  --explain

# Expected response MTI: 0110 (authorization response)
# Key fields to examine:
# DE39 = response code (00 = approved, 05 = decline, 14 = invalid card)
# DE38 = authorization code
# DE54 = additional response data
```

### Step 4: Field Manipulation Testing

Test each field for boundary conditions:

```bash
# Amount boundary tests
python3 neopay/scripts/fuzzer.py \
  --target target-gateway.com:7000 \
  --dialect hiso93 \
  --field 4 \
  --variations "000000000001,000000000100,999999999999,000000000000"

# PAN variations - test card numbers
python3 neopay/scripts/fuzzer.py \
  --target target-gateway.com:7000 \
  --dialect hiso93 \
  --field 2 \
  --variations "4111111111111111,4111111111111112,5123456789012345,6011111111111117"

# RRN manipulation (DE37)
python3 neopay/scripts/fuzzer.py \
  --target target-gateway.com:7000 \
  --dialect hiso93 \
  --field 37 \
  --variations "RRN000000001,A1B2C3D4E5F6,000000000000,999999999999"
```

### Step 5: MAC Testing

Many gateways validate a MAC in DE64 or DE128. Test MAC bypass:

```python
# Using hsm_simulator to generate valid MAC
python3 neopay/scripts/hsm_simulator.py \
  --command MAC_GENERATE \
  --key-index 1 \
  --data "$(cat /tmp/auth_msg_b64)" \
  --algorithm ISO9797_1

# Inject into message and send
python3 neopay/scripts/mac_generator.py \
  --insert-mac \
  --message /tmp/auth_msg.bin \
  --mac "$(python3 neopay/scripts/hsm_simulator.py --command MAC_GENERATE ...)" \
  --field 64 \
  --output /tmp/mac_msg.bin
```

### Step 6: ARQC/ARPC Testing

For chip card authentication testing:

```bash
# Generate ARQC challenge
python3 neopay/scripts/hsm_simulator.py \
  --command ARQC_GENERATE \
  --pan 4111111111111111 \
  --pan-seq 01 \
  --amount 1000 \
  --txn-datetime 250509153000 \
  --atc 0001 \
  --unpredictable-num 12345678

# Verify ARPC response
python3 neopay/scripts/hsm_simulator.py \
  --command ARPC_VERIFY \
  --arqc <arqc_from_card> \
  --arpc <arpc_from_issuer> \
  --cpsn 000001
```

## Message Types Quick Reference

| MTI | Description | Common Response |
|---|---|---|
| 0100 | Authorization request | 0110 |
| 0110 | Authorization response | — |
| 0200 | Financial transaction | 0210 |
| 0210 | Financial response | — |
| 0220 | Reversal | 0230 |
| 0230 | Reversal response | — |
| 0400 | Management request | 0410 |
| 0800 | Network test | 0810 |
| 0820 | Network test response | — |

## Common DE Fields

| Field | Name | Size | Notes |
|---|---|---|---|
| DE2 | Primary Account Number | 19 | Card number |
| DE3 | Processing Code | 6 | Transaction type |
| DE4 | Transaction Amount | 12 | In cents |
| DE7 | Transmission Date/Time | 10 | MMDDhhmmss |
| DE11 | STAN | 6 | Trace number |
| DE12 | Local Transaction Time | 12 | hhmmss MMDD |
| DE14 | Card Expiry Date | 4 | YYMM |
| DE22 | POS Entry Mode | 3 | Swipe/EMV/Chip |
| DE35 | Track 2 Data | 37 | Card data |
| DE37 | Retrieval Reference | 12 | Unique per txn |
| DE38 | Authorization Code | 6 | Issuer response |
| DE39 | Response Code | 2 | 00=approved |
| DE41 | Terminal ID | 8 | Unique per terminal |
| DE42 | Merchant ID | 15 | Unique per merchant |
| DE49 | Currency Code | 3 | 840=USD |
| DE64 | MAC | 8/16 | Message auth code |
| DE128 | MAC | 8/16 | Alternate MAC field |

## Detection and Response Codes

| DE39 | Meaning | Use |
|---|---|---|
| 00 | Approved | Success |
| 01 | Refer to card issuer | Decline |
| 05 | Do not honor | Decline |
| 12 | Invalid transaction | Check field format |
| 14 | Invalid card number | Check PAN |
| 51 | Insufficient funds | Decline |
| 54 | Expired card | Check DE14 |
| 63 | MAC verification failed | Check DE64 |

## Output

All ISO8583 interactions are logged to:
- `knowledge/payment_protocol_db/protocols.json` — protocol fingerprint data
- `knowledge/gateway_profiles/<target>/` — per-target protocol notes

## Cross-References

- `memory/procedures/iso8583_attack.md` — full attack playbook
- `neopay/scripts/fuzzer.py` — field fuzzing tool
- `neopay/scripts/parse_iso8583.py` — message parser
- `bot_hunter.md` — HUNTER bot deployment
- `neopay/references/iso8583.md` — protocol reference

## Troubleshooting

| Problem | Solution |
|---|---|
| No response from gateway | Check port, try SSL wrapper (stunnel), verify network reachability |
| Response garbled/binary | Wrong dialect — switch from HISO93 to HISO87 |
| MAC failure (DE39=63) | Generate correct MAC using shared secret, or check key index |
| Invalid MTI response | Gateway doesn't speak ISO8583 — try REST/JSON API instead |
| Connection reset | Gateway closed connection — check for timeout, firewall, or protocol mismatch |