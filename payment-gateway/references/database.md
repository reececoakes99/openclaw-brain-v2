# PostgreSQL Database Schema

## Schema Design Principles

- **Write-heavy optimized**: High-volume transaction inserts (2000+ TPS)
- **Append-only ledger**: No updates on transaction records (immutable audit)
- **Logical separation**: Transactions in one DB, vault/keys in another (network-segmented)
- **Partitioning**: By date for transactions table (hot data) vs. static data
- **Row-level security**: Enforced at DB level for multi-tenant access

## Schema: Transactions & Ledger

```sql
-- ============================================================
-- CORE TABLES
-- ============================================================

-- Payments: Master transaction record (append-only)
CREATE TABLE payments (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Identifiers
    reference       VARCHAR(40) NOT NULL UNIQUE,  -- E2E ID (our ref)
    psp_reference   VARCHAR(40),                   -- PSP's transaction ID
    merchant_id     UUID NOT NULL REFERENCES merchants(id),
    
    -- Amount & Currency
    amount          NUMERIC(15, 2) NOT NULL,
    currency        CHAR(3) NOT NULL,  -- ISO 4217
    settlement_currency CHAR(3),         -- If different (FX)
    settlement_rate  NUMERIC(15, 8),    -- FX rate applied
    
    -- Type & Status
    payment_type    payment_type_enum NOT NULL,  -- sale, auth, capture, refund, reversal
    status          payment_status_enum NOT NULL DEFAULT 'pending',
    
    -- Card / Token data (no PAN stored here — only vault token)
    vault_token     VARCHAR(64),  -- Tokenized PAN reference
    card_last4      CHAR(4),
    card_type       VARCHAR(10),  -- visa, mc, amex
    card_country    CHAR(2),      -- Issuing country (from BIN)
    
    -- ISO8583 DE fields stored as JSONB
    iso_fields      JSONB,  -- Key DE values for dispute resolution
    
    -- Routing
    acquirer_id     UUID REFERENCES acquirers(id),
    routing_rule_id UUID REFERENCES routing_rules(id),
    psp_id          UUID REFERENCES psps(id),
    
    -- Authorization
    auth_code       VARCHAR(12),
    response_code   VARCHAR(6),
    cvv_result      VARCHAR(4),
    avs_result      VARCHAR(4),
    three_ds_status VARCHAR(20),  -- authenticated, failed, attempted, not_enrolled
    
    -- Fees & Settlement
    interchange_fee NUMERIC(10, 4),
    scheme_fee      NUMERIC(10, 4),
    our_fee         NUMERIC(10, 4),
    net_amount      NUMERIC(15, 2),  -- amount - total fees
    settlement_batch UUID REFERENCES settlement_batches(id),
    
    -- Refunds/Parent link
    parent_payment_id UUID REFERENCES payments(id),
    is_full_refund   BOOLEAN DEFAULT FALSE,
    
    -- Timestamps
    created_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    authorized_at   TIMESTAMPTZ,
    captured_at     TIMESTAMPTZ,
    settled_at      TIMESTAMPTZ,
    failed_at       TIMESTAMPTZ,
    
    -- Webhook
    webhook_url     VARCHAR(512),
    webhook_sent_at TIMESTAMPTZ,
    webhook_retry_count INT DEFAULT 0,
    
    -- Risk
    risk_score      DECIMAL(5,2),  -- 0.00 - 100.00
    risk_rules_hit  JSONB,
    risk_decision   VARCHAR(20),  -- accept, challenge, decline
    
    -- Metadata
    metadata        JSONB,
    ip_address      INET,
    user_agent      TEXT,
    
    CONSTRAINT positive_amount CHECK (amount > 0)
);

-- Partition by month for performance
CREATE TABLE payments_2024_05 (LIKE payments INCLUDING ALL);
ALTER TABLE payments ATTACH PARTITION payments_2024_05 FOR VALUES FROM ('2024-05-01') TO ('2024-06-01');
-- Add more partitions per month...

-- Indexes
CREATE INDEX idx_payments_merchant_id ON payments(merchant_id);
CREATE INDEX idx_payments_status ON payments(status) WHERE status NOT IN ('settled','failed');
CREATE INDEX idx_payments_created_at ON payments(created_at DESC);
CREATE INDEX idx_payments_reference ON payments(reference);
CREATE INDEX idx_payments_psp_reference ON payments(psp_reference) WHERE psp_reference IS NOT NULL;
CREATE INDEX idx_payments_settlement ON payments(settlement_batch) WHERE settlement_batch IS NOT NULL;
CREATE INDEX idx_payments_risk ON payments(risk_decision, risk_score) WHERE risk_decision = 'challenge';

COMMENT ON TABLE payments IS 'Immutable payment transaction ledger';
```

