# Ledger & Reconciliation Reference

## Overview
The Paybox ledger implements double-entry bookkeeping for all financial transactions, maintaining immutable transaction journals with full audit trails across authorization, capture, refund, and chargeback flows.

## Double-Entry Bookkeeping

### Account Types
- **Asset Accounts**: Cash (settlement account), Receivables (pending settlements)
- **Liability Accounts**: Merchant settlements payable, Rolling reserves
- **Equity Accounts**: Fee income, Interchange expense
- **Revenue/Expense**: Scheme fees, Acquirer fees, Platform fees

### Entry Structure
Every transaction creates balanced debit/credit entries:
```
Transaction ID: TXN-20240615-001
  Merchant Receivable    DR  $100.00
  Cash Settlement        CR  $100.00

Fee Recording:
  Merchant Fee           DR  $2.50
  Fee Income             CR  $2.50

Interchange:
  Interchange Expense    DR  $1.80
  Scheme Settlement      CR  $1.80
```

## Transaction Journal

### Lifecycle States
```
AUTHORIZATION -> CAPTURE -> SETTLEMENT -> RECONCILIATION -> COMPLETED
                     |
                     v
                  REFUND
                     |
                     v
              CHARGEBACK (T+1 to T+180)
```

### Authorization Flow
1. Auth request received with amount, card data, merchant_id
2. Create pending ledger entry (liability side)
3. Record interchange estimate
4. Emit auth event to message queue
5. Return auth code + reference

### Capture Flow
1. Capture request matches original auth
2. Transition pending to captured state
3. Split amounts: gross, fees, net settlement
4. Create GL entries for all legs
5. Update merchant position

### Refund Flow
1. Full or partial refund request
2. Create reversal entries (debit original revenue)
3. Update settlement queue
4. Trigger refund notification webhook
5. Reconcile within current or next settlement batch

### Chargeback Flow
1. Acquirer sends chargeback notification (CBID)
2. Create provisional debit entry against merchant
3. Attach evidence package for representment
4. If won: reverse provisional entry
5. If lost: finalize debit, update rolling reserve

## Settlement Netting & Batching

### Daily Netting Process
- Aggregate all captured transactions per merchant
- Calculate net settlement amount after fees
- Generate settlement file for scheme (HISO93 format)
- Submit to acquirer by 18:00 UTC cutoff

### Settlement Batching
```python
class SettlementBatch:
    merchant_id: str
    currency: str
    gross_amount: Decimal
    fees: FeeBreakdown
    net_amount: Decimal
    transaction_count: int
    settlement_date: date
    status: PENDING|PROCESSING|COMPLETED|FAILED
```

### Settlement Terms
- **T+1**: Next business day settlement (standard)
- **T+2**: Two business days (some schemes/card types)
- **Weekly**: Every Monday for rolling reserve merchants
- **Monthly**: Enterprise merchants with negotiated terms

## Multi-Currency & FX

### Currency Handling
- All amounts stored in transaction currency
- Conversion to settlement currency at auth rate (locked)
- FX gain/loss recorded at settlement
- Currency precision: 4 decimal places for FX, 2 for transaction

### Settlement Currency Conversion
```python
fx_rate_locked = get_fx_rate(auth_timestamp, txn_currency, settle_currency)
settled_amount = txn_amount * fx_rate_locked
fx_variance = abs(settled_amount - expected_amount)
# Variance > threshold triggers investigation
```

## Reconciliation

### T+1 Reconciliation Process
1. Download settlement reports from acquirer
2. Match Paybox transactions to acquirer records
3. Flag unmatched transactions
4. Investigate and resolve exceptions
5. Generate reconciliation report

### T+2 Settlement Finalization
- Confirm final settlement amounts
- Update merchant ledger positions
- Trigger payout processing
- Archive reconciliation records (7 years)

### Exception Handling
```
Exception Types:
- AMOUNT_MISMATCH: Paybox amount != Scheme amount
- MISSING_TRANSACTION: In scheme report, not in Paybox
- DUPLICATE_TRANSACTION: Multiple captures detected
- TIMING_MISMATCH: Auth/capture timing discrepancy
```

## Fee Calculation

### Interchange++
Interchange rate varies by:
- Card type (consumer/premium/corporate)
- Card present (CP) vs Card Not Present (CNP)
- Entry mode (chip/swipe/contactless)
- Transaction type (sale/withdrawal)

```
Interchange Schedule (example USD):
- Domestic Visa Credit: 1.50% + $0.10
- International MC Credit: 2.00% + $0.10
- Amex: 2.50% + $0.05
```

### Scheme Fees
- Visa/MC assessment: 0.10% of transaction value
- Processing fee: Fixed per transaction
- Cross-border fee: Additional 1% for international

### Acquirer Fees
- Per-transaction fee: $0.02-$0.05
- Monthly minimum: $100
- Volume discounts: Tiered based on monthly volume

### Platform Fees
- Transaction fee: Configured per merchant (0.5%-3%)
- Rolling reserve: 5-10% withheld for 90 days
- Chargeback fee: $15-$25 per dispute
- Refund fee: $0.25-$0.50 per refund

## Rolling Reserve

### Reserve Calculation
```python
reserve_rate = merchant.rolling_reserve_rate  # default 5%
reserve_amount = transaction.net_amount * reserve_rate
hold_release_date = today + 90 days
```

### Reserve Release
- Automatic release after 90 days if no chargebacks
- Partial release proportional to resolved disputes
- Full withholding if active dispute ongoing

## GL Integration

### Chart of Accounts
```
1000-1999: Assets
  1001: Cash - Settlement Account
  1002: Cash - Rolling Reserve
  1100: Accounts Receivable - Merchants
  
2000-2999: Liabilities
  2001: Settlements Payable
  2002: Rolling Reserve Payable
  2100: Accounts Payable - Schemes
  
3000-3999: Equity
  3001: Retained Earnings
  
4000-4999: Revenue
  4001: Transaction Fees
  4002: Monthly Fees
  
5000-5999: Expenses
  5001: Interchange Expense
  5002: Scheme Fees
  5003: Acquirer Fees
```

### Daily GL Close
1. Run end-of-day batch at 23:00 UTC
2. Generate trial balance
3. Verify debit = credit
4. Generate daily P&L
5. Export for ERP integration

## Audit & Compliance

### Audit Trail Requirements
- All entries immutable (append-only)
- Retention: 7 years minimum (PCI DSS)
- Immutable timestamp on each entry
- User/action attribution where applicable

### Reconciliation Reports
- Daily settlement summary
- Exception report
- Fee breakdown by merchant
- Chargeback status report
- Rolling reserve report
