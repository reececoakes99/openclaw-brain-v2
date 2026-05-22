# SKILL: token-vault

## Identity
- **Name:** token-vault
- **Category:** Payment Security Testing
- **Trigger:** When working with tokenized payment systems (Stripe, Braintree, Vault-based systems), or when mapping tokens back to card numbers
- **Confidence requirement:** 7/10

## Overview

Tokenization replaces card numbers with surrogate tokens to reduce PCI-DSS scope. But tokens are only as strong as the vault that generates them. This skill covers token format analysis, token-to-card mapping, vault correlation attacks, and token extraction techniques.

## Operational Procedure

### Step 1: Identify Tokenization Provider

```bash
# Check for Stripe tokens (starts with tok_ or pi_)
grep -r "tok_" knowledge/gateway_profiles/<target>/ 2>/dev/null

# Check for Braintree tokens ( opaqueValue format)
# Braintree uses opaque tokens in JavaScript SDK

# Check for Vantiv/iQor tokens (UUID format)
# UUID v4 tokens often indicate tokenization platform

# Check response headers for tokenization provider fingerprints
curl -sI https://target.com/checkout | grep -i "stripe\|braintree\|vantiv\|tokenex"

# Analyze JavaScript for token format patterns
curl -s https://target.com/ | grep -oE "(tok_|pi_|pm_|card_)[a-zA-Z0-9]+"
```

Token format indicators:
| Provider | Format | Example |
|---|---|---|
| Stripe | `tok_`, `pi_`, `pm_` + 24 chars | `tok_1ABC2DEF3GHI4JKL` |
| Braintree | Opaque string | `opaque_value_abc123` |
| Vantiv | UUID v4 | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` |
| TokenEx | 16-32 char alphanumeric | `Tkn_AbCdEfGhIjKlMnOp` |
| Custom | Often MD5/SHA1 of PAN | `d41b5c9e1f7a8b2c3d4e5f6a7b8c9d0e` |

### Step 2: Analyze Token Format

```bash
# Token entropy analysis (high entropy = UUID/random, low = hash)
python3 neopay/scripts/parse_iso8583.py --analyze-token "tok_1ABC2DEF3GHI4JKL"

# Check for timestamp encoding in token (UUID v1)
# UUID v1 contains timestamp — can reveal token generation time

# Check for sequential patterns in tokens
# Send multiple transactions, compare token formats

# MD5 format detection (32 hex chars, no dashes)
echo -n "4111111111111111" | md5sum
# Compare against observed token format

# Check for card-last-4 in token
# Some vaults encode last 4 directly in token
echo "Looking for: last4 embedded in token format"
```

### Step 3: Token Correlation Testing

```bash
# Test: Does same card always produce same token?
# Send multiple transactions with identical card
# Check if token is deterministic (security risk)

# Test: Does different card ever produce same token? (collision)
# Should never happen with proper tokenization

# Test: token prefix analysis
# Some platforms use prefix to identify card network
# Visa: starts with 4
# MC: starts with 5
# Amex: starts with 3

# Script to test token correlation
python3 << 'PY'
tokens = []
card = "4111111111111111"
for i in range(5):
    # Send transaction via payment API
    # Record returned token
    pass
# Check if tokens are identical
print("Token correlation test:")
print(f"Same card = Same token: {len(set(tokens)) == 1}")
PY
```

### Step 4: Token-to-Card Mapping

```bash
# If token uses reversible format:
# Check for XOR patterns (PAN ⊕ something = token)
python3 << 'PY'
# XOR PAN with token to find derivation key
pan = "4111111111111111"
token_hex = "A1B2C3D4E5F6A7B8"
pan_bytes = bytes.fromhex(pan)
token_bytes = bytes.fromhex(token_hex)
xor_result = bytes(a ^ b for a, b in zip(pan_bytes, token_bytes))
print(f"XOR result: {xor_result.hex()}")
PY

