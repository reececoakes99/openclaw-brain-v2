---
name: paybox
description: "Build and operate a full-stack payment gateway infrastructure. Covers: merchant onboarding, payment orchestration (card acquiring, SEPA/SWIFT bank transfer, open banking PISP/AISP), ISO8583 message switching, transaction routing, ledger/reconciliation, PCI DSS compliance, token vault, HSM integration, fraud detection, webhook management, and admin dashboarding. Trigger on anything involving building, operating, or red-teaming a payment processing system."
metadata: {"nanobot":{"emoji":"🏦"}}
---

# Paybox — Payment Gateway Infrastructure

Full-stack payment gateway: from merchant onboarding through settlement, fraud, and webhook delivery.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        MERCHANT LAYER                           │
│   Merchant Portal  │  Admin Dashboard  │  API Gateway (REST)    │
└────────────┬────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────┐
│                     ORCHESTRATION LAYER                        │
│  Authorization  │  Capture  │  Refund  │  Reversal  │  Routing   │
└────────┬─────────────┬──────────────┬──────────────┬────────────┘
         │            │              │              │
┌────────▼────┐ ┌──────▼──┐ ┌───────▼────┐ ┌────────▼────────────┐
│  ISO8583    │ │ SEPA /  │ │  Token     │ │  Fraud Detection     │
│  Switch    │ │  SWIFT  │ │  Vault     │ │  Engine              │
└────────────┘ └─────────┘ └────────────┘ └───────────────────────┘
         │            │              │              │
┌────────▼────────────▼──────────────▼──────────────▼────────────┐
│                     MESSAGING & SECURITY                       │
│  RabbitMQ / Kafka / IBM MQ  │  HSM (PayShield/CloudHSM)         │
│  Redis Queue  │  Message Routing  │  Key Management             │
└───────────────┬───────────────────┬────────────────────────────┘
                │                   │
┌───────────────▼───────────────────▼──────────────────────────────┐
│                     DATA LAYER                                  │
│  PostgreSQL (Ledger/Transactions)  │  Oracle/DB2 (Settlement)   │
│  NoSQL (Config/Keys)  │  Redis (Cache/Queue)                    │
└─────────────────────────────────────────────────────────────────┘
                │
┌───────────────▼────────────────────────────────────────────────┐
│                     CONNECTOR LAYER                             │
│  Scheme Interface  │  Acquiring Bank  │  Cloud Messaging        │
│  SIEM Integration  │  Threat Intel Feed                         │
└─────────────────────────────────────────────────────────────────┘
```

## Core Workflows

### Authorization (Card)
1. Merchant API → parse ISO8583 message (MTI 0100)
2. Tokenize PAN → check token vault
3. Fraud screening (velocity, geo, ML score)
4. HSM: verify ARQC (if Chip+PIN), generate ARPC
5. Scheme routing → Visa/MC/Amex/etc.
6. Response (0110) → merchant + update ledger

### Capture
1. Merchant request (0200) → link to auth
2. Validate: auth not captured, amount ≤ auth amount
3. Clearing preparation → settle batch

### Settlement (T+1/T+2)
1. Aggregate transactions into clearing file
2. Generate ISO20022 camt.054 / SWIFT MT940
3. Send to acquiring bank / scheme

## Directory Structure

```
paybox/
├── SKILL.md
├── references/
│   ├── architecture.md         # System architecture
│   ├── iso8583.md              # Card message switching
│   ├── sepa.md                 # SEPA payment types
│   ├── swift.md                # SWIFT messaging
│   ├── ledger.md               # Double-entry bookkeeping
│   ├── merchant_onboarding.md  # KYC/KYB workflow
│   ├── webhook_management.md   # Webhook delivery
│   ├── fraud_detection.md      # Fraud rules & ML
│   └── token_vault.md         # PAN tokenization
├── assets/
│   ├── terraform/             # GCP + AWS IaC
│   ├── monitoring/             # Prometheus + Grafana
│   ├── cicd/                  # GitLab CI/CD
│   └── test_data/             # Cards, merchants, webhooks
└── connectors/                # Scheme/adapter connectors
```

## Setup

### Prerequisites
- Java 17+ (JDK for message engine)
- Docker + Kubernetes
- Message Broker: RabbitMQ, Kafka, or IBM MQ
- Database: PostgreSQL 15+ (ledger), optionally Oracle/DB2
- HSM: Thales PayShield or AWS CloudHSM
- Redis 7+ (queue + cache)

### Configuration
```yaml
# Environment variables
PAYBOX_ENV=production
PAYBOX_DB_URL=jdbc:postgresql://localhost:5432/paybox
PAYBOX_REDIS_URL=redis://localhost:6379
PAYBOX_HSM_HOST=thales-payshield:9999
PAYBOX_MESSAGING=rabbitmq
PAYBOX_MQ_URL=amqp://localhost:5672
PAYBOX_FRAUD_THRESHOLD=0.85
PAYBOX_TOKEN_VAULT_KEY_REF=KEK.MASTER.01
```

## Security

- **PCI DSS Level 1** compliance required
- HSM: all cryptographic operations (PIN, MAC, ARQC/ARPC, key management)
- Token vault: AES-256-GCM, KEK/Dek hierarchy
- TLS 1.2+ enforced on all endpoints
- Network: mTLS between internal services
- Secrets: HashiCorp Vault or cloud secret manager
- Audit: every transaction logged, immutable

## Monitoring

See `references/architecture.md` for SLI/SLO:
- Availability: 99.95%
- Latency p99: < 2s
- Error rate: < 0.5%
- Fraud catch rate: > 85%

Prometheus metrics:
- `paybox_authorizations_total{status,network}`
- `paybox_capture_total{status}`
- `paybox_fraud_score{source}`
- `paybox_webhook_delivery_rate`
- `paybox_token_operations_total{op}`
- `paybox_ledger_reconciliation_gaps`

## Red Team

For offensive security testing, see the `protocol-engineering` skill
for: ISO8583 fuzzing, HSM attack surface, MITM proxy setup, crypto
downgrade testing, red team configuration.

## Dependencies

- Java 17+
- Docker 24+
- Kubernetes 1.28+
- Maven 3.9+
- PostgreSQL 15+
- Redis 7+
- RabbitMQ 3.12+ / Kafka 3.6+ / IBM MQ 9.3+

## Notes

- Network tokens (Visa Token Service, Mastercard Tokenization) preferenced over vault tokens for card-on-file
- 3D Secure 2.x mandatory for EU payments under PSD2
- Rolling reserve: 5-10% for high-risk merchants, held 90-180 days
- Webhook retry: exponential backoff, dead letter after 5 attempts
- PCI DSS scan required quarterly by approved vendor