## Vault Schema

```sql
-- ============================================================
-- VAULT (Separate DB — PCI Scope)
-- ============================================================

-- PAN Token Vault (separate PostgreSQL instance, network-isolated)
CREATE TABLE card_tokens (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token           VARCHAR(64) NOT NULL UNIQUE,  -- Our token
    pan_hash        VARCHAR(64) NOT NULL UNIQUE, -- SHA-256 of PAN (for lookup)
    pan_last4       CHAR(4) NOT NULL,
    
    -- PAN is encrypted via application-level AES-256-GCM before storage
    -- Key stored in HSM; decrypt only in HSM service
    pan_encrypted   TEXT NOT NULL,
    pan_aad         TEXT,  -- Additional Authenticated Data
    
    -- Card metadata (not sensitive)
    expiry_month    SMALLINT,
    expiry_year     SMALLINT,
    cardholder_name VARCHAR(100),
    card_type       VARCHAR(10),  -- visa, mc, amex, unionpay, etc.
    country         CHAR(2),
    
    -- Tokenization metadata
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      VARCHAR(64),  -- User/service that tokenized
    expires_at      TIMESTAMPTZ,  -- Token expiry (usually linked to card expiry)
    is_expired      BOOLEAN DEFAULT FALSE,
    
    -- Cryptographic version (for key rotation)
    crypto_version  INT DEFAULT 1
);

CREATE INDEX idx_card_tokens_pan_hash ON card_tokens(pan_hash);
CREATE INDEX idx_card_tokens_token ON card_tokens(token);

-- Token-to-merchant mapping (deterministic token per merchant)
CREATE TABLE merchant_token_map (
    merchant_id  UUID REFERENCES merchants(id),
    token        VARCHAR(64) REFERENCES card_tokens(token),
    merchant_token VARCHAR(64) NOT NULL UNIQUE,  -- Deterministic per-merchant token
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (merchant_id, token)
);

-- PIN block storage (encrypted, HSM-backed)
CREATE TABLE pin_blocks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_id        UUID REFERENCES card_tokens(id),
    
    -- PIN block encrypted under TMK (per terminal)
    pin_block_encrypted TEXT NOT NULL,
    pin_block_key_id    VARCHAR(64),
    
    -- PIN verification value (PVV) for card verification
    pvv_encrypted   TEXT,
    
    -- Translation to ZPK (acquirer-specific PIN block)
    zpk_pin_block_encrypted TEXT,
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    terminal_id     VARCHAR(16)
);
```

## Merchants & Onboarding

