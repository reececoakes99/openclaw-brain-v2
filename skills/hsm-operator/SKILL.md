# SKILL: hsm-operator

## Identity
- **Name:** hsm-operator
- **Category:** Cryptographic Operations
- **Trigger:** When working with HSM-protected payment systems, or testing key management infrastructure
- **Confidence requirement:** 8/10 before operational use (HSM interactions are irreversible)

## Overview

Hardware Security Modules (HSMs) protect the cryptographic keys used in payment infrastructure. They're the vault — compromise an HSM and you compromise the entire payment network. This skill covers the command interface, key operations, and testing procedures for common HSMs (Thales PayShield, AWS CloudHSM, GCP Cloud KMS).

**Never send commands to a production HSM.** Use simulators for testing.

## Operational Procedure

### Step 1: Identify HSM Type and Interface

```bash
# Check for Thales PayShield (common port 8443 for admin)
nc -v target-hsm.internal 8443
# PayShield admin interface uses proprietary command language

# Check for CloudHSM (AWS)
aws cloudhsm describe-clusters --region us-east-1

# Check connectivity to GCP Cloud KMS
gcloud kms keyrings list --location global

# Use the HSM simulator for all testing
python3 neopay/scripts/hsm_simulator.py --mode server --port 8444
```

HSM interface types:
- **Thales PayShield Manager (PSM)** — TCP port 8443, proprietary protocol
- **AWS CloudHSM** — AWS CLI or PKCS#11 interface
- **GCP Cloud KMS** — REST API with OAuth2
- **nCipher** — CSP/PKCS#11 interface

### Step 2: PIN Block Operations

PIN blocks are the most commonly tested HSM function:

```bash
# Generate PIN block (ISO9564 Format 0)
python3 neopay/scripts/hsm_simulator.py \
  --command PIN_BLOCK_GENERATE \
  --pin 1234 \
  --pan 4111111111111111 \
  --format 0 \
  --output /tmp/pin_block.hex

# PIN block formats:
# Format 0: PIN ⊕ PAN (last 12 digits)
# Format 1: Reserved
# Format 2: PIN ⊕PAN (last 12 digits + MRD)
# Format 3: ISO 9564 Format 3 (TECB)

# Translate PIN block between formats
python3 neopay/scripts/pin_block.py \
  --translate \
  --input-format 0 \
  --output-format 3 \
  --pin-block "$(cat /tmp/pin_block.hex)" \
  --pan 4111111111111111
```

**PIN Verification Attack:**
```bash
# Generate PIN verification data from known PIN
python3 neopay/scripts/hsm_simulator.py \
  --command PIN_VERIFY \
  --pin 1234 \
  --pan 4111111111111111 \
  --encrypted-pin <encrypted_pin_block>

# Enumerate PIN by brute force (throttled)
python3 neopay/scripts/pin_block.py \
  --brute-force \
  --pan 4111111111111111 \
  --encrypted-pin <target_pin_block> \
  --max-attempts 3
```

### Step 3: MAC Generation

Message Authentication Codes verify message integrity:

```bash
# Generate ISO9797-1 MAC (CBC)
python3 neopay/scripts/hsm_simulator.py \
  --command MAC_GENERATE \
  --algorithm ISO9797_1 \
  --key-index 1 \
  --data "02003400000000000010001100915300000001" \
  --output /tmp/mac.hex

# Generate EMV MAC
python3 neopay/scripts/hsm_simulator.py \
  --command MAC_GENERATE \
  --algorithm EMV \
  --data "$(cat /tmp/message_b64)" \
  --output /tmp/emv_mac.hex

# Verify MAC
python3 neopay/scripts/mac_generator.py \
  --verify \
  --mac "$(cat /tmp/mac.hex)" \
  --message "$(cat /tmp/message.hex)" \
  --algorithm ISO9797_1
```

**MAC Bypass Testing:**
```bash
# Try sending with incorrect MAC
python3 neopay/scripts/fuzzer.py \
  --target target-gateway.com:7000 \
  --dialect hiso93 \
  --field 64 \
  --variations "0000000000000000,FFFFFFFFFFFFFFFF,1111111111111111"

# Try sending without MAC field entirely
# Check if DE64 is optional or enforced

# Test key index confusion
python3 neopay/scripts/fuzzer.py \
  --target target-gateway.com:7000 \
  --dialect hiso93 \
  --field 64 \
  --variations "KEY0000000000,KEY9999999999,0000000000000000"
```

### Step 4: Key Operations