# Rainbow table attack (if tokens are MD5 of PAN)
# Precompute MD5 of all possible PANs for targeted BIN range
echo "Rainbow table approach: generate MD5(PAN) for BIN 411111"
echo "Requires: known token + target BIN range + compute power"

# Token enumeration attack
# Only viable if vault has weak rate limiting
python3 << 'PY'
# Enumerate tokens by modifying one character at a time
import itertools
charset = "abcdefghijklmnopqrstuvwxyz0123456789"
# Generate variations of known token
token_base = "tok_abc123def456"
for combo in itertools.product(charset, repeat=3):
    new_token = token_base[:8] + ''.join(combo) + token_base[11:]
    # Test if token is valid via API
    pass
PY
```

### Step 5: Multi-Vault Correlation

```bash
# Test: Merchant uses multiple processors
# Can we correlate tokens across processors to same card?
echo "Multi-processor token correlation:"
echo "1. Find processor A token for known card"
echo "2. Find processor B token for same card"
echo "3. Compare token formats and patterns"
echo "4. Check if same card = correlated tokens"

# Test: Token migration on processor upgrade
# Old processor replaced by new one
# Check if existing tokens still work (migration) or new tokens issued

# Script to test multi-vault
python3 << 'PY'
# Test token portability across processors
processors = ["stripe", "braintree", "vantiv"]
for p in processors:
    token = get_token(p, "4111111111111111")
    print(f"{p}: {token}")
    verify_token(p, token)  # Check if token is valid
PY
```

### Step 6: Network-Level Token Extraction

```bash
# ARP spoofing on payment LAN to intercept token traffic
# Only during authorized internal testing
echo "=== Internal network token interception ==="
echo "Target: payment processing VLAN"
echo "Tools: arpspoof, tcpdump, ettercap"

# TCPdump capture on payment network segment
tcpdump -i eth0 -nn -s0 -c 100 'tcp port 443' -w /tmp/token_capture.pcap

# Analyze captured tokens
python3 neopay/scripts/pcap_tools.py \
  --input /tmp/token_capture.pcap \
  --extract-strings \
  --filter "tok_|pi_|pm_|card_"

# Check for token in HTTP headers/body
python3 neopay/scripts/pcap_tools.py \
  --input /tmp/token_capture.pcap \
  --extract-json \
  --look-for "token"
```

## Token Format Reference

| Format | Example | Entropy | Reversible? |
|---|---|---|---|
| UUID v1 | `a1b2c3d4-e5f6-7890-abcd-ef1234567890` | High | Yes (timestamp) |
| UUID v4 | `a1b2c3d4-e5f6-4a90-bcde-f1234567890` | High | No |
| MD5(PAN) | `d41b8e1f7a2b3c4d5e6f7a8b9c0d1e2f` | Medium | Via rainbow table |
| SHA1(PAN) | `4111111111111111a1b2c3d4e5f6a7b8c9d0e` | High | No |
| Custom 32-char | `TknAbCdEfGhIjKlMnOpQrStUvWx` | Medium | Likely |
| Stripe format | `tok_1ABC2DEF3GHI4JKL` | High | No |
| Braintree opaque | `opaque_abc123DEF456` | High | No |

## Output

Token analysis goes to:
- `knowledge/gateway_profiles/<target>/token_format.json` — token format findings
- `knowledge/gateway_profiles/<target>/token_correlation.json` — correlation test results

## Cross-References

- `memory/procedures/token_vault_extraction.md` — full playbook
- `neopay/references/pci_dss.md` — tokenization requirements
- `bot_hunter.md` — HUNTER bot procedures

## Troubleshooting

| Problem | Solution |
|---|---|
| Token format unknown | Analyze multiple samples, check JS SDK, check API responses |
| Token enumeration blocked | Rate limiting detected — back off, document finding |
| Can't intercept network | No LAN access — use API testing instead |
| Token correlation fails | Different processors may use different vaults — expected |