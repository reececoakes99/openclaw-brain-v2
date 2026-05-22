# Payload Templates Index

## Overview
This directory contains categorized payload templates for payment gateway security testing. Each payload is designed for specific target types and should be used within authorized engagement scopes only.

---

## Directory Structure

```
payload_templates/
├── README.md                    # This file
├── iso8583/
│   ├── pin_block_fuzz.hex      # PIN block fuzzing template
│   ├── message_replay.py       # ISO8583 transaction replay
│   ├── arqc_bypass.hex         # ARQC bypass proof-of-concept
│   ├── mac_injection.py        # MAC injection template
│   └── de103_extraction.py     # DE103 (extended data) extraction
├── web/
│   ├── sql_injection.txt       # SQL injection test strings
│   ├── ssrf_probes.txt         # SSRF testing targets
│   ├── jwt_manipulation.py     # JWT algorithm manipulation
│   ├── xss_payloads.txt        # XSS payloads for admin panels
│   ├── open_redirect.txt       # Open redirect validation
│   └──idor_probes.txt          # IDOR testing patterns
├── api/
│   ├── fuzzing_rules.yaml      # API fuzzing configuration
│   ├── graphql_introspection.py # GraphQL introspection queries
│   ├── rest_auth_bypass.py     # REST API auth bypass techniques
│   └── mass_assignment.py       # Mass assignment test vectors
├── hsm/
│   ├── key_slot_enum.py         # HSM key slot enumeration
│   ├── pin_block_inject.hex    # ISO9564 PIN block injection
│   ├── mac_generation.py       # MAC generation test vectors
│   └── zone_key_extraction.py  # Zone key extraction attempts
├── token/
│   ├── token_format_fuzz.py    # Payment token format testing
│   ├── token_reuse.py          # Token reuse exploitation
│   └── vault_probe.sh          # Token vault probing
└── protocol/
    ├── spdh_desync.py           # SPDH desynchronization
    ├── spdh_inject.py           # SPDH message injection
    ├── xflow_fingerprint.py     # Verifone XFlow fingerprint
    └── custom_protocol_fuzz.py  # Generic protocol fuzzer template
```

---

## ISO8583 Payloads

### pin_block_fuzz.hex
- **Type:** Protocol / Cryptographic
- **Target Protocol:** ISO8583 HISO93-ASCII
- **Description:** Hex template for fuzzing DE52 (PIN Data) field with malformed ISO9564 PIN blocks
- **Example:** `0412` prefix followed by random 16-byte blocks

### message_replay.py
- **Type:** Protocol / Replay Attack
- **Target Protocol:** ISO8583
- **Description:** Python script to replay captured valid transaction with modified fields
- **Example:** Replays transaction with changed amount field

### arqc_bypass.hex
- **Type:** Protocol / Cryptographic
- **Target:** ARQC/ARPC validator / HSM
- **Description:** Crafted message designed to bypass ARQC verification
- **Warning:** HIGH RISK — use only in isolated test environment

---

## Web Application Payloads

### sql_injection.txt
- **Type:** Web / Injection
- **Target:** API endpoints, admin panels
- **Description:** SQL injection test strings for authentication and data endpoints
- **Example:** `' OR '1'='1`, `'; DROP TABLE users;--`

### ssrf_probes.txt
- **Type:** Web / SSRF
- **Target:** Webhook callbacks, URL parameters
- **Description:** SSRF testing targets including cloud metadata endpoints
- **Example:** `http://169.254.169.254/latest/meta-data/`

### jwt_manipulation.py
- **Type:** Web / Authentication
- **Target:** JWT-protected endpoints
- **Description:** JWT manipulation including alg:none attack, weak secret brute force
- **Example:** `{"alg": "none"}` header modification

---

## API Payloads

### fuzzing_rules.yaml
- **Type:** API / Fuzzing
- **Target:** REST API endpoints
- **Description:** YAML configuration for mass parameter fuzzing
- **Example:** Defines parameter types, fuzzing strategies, expected responses

### graphql_introspection.py
- **Type:** API / GraphQL
- **Target:** GraphQL endpoints
- **Description:** GraphQL introspection query to extract full schema
- **Example:** `__schema { types { name fields { name type } } }`

---

## HSM Payloads

### key_slot_enum.py
- **Type:** Hardware Security Module
- **Target:** HSM management port
- **Description:** Python script to enumerate HSM key slots via vendor-specific commands
- **Example:** Thales PayShield `LIST SLOTS` command

### pin_block_inject.hex
- **Type:** Hardware Security Module / PIN Processing
- **Target:** PIN processing subsystem
- **Description:** ISO9564 Format 0 PIN block injection with null PIN
- **Warning:** CRITICAL RISK — potential for PIN compromise

---

## Token Payloads

### token_format_fuzz.py
- **Type:** Token / Format Confusion
- **Target:** Tokenization provider / vault
- **Description:** Fuzzing tool to test token format parsing and validation
- **Example:** Tests various token formats (UUID, numeric, alphanumeric)

### token_reuse.py
- **Type:** Token / Replay
- **Target:** Token vault, tokenized payment flow
- **Description:** Attempts to reuse valid tokens across different contexts
- **Example:** Use payment token for different merchant or amount

---

## Protocol Payloads

### spdh_desync.py
- **Type:** POS Protocol
- **Target:** Verifone XFlow / SPDH listener
- **Description:** Script to send malformed sequence to desynchronize POS terminal
- **Example:** Sequence number mismatch injection

### spdh_inject.py
- **Type:** POS Protocol / Injection
- **Target:** Transaction capture point
- **Description:** Injects custom transaction data into POS flow
- **Example:** Modifies transaction amount before settlement

---

## Usage Guidelines

### Pre-Execution Checklist
1. ✅ Confirm target is within authorized scope
2. ✅ Review abort conditions in playbook.yaml
3. ✅ Verify network isolation of test environment
4. ✅ Validate payload is appropriate for target version
5. ✅ Document expected outcome before execution

### Payload Selection Matrix

| Target Type | Priority Payloads | Risk Level |
|------------|-------------------|------------|
| ISO8583 Gateway | arqc_bypass, mac_injection | Critical |
| SPDH POS | spdh_desync, spdh_inject | High |
| HSM Interface | key_slot_enum, pin_block_inject | Critical |
| Admin Panel | jwt_manipulation, sql_injection | High |
| API (REST) | fuzzing_rules, rest_auth_bypass | Medium |
| Token Vault | token_format_fuzz, token_reuse | High |
| Webhook Handler | ssrf_probes, xss_payloads | Medium |

### Disclaimer
All payloads in this directory are intended for authorized security testing only. Unauthorised use against payment systems may violate PCI DSS, local laws, and international regulations. The operators accept no liability for misuse.
