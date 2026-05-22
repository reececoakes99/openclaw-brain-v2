# Merchant Onboarding Workflow

## Overview

Merchant onboarding transforms a business into a live payment acceptance partner. This spans KYC/KYB verification, contract signing, risk classification, API provisioning, and integration testing.

## Stages

### Stage 1: Application & KYC

**Individual merchants (KYC):**
- Government-issued ID (passport, driver's license, national ID)
- Proof of address (utility bill < 90 days, bank statement)
- Date of birth, nationality
- Tax ID / SSN
- Bank account verification (micro-deposit or Plaid/Yodlee)

**Business merchants (KYB):**
- Certificate of incorporation / business registration
- Articles of association / partnership agreement
- EIN / VAT number / Tax ID
- Ultimate Beneficial Owner (UBO) declaration — any individual >25% ownership
- Directors/officers identification
- Registered business address proof

**Verification methods:**
- Manual review by compliance team
- Automated: Onfido, Jumio, Veriff, Sumsub
- Database checks: Sanctions (OFAC, EU, UN), PEP lists, adverse media
- Business verification: Dun & Bradstreet, Companies House, open data

### Stage 2: Risk Classification

**MCC (Merchant Category Code) assignment:**
- Based on primary business activity
- Determines interchange rate + fraud risk tier
- Examples: 5411 (Grocery), 5812 (Eating), 7011 (Hotels), 7995 (Gambling)
- High-risk MCCs require additional review: 5967 (Dating), 7994 (Gaming), 5122 (Pharma)

**Volume-based risk tiers:**
| Tier | Monthly Volume | Requirements |
|------|--------------|--------------|
| Starter | < $10K | Basic KYC, no rolling reserve |
| Growth | $10K - $100K | Enhanced KYB, 5% rolling reserve |
| Enterprise | > $100K | Full KYB, compliance review, dedicated support |

**Rolling reserve calculation:**
- Default: 5% of transaction volume
- High-risk MCC: 10%
- Rolling period: 90 days (returned after chargeback window closes)
- Separate merchant ledger: `reserve_held` vs `reserve_available`

### Stage 3: Contract & Pricing

**Fee schedule negotiation:**
- Interchange ++ model: Interchange + scheme fee + acquiring margin
- Effective rate: varies by card type, MCC, entry mode (CNP vs POS)
- Monthly minimum fee (e.g., $25/month if volume below threshold)
- Chargeback fee per dispute (e.g., $25/first, $15/subsequent)
- Refund fee (sometimes waived)

**Settlement terms:**
- Standard: T+2 (funds transferred 2 business days after transaction)
- Rolling reserve: withheld portion
- Payout schedule: daily / weekly / monthly (configurable)
- Currency: single currency or multi-currency with FX conversion

**Contract types:**
- Standard merchant agreement
- Enterprise agreement (negotiated rates, custom SLAs)
- Marketplace / platform agreement (split payments, escrow)

### Stage 4: API Key Provisioning

**Key generation:**
- API key: `pk_live_xxxxxxxxxx` (publishable) + `sk_live_xxxxxxxxxx` (secret)
- HMAC signing key for webhook signature verification
- OAuth2 client credentials (for server-to-server)

**Key rotation policy:**
- Automatic rotation every 90 days
- Manual rotation on security event
- Zero-downtime rotation: new key + old key active for 24h transition

**Scopes:**
- `payments:create` — initiate transactions
- `payments:read` — query transaction status
- `refunds:create` — process refunds
- `webhooks:manage` — configure webhook endpoints

### Stage 5: Webhook & Integration Configuration

**Webhook setup:**
- Endpoint URL (must be HTTPS, publicly reachable)
- Event subscriptions: payment.completed, payment.failed, refund.created, chargeback.created, fraud.blocked
- Secret for signature verification (HMAC-SHA256)
- Retry policy configuration

**Integration testing:**
- Test credentials (`pk_test_xxxx`) for sandbox environment
- ISO8583 message validation against test card numbers
- Webhook delivery test (synthetic event injection)
- End-to-end flow: auth → capture → settlement

**Testing scenarios:**
- Successful payment
- Decline (insufficient funds, card expired)
- 3D Secure authentication
- Refund (full and partial)
- Timeout simulation

### Stage 6: Go-Live

**Checklist:**
- [ ] KYC/KYB documents verified and approved
- [ ] Contract signed
- [ ] API keys provisioned and tested
- [ ] Webhook endpoint verified
- [ ] Rolling reserve configured
- [ ] Payout schedule set
- [ ] Fraud rules configured (merchant-specific overrides)
- [ ] Contact details for support and chargeback notification
- [ ] Sandbox testing complete

**Activation:**
- Move from test (`pk_test_*`) to live (`pk_live_*`)
- Rate limiting adjustments for expected volume
- Monitoring dashboard provisioned
- Dedicated support queue assigned (enterprise tier)

## Merchant Self-Service Portal

Provide a portal for merchants to:
- View dashboard (volume, revenue, chargebacks)
- Manage API keys
- Configure webhooks
- Download settlement reports
- Submit chargeback representments
- Update business details (re-verification triggers on material changes)

## Notes

- AML compliance: monitor transaction patterns for structuring (smurfing)
- Sanctioned countries: block transactions from OFAC/EU list
- High-risk merchants: require board approval, enhanced monitoring
- GDPR: ensure merchant data handled per privacy policy