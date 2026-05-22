---
name: protocol-engineering
description: Financial protocol engineering for payment switch infrastructure. Covers ISO8583 (HISO93, HISO87, binary/ASCII dialects), ISO20022 MX, SWIFT MT (ISO15022), POS protocols (SPDH, HPDH, Verifone XFlow), HSM cryptography (PIN block ISO9564, MAC ISO9797-1, ARQC/ARPC), Thales PayShield/CloudHSM integration, Java message engine, Kubernetes deployment, RabbitMQ/Kafka/IBM MQ messaging, PCI-DSS/FIPS140-2 compliance, scheme certification (Visa/MC/Amex), performance testing to 1500 TPS, and full offensive security red-teaming with 110 items across skills/tools/bots. Trigger on anything involving payment protocol parsing, HSM integration, scheme connectivity, terminal integration, message switching, payment switch architecture, or payment security testing.
---

# Protocol Engineering

Deep expertise in financial protocol switching, HSM cryptography, POS terminal integration, and payment switch architecture — mirroring Neopay's core engine and red-team security testing framework.

## When to Trigger

**Protocols & Parsing:**
- "Parse ISO8583 message", "HISO93 binary format", "variable-length fields"
- "SWIFT MT message handling", "ISO15022 syntax", "MX message conversion"
- "SPDH/HPDH terminal messages", "Verifone protocol", "POS message decode"

**Core Engine:**
- "Java message engine", "authorization host", "switch router"
- "business logic orchestration", "runtime administration", "terminal applet scripting"

**HSM & Cryptography:**
- "HSM key management", "LMK/ZMK/TMK operations", "Thales PayShield integration"
- "PIN block translation (ISO9564)", "MAC generation/verification", "ARQC/ARPC validation"
- "EMV cryptography", "key ceremony", "CloudHSM (AWS/GCP)"

**Infrastructure:**
- "Kubernetes payment switch", "Docker containerization"
- "RabbitMQ/Kafka/IBM MQ message routing", "SQS/Pub-Sub integration"
- "Oracle/DB2/NoSQL database administration", "AWS/GCP/Azure architecture"

**Connectors:**
- "Scheme interface (Visa/MC/Amex/UnionPay/JCB)", "acquiring connectors"
- "POS/ATM terminal integration", "clearing settlement connectors"
- "SIEM integration (Splunk/ELK)", "threat intel feeds"

**Testing & Security:**
- "Performance testing 1500 TPS", "API fuzzing", "regression automation"
- "Red-team payment switch", "cryptographic downgrade attacks", "SQL/XXE injection"
- "PCI-DSS compliance", "FIPS140-2 standards", "honeypot design"
- "ISO8583 fuzzer", "replay attack", "MITM proxy", "echo server"

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    EXTERNAL CONNECTIVITY                                     │
│  Card Schemes  │  POS/ATM   │  Open Banking  │  Merchants  │  Clearing     │
│  Visa/MC/Amex  │  Terminals │  PSD2/PISP     │  REST API   │  Settlement   │
└─────┬──────────┬────┬───────┬────┬───────────┬────┬─────────┬────┬─────────┘
      │          │    │       │    │           │    │         │    │
  ISO8583    SPDH/HPDH   MX    HTTPS    ISO15022  Custom
  (HISO93)   Verifone    ISO20022   JSON   SWIFT MT   Protocols
      ▼          ▼        ▼         ▼        ▼           ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                   JAVA MESSAGE ENGINE (Core Switch)                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │  Parser      │  │  Router      │  │  Security    │  │  Workflow    │   │
│  │  ISO8583     │  │  Config      │  │  MAC/PIN/HSM │  │  Orchestrator│   │
│  │  MX/HPDH     │  │  Rule Engine │  │  Timeout     │  │  Retry/Queue │   │
│  │  SWIFT MT    │  │  Connector   │  │  Key Mgmt    │  │  Simulator   │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         └─────────────────┼─────────────────┼──────────────────┘          │
│                           ▼                                                  │
│                 ┌─────────────────┐    ┌─────────────────┐               │
│                 │   HSM Cluster   │    │   Token Vault   │               │
│                 │  (Thales/GCP    │    │   (AES-256      │               │
│                 │   CloudHSM)     │    │    Encryption)  │               │
│                 └─────────────────┘    └─────────────────┘               │
└─────────────────────────────────────────────────────────────────────────────┘
      │                │                    │                    │
      ▼                ▼                    ▼                    ▼
