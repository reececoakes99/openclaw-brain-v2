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

## Safety

All techniques documented for authorized testing only.
Verify engagement_config.json before any payment system interaction.
