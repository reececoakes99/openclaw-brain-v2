---
name: payment-gateway
description: End-to-end payment gateway infrastructure — ISO8583 switching, HSM key management, SEPA/PSD2 open banking, PCI DSS compliance, Java message engine, Kubernetes orchestration, RabbitMQ/IBM MQ messaging, token vault, fraud detection, and red-team security testing. Trigger on anything involving building, operating, or red-teaming payment switch infrastructure.
---

# Neopay Payment Gateway — Full Infrastructure

Enterprise-grade payment switch replicating Neopay's architecture: Java message engine, ISO8583/SPDH/HPDH switching, HSM cryptography, SEPA/PSD2 open banking, PCI DSS L1 compliance, Kubernetes deployment, and offensive security testing.

## When to Trigger

- "Build payment switch", "ISO8583 message handling", "HSM integration"
- "SEPA/PSD2 open banking", "PISP/AISP flows", "payment initiation"
- "PCI DSS compliance", "token vault", "PIN block processing"
- "Payment gateway red-team", "fraud detection", "card data security"
- "Kubernetes payment infra", "message queue architecture", "settlement"
- "EMV crypto", "ARQC/ARPC", "key ceremony"

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        EXTERNAL CONNECTIONS                          │
│  POS Terminals │ Card Networks │ Banks │ Open Banking │ Merchants  │
└───────┬─────────┬───────┬───────────┬───────────┬────────┬──────────┘
        │         │       │           │           │        │
   ISO8583   ISO8583  ISO20022   PSD2 API   REST API  REST API
   (ASCII/   (Binary)  MX        PISP/AISP  Payments  Webhooks
    Binary)                                                   │
        ▼         ▼       ▼           ▼           ▼        │
┌─────────────────────────────────────────────────────────────────┐
│                   JAVA MESSAGE ENGINE (Core Switch)              │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐         │
│  │ Parser   │ │ Router   │ │ Security  │ │ Workflow │         │
│  │ ISO8583  │ │ Config   │ │ (MAC/PIN) │ │ Orchestr. │         │
│  │ MX/HPDH  │ │ Rule Eng │ │ Timeout   │ │ Retry     │         │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘         │
│       └────────────┼───────────┼────────────┘                │
│                    ▼           ▼                               │
│           ┌────────────┐  ┌────────────┐                     │
│           │    HSM     │  │ Token Vault │                     │
│           │ (Thales    │  │ (AES-256    │                     │
│           │ CloudHSM)  │  │  Vault)     │                     │
│           └────────────┘  └────────────┘                     │
└─────────────────────────────────────────────────────────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
  │  RabbitMQ   │    │ PostgreSQL  │    │   Redis     │
  │  (Async     │    │  (Ledger,   │    │  (Cache,     │
  │   Tasks)    │    │   Config)   │    │   Sessions) │
  └─────────────┘    └─────────────┘    └─────────────┘
         │
         ▼
  ┌─────────────────────────────────────────────┐
  │         KUBERNETES ORCHESTRATION             │
  │  Gateway │ Switch │ HSM │ Vault │ API │ UI   │
  └─────────────────────────────────────────────┘
```

## Protocol Stack

| Layer | Protocol | Format |
|-------|----------|--------|
| **Card Acquiring** | ISO8583:1987/1993/2003 | ASCII or Binary |
| **POS Terminal** | SPDH, HPDH, Verifone | ASCII |
| **Open Banking** | ISO20022 MX (pacs.008, pain.001) | XML |
| **Legacy SWIFT** | SWIFT MT (ISO15022) | FIN |
| **POS Entry** | EMV CROSSLINK, Ingenico, Verifone | TLV |
| **Messaging** | RabbitMQ, IBM MQ, ActiveMQ | AMQP/JMS |
| **API** | REST JSON | HTTPS |
| **Webhook** | POST JSON | HTTPS |

## Core Workflow

```
1. RECEIVE  → Terminal/Card Network/API → TCP socket or REST
2. PARSE    → ISO8583 (ASCII/Binary) or MX message → Internal DTO
3. VALIDATE → Field format, bitmap, MAC, DE length
4. SECURITY → HSM: ARQC verify, PIN translate, MAC compute
5. ROUTE    → Rule engine (BIN range, amount, country) → Processor
6. ENCRYPT  → PAN tokenization via vault (AES-256-GCM)
7. QUEUE    → RabbitMQ task (async processing, retries)
8. CONNECT  → Acquirer/processor via ISO8583 or ISO20022
9. RESPOND  → Authorize/Decline/Retry → Terminal/Card Network
10. STORE   → Ledger entry, transaction log, settlement batch
```

## Service Catalog

| Service | Language | Purpose |
|---------|----------|---------|
| **message-engine** | Java 17 | Core ISO8583 switch, routing, business logic |
| **hsmm-service** | Java | HSM operations: PIN, MAC, KEK, key translation |
| **vault-service** | Java | Tokenization, PAN encryption, key management |
| **psd2-gateway** | Java | PISP/AISP open banking flows, OAuth2 |
| **rest-api** | Java/Spring | External REST API (payments, links, webhooks) |
| **admin-ui** | React/Node | Operations dashboard, monitoring, key ceremony |
| **settlement** | Python | Batch processing, clearing, reconciliation |
| **fraud-engine** | Python/Go | Real-time scoring, velocity rules, ML |
| **messaging** | Java | RabbitMQ/IBM MQ consumer/producer |
| **connector-spdh** | Java | SPDH/HPDH terminal protocol handler |
| **connector-swift** | Java | SWIFT MT message handling |
| **reporting** | Python | Batch reports, regulatory, analytics |

## Workflow: ISO8583 Message Flow

```
INBOUND (ASCII 0100 Authorization Request)
  │
  ├─ bitmap.parse(DE001-128)
  ├─ field.validate(DE002-DE128)
  │   DE003 (PAN) → Luhn check
  │   DE004 (Amount) → range validation
  │   DE014 (Expiry) → format + future check
  │   DE035 (Track2) → decrypt if encrypted
  │   DE055 (EMV Data) → tag parse
  │   DE064 (MAC) → HSM verify
  │
  ├─ hsm.verify_arqc(DE55)    ← ARQC from chip card
  ├─ vault.tokenize(DE002)     ← PAN → token
  ├─ routing.rule_lookup()    ← BIN → acquirer route
  │
  ├─ queue.submit(routing_key)  ← RabbitMQ
  │
  ├─ processor.send(ISO8583)  ← Acquirer connection
  │
  └─ RESPONSE
       ├─ approve → ISO8583 0110 + RabbitMQ event
       ├─ decline → ISO8583 0110
       └─ retry → schedule requeue