```sql
-- ============================================================
-- MERCHANT MANAGEMENT
-- ============================================================

CREATE TABLE merchants (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    merchant_id     VARCHAR(20) NOT NULL UNIQUE,  -- MID
    legal_name      VARCHAR(200) NOT NULL,
    trading_name    VARCHAR(200),
    
    -- Contact
    email           VARCHAR(255) NOT NULL,
    phone           VARCHAR(20),
    
    -- Address
    address_line1   VARCHAR(200),
    city            VARCHAR(100),
    state           VARCHAR(100),
    country         CHAR(2) NOT NULL,
    postal_code     VARCHAR(20),
    
    -- Business details
    mcc             VARCHAR(4) NOT NULL,  -- Merchant Category Code
    tax_id          VARCHAR(50),
    website_url     VARCHAR(255),
    
    -- Onboarding
    onboarding_status onboarding_status_enum DEFAULT 'pending',
    kyc_completed   BOOLEAN DEFAULT FALSE,
    risk_rating     VARCHAR(20),  -- low, medium, high
    
    -- Processing limits
    daily_limit     NUMERIC(15,2),
    monthly_limit   NUMERIC(15,2),
    per_transaction_limit NUMERIC(15,2),
    
    -- Integration
    webhook_url     VARCHAR(512),
    webhook_secret  VARCHAR(128),  -- HMAC key for webhook signing
    api_key_hash    VARCHAR(64),
    
    -- Fees (per merchant pricing)
    pricing_plan_id UUID REFERENCES pricing_plans(id),
    rolling_reserve_pct DECIMAL(5,2) DEFAULT 0,  -- Rolling reserve %
    rolling_reserve_days INT DEFAULT 30,
    
    -- Status
    is_active       BOOLEAN DEFAULT TRUE,
    suspended_reason TEXT,
    
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

-- PSP / Acquirer / Open Banking Configurations
CREATE TABLE acquirers (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    code            VARCHAR(20) NOT NULL UNIQUE,  -- e.g., 'ADYEN', 'WORLDPAY'
    
    -- Connection
    connection_type connection_type_enum,  -- iso8583, rest, open_banking
    host            VARCHAR(255),
    port            INT,
    timeout_ms      INT DEFAULT 30000,
    
    -- Credentials (encrypted)
    credentials_encrypted TEXT,  -- AES-256-GCM encrypted JSON
    
    -- Routing
    supported_card_types VARCHAR(50)[],
    supported_currencies CHAR(3)[],
    countries       CHAR(2)[],
    
    -- Rate limits
    max_tps         INT DEFAULT 100,
    daily_limit     NUMERIC(15,2),
    
    is_active       BOOLEAN DEFAULT TRUE,
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Routing Rules Engine
CREATE TABLE routing_rules (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            VARCHAR(100) NOT NULL,
    priority        INT NOT NULL DEFAULT 100,  -- Lower = higher priority
    
    -- Conditions (all must match)
    card_type       VARCHAR(10)[],  -- NULL = any
    currency        CHAR(3)[],
    amount_min      NUMERIC(15,2),
    amount_max      NUMERIC(15,2),
    country         CHAR(2)[],
    merchant_mcc    VARCHAR(4)[],
    time_start      TIME,
    time_end        TIME,
    day_of_week     SMALLINT[],  -- 0=Mon, 6=Sun
    
    -- Fallback rule
    is_fallback     BOOLEAN DEFAULT FALSE,
    
    -- Action: route to acquirer/PSP
    acquirer_id     UUID REFERENCES acquirers(id),
    psp_id          UUID REFERENCES psps(id),
    
    -- Cost-based routing
    estimated_cost_pct NUMERIC(6,4),
    
    is_active       BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## Terminals & Keys

```sql
-- ============================================================
-- TERMINAL & KEY MANAGEMENT
-- ============================================================