```bash
# Generate KEK (Key Encrypting Key)
python3 neopay/scripts/hsm_simulator.py \
  --command KEY_GENERATE \
  --key-type KEK \
  --scheme SINGLE_DEA \
  --output /tmp/kek.hex

# Generate DEK (Data Encrypting Key)
python3 neopay/scripts/hsm_simulator.py \
  --command KEY_GENERATE \
  --key-type DEK \
  --scheme DOUBLE_TDES \
  --output /tmp/dek.hex

# Import clear key (testing only)
python3 neopay/scripts/hsm_simulator.py \
  --command KEY_IMPORT \
  --key-type ZMK \
  --key-data "0123456789ABCDEF0123456789ABCDEF" \
  --key-index 1

# Derive key from master key
python3 neopay/scripts/hsm_simulator.py \
  --command KEY_DERIVE \
  --master-key-index 0 \
  --component "COMPONENT_A" \
  --output /tmp/derived_key.hex

# Key check value calculation
python3 neopay/scripts/hsm_simulator.py \
  --command KEY_CHECK \
  --key "$(cat /tmp/kek.hex)" \
  --output /tmp/kcv.hex
```

### Step 5: ARQC/ARPC Operations

For EMV chip card authentication:

```bash
# Generate Authentication Cryptogram Request
python3 neopay/scripts/hsm_simulator.py \
  --command ARQC_GENERATE \
  --pan 4111111111111111 \
  --pan-seq 01 \
  --amount 000000000100 \
  --currency 840 \
  --country 840 \
  --txn-datetime 250509153000 \
  --atc 0001 \
  --unpredictable-num 12345678 \
  --terminal-capability "8C" \
  --terminal-type E1 \
  --output /tmp/arqc.hex

# Verify ARPC
python3 neopay/scripts/hsm_simulator.py \
  --command ARPC_VERIFY \
  --arqc "$(cat /tmp/arqc.hex)" \
  --arc 3030 \
  --cpsn 000001 \
  --output /tmp/arpc_verified.hex

# Generate ARPC from issuer
python3 neopay/scripts/hsm_simulator.py \
  --command ARPC_GENERATE \
  --arqc "$(cat /tmp/arqc.hex)" \
  --arc 3030 \
  --cpsn 000001 \
  --cryptogram-type AAC
```

### Step 6: Key Extraction Testing (If Authorized)

```bash
# Test for lazy key loading (key loaded in plaintext)
# This tests for CVE in HSM configuration

# Test key component reuse
# Attempt to use same key component for multiple keys

# Check for default key patterns
python3 neopay/scripts/hsm_simulator.py \
  --command KEY_CHECK \
  --key "00000000000000000000000000000000" \
  --output /tmp/default_kcv.hex

# Compare against known default KCVs
# Common defaults: 000000, FFFFFF, A1B1C1D1E1F1A2B2

# Test key index enumeration
for i in $(seq 0 99); do
  python3 neopay/scripts/hsm_simulator.py \
    --command KEY_CHECK \
    --key-index $i \
    --output /tmp/kcv_${i}.hex
done | grep -v "ERROR"
```

## Key Schemes Reference

| Scheme | Key Length | Use |
|---|---|---|
| Single DEA (K3) | 16 hex chars (64-bit) | PIN translation only |
| Double TDES (K2) | 32 hex chars (128-bit) | Most common |
| Triple TDES (K1) | 48 hex chars (192-bit) | Legacy systems |
| AES-128 | 32 hex chars | Modern systems |
| AES-256 | 64 hex chars | High-security |

## Thales PayShield Commands

| Command | Description |
|---|---|
| HA | Generate AUTH cryptogram |
| HB | Verify AUTH response |
| JC | Translate PIN block |
| KA | Generate MAC |
| KC | Generate key check value |
| KE | Import key component |
| KK | Generate session key |
| OA | Import clear key |
| OG | Generate random number |

## Output

HSM interaction logs go to:
- `knowledge/gateway_profiles/<target>/` — HSM interaction logs
- `neopay/scripts/hsm_simulator.log` — simulator activity log

## Cross-References

- `memory/procedures/hsm_attack.md` — full HSM attack playbook
- `neopay/references/hsm.md` — HSM operations reference
- `neopay/scripts/pin_block.py` — PIN block operations
- `neopay/scripts/mac_generator.py` — MAC generation
- `neopay/scripts/hsm_simulator.py` — HSM command simulator

## Troubleshooting

| Problem | Solution |
|---|---|
| Connection refused to HSM | Check port, firewall rules, TLS version |
| Authentication failed | Verify key index, check shared secret |
| Invalid MAC | Verify MAC algorithm matches gateway expectation |
| PIN verification failed | Check PAN format (no spaces, 16 digits) |
| ARQC rejected | Verify all cryptogram fields are correct |
| Key import fails | Check key format (hex, even-length), scheme compatibility |