OUTBOUND (ISO20022 pacs.008 SEPA Credit Transfer)
  ├─ MX builder (pacs.008)
  ├─ KEK encrypt (HSM)
  └─ send to ASPSP via PSD2 gateway
```

## Security Architecture

```
PCI DSS Scope Boundary:
┌────────────────────────────────────────────────────────┐
│ IN SCOPE                                                │
│  ├── message-engine (PAN processing)                   │
│  ├── vault-service (card data storage)                 │
│  ├── hsm-service (key management)                     │
│  ├── rest-api (card data transit)                      │
│  └── connector-spdh (terminal encryption)             │
│                                                        │
│ OUT OF SCOPE (cannot touch PAN/card data)              │
│  ├── admin-ui, reporting, fraud-engine, settlement     │
│  └── infrastructure (K8s, monitoring, logs)          │
└────────────────────────────────────────────────────────┘

Key Hierarchy (HSM-protected):
  LMK (Local Master Key)       ← HSM generated, never exports
  ├── TMK (Terminal Master Key)    → per-POS terminal
  ├── ZMK (Zone Master Key)        → per-acquirer
  ├── KEK (Key Encrypting Key)    → session key encryption
  └── DUK (Data Unpacking Key)    → field-level encryption

PIN Block Operations (ISO 9564):
  - ISO9564-1 Format 0:  PIN ⊕ PAN
  - ISO9564-1 Format 1:  PIN ⊕ Random
  - Translation: Format 0 → Format 4 (IBM HSM) via KEK
  - ARQC/ARPC: Visa CAP / MasterCard SCP via HSM
```

## References

| File | Scope |
|------|-------|
| `references/iso8583.md` | DE fields 1-128, MTI, bitmap, SPDH, HPDH, test vectors |
| `references/hsm.md` | Thales Luna/CloudHSM, key ceremony, PIN/MAC/ARQC operations |
| `references/sepa_psd2.md` | PSD2 flows, AISP/PISP, ISO20022 MX, Berlin Group NGIPS |
| `references/pci_dss.md` | Scoping, requirements 1-12, tokenization, SAQ/DSS |
| `references/database.md` | PostgreSQL schema: transactions, ledger, keys, terminals |
| `references/messaging.md` | RabbitMQ/IBM MQ topology, queues, consumer groups |
| `references/kubernetes.md` | K8s manifests, Helm charts, autoscaling, network policies |
| `references/fraud_detection.md` | Rules engine, velocity, ML scoring, alerts |
| `references/settlement.md` | Batch processing, clearing, reconciliation |
| `references/test_cases.md` | ISO8583 fuzzing, replay, field overflow, API security |

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/gen_iso8583.py` | Generate valid ISO8583 messages for testing |
| `scripts/validate_fields.py` | Field format validation against spec |
| `scripts/parse_message.py` | Parse raw ISO8583 hex/ASCII into structured dict |
| `scripts/hsm_client.py` | HSM operations: encrypt, decrypt, MAC, PIN translate |
| `scripts/load_test.py` | k6/Locust load testing (1500 TPS target) |
| `scripts/iso_fuzz.py` | Fuzzing: bitmap flip, field overflow, MTI fuzz |
| `scripts/migrate_keys.py` | LMK/TMK migration scripts |
| `scripts/hex_to_iso.py` | Binary-to-ASCII ISO8583 converter |

## Assets

| File | Purpose |
|------|---------|
| `assets/sample_messages/` | Test ISO8583 (ASCII/Binary), SEPA MX, EMV data |
| `assets/conn_configs/` | Per-acquirer ISO8583 connection configs (XML/YAML) |
| `assets/field_maps/` | Variable-length field parsers for DE001-DE128 |
| `assets/ssl/` | mTLS certificates (test CA + server/client certs) |
| `assets/k8s/` | Helm charts, deployment YAMLs, network policies |
| `assets/postman/` | Full API collection (Payments, Links, Customers, Webhooks) |