# NEOPAY — Payment Gateway Attack Framework

Elkin's embedded payment infrastructure attack knowledge base.

## Overview

This framework provides deep technical knowledge for:
- ISO8583 message injection and protocol manipulation
- HSM key extraction and cryptographic attacks
- POS terminal exploitation (SPDH, HPDH, Verifone XFlow)
- Payment checkout injection and token manipulation
- Token vault extraction and correlation attacks
- Webhook hijacking and replay
- PCI-DSS compliance exploitation
- Scheme-level testing (Visa/MC/Amex/UnionPay)

## Structure

```
neopay/
├── SKILL.md                    ← This file
├── ATTACK_PLAYBOOK.md          ← Full attack methodology
├── references/                ← Protocol references
│   ├── iso8583.md            ← ISO8583/HISO93/HISO87
│   ├── hsm.md                ← HSM integration + attacks
│   ├── pos_protocols.md      ← SPDH, HPDH, XFlow
│   ├── iso20022.md           ← ISO20022 MX messages
│   ├── pci_dss.md            ← PCI-DSS exploitation
│   ├── compliance.md         ← Regulatory exploitation
│   └── software_stack.md     ← Payment software stack
├── scripts/                   ← Attack tools
│   ├── iso8583_fuzzer.py     ← ISO8583 message fuzzer
│   ├── pin_block.py          ← PIN block generator
│   ├── hsm_simulator.py      ← HSM command simulator
│   ├── crypto_downgrade.py   ← Crypto downgrade tester
│   ├── bot_monitor.py        ← Bot monitoring dashboard
│   └── transaction_flow.py   ← Transaction flow analyzer
├── assets/                    ← Test data + configs
│   ├── test_data/
│   │   ├── card_ranges.json  ← BIN ranges (Visa, MC, Amex)
│   │   ├── iso_payloads.json ← Sample ISO8583 payloads
│   │   └── test_cards.json   ← Test card numbers
│   ├── terraform/            ← Infra configs (AWS/GCP)
│   └── kubernetes/           ← K8s attack manifests
└── references/COMMANDS.md     ← HSM command reference
```

## Core Capabilities

### Protocol Exploitation
- ISO8583 message crafting, field manipulation, MAC bypass
- ARQC/ARPC authentication testing
- Transaction replay and modification
- Multi-message attack sequences

### Terminal Attacks
- SPDH/HPDH protocol exploitation
- Verifone XFlow remote commands
- Terminal firmware extraction
- PIN pad compromise

### Checkout Warfare
- Web injection in payment forms
- Token manipulation and price override
- Business logic bypass
- Race condition exploitation

### Data Extraction
- Token vault correlation attacks
- Transaction data harvesting
- PII and card data exfiltration
- Evidence preservation

## Usage

Load relevant reference before payment gateway engagement:
1. Read `references/iso8583.md` for ISO8583 protocol
2. Read `references/hsm.md` for HSM attacks
3. Read `references/pos_protocols.md` for terminal exploits
4. Load `scripts/iso8583_fuzzer.py` for protocol testing
5. Use `assets/test_data/card_ranges.json` for BIN mapping


## ISO20022 / SWIFT Module

### Overview
The `iso20022_converter.py` script provides full bidirectional conversion between SWIFT MT messages and ISO20022 MX XML format, enabling:
- Parsing of SWIFT MT103, MT202, MT900, MT910, MT940, MT950 messages
- Generation of ISO20022 pacs.008, pacs.009, camt.053, camt.054 messages
- JSON/SQL/CSV export for data warehouse integration
- Message validation against XSD schemas

### Key Scripts
| Script | Function |
|---|---|
| `iso20022_converter.py` | SWIFT MT ↔ ISO20022 MX ↔ JSON conversion |
| `clearing_settlement.py` | Visa CTF / Mastercard IPM batch processing |
| `qr_payments_connector.py` | EMV QR code generation, parsing, validation |
| `spdh_client.py` | SPDH/HPDH POS terminal protocol client |

### ISO20022 Attack Surface
- **Schema injection**: Malformed XML in ISO20022 MX messages
- **Amount field overflow**: Large decimal values in `<Amt>` fields
- **IBAN validation bypass**: Non-standard IBAN formats accepted by some processors
- **Duplicate transaction detection bypass**: Identical `<EndToEndId>` with different amounts
- **Clearing file manipulation**: Modifying Visa CTF / MC IPM batch records

### SWIFT MT Attack Surface
- **Field 50K/59 manipulation**: Originator/beneficiary name injection
- **Field 70 narrative injection**: Unstructured remittance info field
- **MT103 GPI tracking bypass**: Missing UETR field in GPI-enabled corridors
- **Settlement amount mismatch**: DE4 vs DE5 discrepancy exploitation

### QR Payment Attack Surface
- **QR substitution**: Replace merchant QR with attacker QR (physical/digital)
- **Amount manipulation**: Modify transaction amount in dynamic QR before scan
- **CRC bypass**: Many readers skip CRC validation — forge QR without valid CRC
- **Merchant ID spoofing**: Replace merchant account info tags (02-51)
- **Static QR with amount**: Lock amount to force overpayment

### Clearing & Settlement Attack Surface
- **Batch record injection**: Insert fraudulent records into CTF/IPM files
- **Settlement amount inflation**: Modify DE4/DE5 in clearing records
- **Duplicate submission**: Submit same batch file twice to different endpoints
- **Response code manipulation**: Change DE39 from decline to approval in clearing
- **Interchange fee manipulation**: Modify MCC to lower-fee category

## Surgical Fleet Integration

The Neopay module is surgically integrated into the bot fleet as follows:

| Bot | Neopay Integration |
|---|---|
| **RECON** | Uses `parse_iso8583.py` to fingerprint payment protocol on discovery |
| **INTEL** | Uses `transaction_flow.py` to map transaction flows and identify attack surface |
| **HUNTER** | Uses `iso8583_fuzzer.py`, `hsm_simulator.py`, `mac_calculator.py`, `pin_block.py` for active exploitation |
| **OPERATIONS** | Uses `clearing_settlement.py`, `iso20022_converter.py` for data extraction and exfiltration |

### Pipeline Stage Integration
| Stage | Neopay Script |
|---|---|
| Stage 1 (Recon) | `parse_iso8583.py` — protocol identification |
| Stage 2 (Enum) | `transaction_flow.py` — flow mapping |
| Stage 3 (Vuln Scan) | `iso8583_fuzzer.py` — field fuzzing |
| Stage 4 (Exploit) | `hsm_simulator.py`, `mac_calculator.py`, `pin_block.py` |
| Stage 5 (Post-Exploit) | `clearing_settlement.py`, `iso20022_converter.py` |
| Stage 6 (Evasion) | Timing profiles, proxy rotation applied to all Neopay connections |
| Stage 7 (Distributed) | Neopay scripts distributed across fleet nodes |

## Environment Variables
```bash
NEOPAY_WORKSPACE=/path/to/neopay          # Neopay module root
NEOPAY_HSM_KEY=<hex_key>                  # HSM master key for simulation
NEOPAY_CARD_RANGES=/path/card_ranges.json # BIN range database
NEOPAY_TEST_MODE=true                     # Use test card numbers only
OPENCLAW_TARGET=<target_host>             # Active target
```