┌────────────┐  ┌────────────┐    ┌────────────┐    ┌────────────┐
│  Kafka /   │  │ PostgreSQL │    │   Redis    │    │   Oracle   │
│  RabbitMQ  │  │  / DB2     │    │  (Cache/   │    │  / MongoDB │
│  IBM MQ    │  │  Ledger    │    │  Rate Limit│    │  Ledger    │
└────────────┘  └────────────┘    └────────────┘    └────────────┘
```

## Core Capabilities

1. **ISO8583 Message Processing** — HISO93/HISO87 binary & ASCII parsing, 128-field dictionary, variable-length fields, bitmap handling, MTI routing
2. **ISO20022 MX Messaging** — pain.001/002/003, pacs.008, camt.053, SWIFT MT↔MX conversion, SEPA-specific rules
3. **POS Protocol Support** — SPDH, HPDH, Verifone XFlow, terminal key download, EMV L2 kernel basics
4. **HSM Operations** — Thales PayShield command suite, PIN block ISO9564, MAC ISO9797-1, ARQC/ARPC, key hierarchy (LMK/ZMK/TMK), CloudHSM integration
5. **Connectors** — 12 connector types covering all external system integrations
6. **Java Message Engine** — Neopay Suite modules, authorization host, switch router, runtime admin
7. **Infrastructure** — Kubernetes, Docker, Terraform (AWS/GCP), Helm, CI/CD pipelines
8. **Security Testing** — 65 skills, 27 tools, 18 bots for full red-team coverage

## Red Team Testing Framework

See `references/red_team.md` for complete coverage of:
- **65 Skills** across 8 categories (Protocol Converters, Infrastructure, Web Testing, Payment Gateway API, Authentication, Tokenization, PCI DSS, OSINT)
- **27 Tools** across 5 categories (OSINT, Web Security, Network & Protocol, Payment-Specific/Crypto, Forensics)
- **18 Bots** across 4 categories (Monitoring, Automated Attack, Intelligence, Reporting)
- **Attack tools A1-A5**: Grammatical ISO8583 mutator, replay engine, crypto downgrade tester, boundary value exploiter, protocol fuzzer

## Protocol Parsing Reference

See `references/iso8583.md` — full field map for HISO93, binary/ASCII variants, variable-length field parsing, MTI routing.
See `references/iso20022.md` — MX message structure (pain.001/002/003, camt.053, pacs.008), SWIFT MT to MX conversion.
See `references/pos_protocols.md` — SPDH/HPDH message formats, Verifone XFlow, terminal configuration scripts.

## HSM & Cryptography Reference

See `references/hsm.md` — Thales PayShield commands, PIN block formats (ISO9564 format 0/1/2/3), MAC algorithms (ISO9797-1 M1/M2/M3), ARQC/ARPC (EMV CP), key hierarchy (LMK/ZMK/TMK/KEK).

## Connectors Reference

See `references/connectors.md` — all 12 connector types, protocols, target systems, configuration templates.

## Software Stack Reference

See `references/software_stack.md` — Neopay Suite modules, Java runtime requirements, Docker/K8s configs, CI/CD pipeline design, testing tools.

## Compliance Reference

See `references/compliance.md` — PCI-DSS v4.0, FIPS140-2, scheme certification (Visa TAP, MC SPR, Amex), EMVCo type approval, honeypot design, red-team scope.

---

**Resources:**

| Directory | Contents |
|-----------|----------|
| `scripts/` | 12 scripts: ISO8583 parser, PIN block, MAC generator, fuzzer, HSM simulator, transaction flow orchestrator, load tester (1500 TPS), echo server, MITM proxy, stress tester, fingerprinter, PCAP tools, replay engine, crypto downgrade tester, monitoring bot |
| `references/` | iso8583, iso20022, pos_protocols, hsm, connectors, software_stack, compliance, red_team |
| `assets/` | Dockerfile, docker-compose, K8s manifests (7 files), Helm chart, Terraform (AWS + GCP), Postman collection, test data generators, fuzzing corpus, CI/CD pipeline, monitoring rules & dashboards, HSM config, red team config, selector maps |