CREATE TABLE terminals (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    terminal_id     VARCHAR(16) NOT NULL UNIQUE,  -- TID
    merchant_id     UUID REFERENCES merchants(id),
    
    -- Terminal info
    serial_number   VARCHAR(50),
    model           VARCHAR(50),
    manufacturer    VARCHAR(50),
    firmware_version VARCHAR(50),
    
    -- Connection
    ip_address      INET,
    port            INT,
    protocol        VARCHAR(20),  -- SPDH, HPDH, TCP
    comm_type       VARCHAR(20),  -- GPRS, Ethernet, WiFi
    
    -- Keys (encrypted, reference only)
    tmk_id          UUID REFERENCES hsm_keys(id),
    tpk_id          UUID REFERENCES hsm_keys(id),
    tak_id          UUID REFERENCES hsm_keys(id),
    
    -- Key status
    keys_injected   BOOLEAN DEFAULT FALSE,
    last_key_change TIMESTAMPTZ,
    key_expiry      TIMESTAMPTZ,
    
    -- Operational
    is_active       BOOLEAN DEFAULT TRUE,
    is_online       BOOLEAN DEFAULT TRUE,
    last_seen_at    TIMESTAMPTZ,
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- HSM Key Registry
CREATE TABLE hsm_keys (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key_id          VARCHAR(64) NOT NULL UNIQUE,  -- Internal key ID
    key_type        VARCHAR(20) NOT NULL,  -- TMK, TPK, ZMK, KEK, LMK
    key_version     INT DEFAULT 1,
    
    -- Key encrypted under LMK (never stored in plaintext)
    encrypted_key   TEXT NOT NULL,
    
    -- Key fingerprint (for verification)
    fingerprint     VARCHAR(64) NOT NULL,  -- SHA-256 of key bytes
    
    -- Ownership
    acquirer_id     UUID REFERENCES acquirers(id),
    terminal_id     UUID REFERENCES terminals(id),
    
    -- Status
    is_active       BOOLEAN DEFAULT TRUE,
    is_expired      BOOLEAN DEFAULT FALSE,
    expiry_at       TIMESTAMPTZ,
    
    -- Audit
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    created_by      VARCHAR(64),
    rotated_at      TIMESTAMPTZ,
    rotated_by      VARCHAR(64)
);

-- Key ceremony audit log
CREATE TABLE key_ceremony_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ceremony_type   VARCHAR(30) NOT NULL,  -- LMK_LOAD, TMK_INJECT, ZMK_ROTATE
    key_id          UUID REFERENCES hsm_keys(id),
    
    -- Custodians present (quorum)
    custodians      VARCHAR(64)[],
    
    -- Before/after fingerprints
    old_fingerprint VARCHAR(64),
    new_fingerprint VARCHAR(64),
    
    -- Outcome
    success         BOOLEAN NOT NULL,
    error_message   TEXT,
    
    -- Signatures
    custodian_signatures JSONB,  -- Each custodian's HMAC of ceremony record
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## Settlement & Reconciliation

```sql
-- ============================================================
-- SETTLEMENT & RECONCILIATION
-- ============================================================

CREATE TABLE settlement_batches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Batch info
    batch_id        VARCHAR(30) NOT NULL UNIQUE,  -- e.g., 'SETT-2024-05-05-001'
    settlement_date DATE NOT NULL,
    currency        CHAR(3) NOT NULL,
    
    -- Net totals
    total_sales     NUMERIC(15,2) NOT NULL DEFAULT 0,
    total_refunds   NUMERIC(15,2) NOT NULL DEFAULT 0,
    total_fees      NUMERIC(15,2) NOT NULL DEFAULT 0,
    total_tax       NUMERIC(15,2) NOT NULL DEFAULT 0,
    net_amount      NUMERIC(15,2) NOT NULL DEFAULT 0,  -- sales - refunds - fees
    
    -- Counters
    sales_count     INT DEFAULT 0,
    refund_count    INT DEFAULT 0,
    
    -- Processing
    status          settlement_status_enum DEFAULT 'pending',  -- pending, processing, completed, failed
    processed_at    TIMESTAMPTZ,
    
    -- File reference
    acquirer_file   VARCHAR(255),  -- Filename from acquirer statement
    our_file        VARCHAR(255),  -- Our settlement file
    
    -- Reconciliation
    reconciled_at   TIMESTAMPTZ,
    reconciliation_diff NUMERIC(15,2) DEFAULT 0,
    reconciliation_notes TEXT,
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Chargebacks / Dispute Management
CREATE TABLE disputes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id      UUID REFERENCES payments(id),
    dispute_id      VARCHAR(40) NOT NULL UNIQUE,  -- Acquirer's dispute ID
    dispute_type    dispute_type_enum NOT NULL,  -- fraud, processing_error,Retrieval
    
    -- Reason
    reason_code     VARCHAR(10),
    reason_text     VARCHAR(255),
    dispute_amount  NUMERIC(15,2) NOT NULL,
    currency        CHAR(3) NOT NULL,
    
    -- Timeline
    filed_at        TIMESTAMPTZ DEFAULT NOW(),  -- Acquirer received dispute
    response_due    TIMESTAMPTZ NOT NULL,  -- Usually 10-45 days
    responded_at    TIMESTAMPTZ,
    
    -- Status
    status          dispute_status_enum DEFAULT 'pending',  -- pending, evidence_sent, won, lost, arbitration
    resolution      VARCHAR(30),
    
    -- Evidence
    evidence_sent_at TIMESTAMPTZ,
    evidence_files  JSONB,  -- List of file references
    
    -- Financial
    fees            NUMERIC(10,2) DEFAULT 0,
    reversed_at     TIMESTAMPTZ,
    
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
```

## Audit & Events

```sql
-- ============================================================
-- AUDIT LOG (Append-only, WORM)
-- ============================================================

-- Payment audit log (immutable)
CREATE TABLE payment_audit (
    id              BIGSERIAL PRIMARY KEY,  -- BIGSERIAL for performance
    payment_id      UUID NOT NULL,
    action          VARCHAR(50) NOT NULL,  -- created, status_changed, webhook_sent, etc.
    
    -- Snapshot of state at this moment
    payment_state   JSONB NOT NULL,  -- Full payment record at this point
    
    -- Context
    actor_type      VARCHAR(20),  -- user, system, psp, webhook
    actor_id        VARCHAR(64),
    ip_address      INET,
    request_id      UUID,  -- Correlation ID
    
    created_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- Event store for event sourcing
CREATE TABLE events (
    id              BIGSERIAL PRIMARY KEY,
    aggregate_id    UUID NOT NULL,
    aggregate_type  VARCHAR(50) NOT NULL,
    event_type      VARCHAR(100) NOT NULL,
    event_data      JSONB NOT NULL,
    metadata        JSONB,
    created_at      TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX idx_events_aggregate ON events(aggregate_type, aggregate_id);
CREATE INDEX idx_events_type ON events(event_type);

-- This table uses BRIN index for efficient time-range queries
CREATE INDEX idx_payment_audit_time ON payment_audit USING BRIN(created_at);
```

## Enums

```sql
CREATE TYPE payment_type_enum AS ENUM ('sale', 'auth', 'capture', 'refund', 'reversal', 'partial_refund');
CREATE TYPE payment_status_enum AS ENUM ('pending', 'authorized', 'captured', 'settled', 'failed', 'declined', 'cancelled', 'refunded', 'partially_refunded', 'disputed');
CREATE TYPE onboarding_status_enum AS ENUM ('pending', 'kyc_review', 'approved', 'rejected', 'suspended');
CREATE TYPE connection_type_enum AS ENUM ('iso8583', 'rest', 'open_banking', 'webhook');
CREATE TYPE settlement_status_enum AS ENUM ('pending', 'processing', 'completed', 'failed', 'reversed');
CREATE TYPE dispute_type_enum AS ENUM ('fraud', 'processing_error', 'retrieval_request', 'compliance', 'arbitration');
CREATE TYPE dispute_status_enum AS ENUM ('pending', 'evidence_sent', 'won', 'lost', 'arbitration', 'withdrawn');
```

## Migrations

```sql
-- Run migrations as separate transactions
-- Each migration: CREATE extension, then schema changes

-- Example: Add rolling reserve to merchants
ALTER TABLE merchants ADD COLUMN rolling_reserve_balance NUMERIC(15,2) DEFAULT 0;
ALTER TABLE merchants ADD COLUMN rolling_reserve_release_date TIMESTAMPTZ;

-- Example: Add 3DS data to payments
ALTER TABLE payments ADD COLUMN three_ds_xid VARCHAR(40);
ALTER TABLE payments ADD COLUMN three_ds_eci VARCHAR(4);
ALTER TABLE payments ADD COLUMN three_ds_cavv TEXT;
ALTER TABLE payments ADD COLUMN three_ds_authentication_id VARCHAR(40);
```