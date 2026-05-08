# Fraud Detection Reference

## Overview
Paybox implements multi-layered fraud prevention including real-time velocity checks, ML-based risk scoring, rules engine, and 3D Secure integration to protect merchants and cardholders.

## Velocity Checks

### Transaction Velocity
```python
velocity_rules = {
    "per_minute": {
        "max_count": 5,
        "window_seconds": 60,
        "action": "FLAG"
    },
    "per_hour": {
        "max_count": 20,
        "window_seconds": 3600,
        "action": "FLAG"
    },
    "per_day": {
        "max_count": 50,
        "window_seconds": 86400,
        "action": "FLAG"
    }
}
```

### Amount Velocity
- Hourly amount threshold: $10,000 default
- Daily amount threshold: $50,000 default
- Per-card velocity tracking

### Geo-Velocity Rules
```python
geo_velocity = {
    "max_distance_km": 500,
    "max_time_seconds": 3600,  # Impossible travel detection
    "impossible_travel_threshold": 1000,  # km
    "action": "BLOCK"
}
```

## Rule-Based Detection

### Amount Thresholds
| Rule | Condition | Action |
|------|-----------|--------|
| High Value | amount > $5000 | FLAG |
| Very High Value | amount > $10000 | REVIEW |
| Low Value Suspicious | amount < $5 AND new card | FLAG |
| Velocity Burst | 3 transactions in 60s | FLAG |

### Card Verification Rules
```python
cvv_rules = {
    "cvv_mismatch": {"action": "BLOCK"},
    "avs_partial_match": {"action": "FLAG"},
    "avs_no_match": {"action": "REVIEW"}
}

# AVS Response Codes
avs_codes = {
    "Y": "Full match",
    "N": "No match", 
    "X": "Address unavailable",
    "W": "Street match only",
    "Z": "Postal match only"
}
```

### Device Fingerprint Rules
- New device first transaction: FLAG
- Device shared across multiple cards: FLAG
- Tor exit node detected: BLOCK
- VPN detected (configurable): FLAG
- Proxy detected: FLAG

### IP-Based Rules
- IP in blacklist: BLOCK
- IP from high-risk country: REVIEW
- IP different from card country: FLAG
- Anonymous proxy: BLOCK
- Hosting provider IP: FLAG

## Machine Learning Features

### Core ML Features
```python
ml_features = {
    # Amount features
    "amount_log": "log(amount + 1)",
    "amount_z_score": "standardized amount",
    "amount_vs_avg_merchant": "ratio to merchant mean",
    
    # Frequency features
    "txn_count_1h": "transactions in last hour",
    "txn_count_24h": "transactions in 24h",
    "txn_count_7d": "transactions in 7 days",
    "unique_cards_24h": "distinct cards",
    
    # Device features
    "device_age_days": "first seen to now",
    "device_txn_count": "lifetime txn count",
    "device_risk_score": "device ML model score",
    
    # IP features
    "ip_age_days": "IP first seen to now",
    "ip_txn_count": "lifetime txn count",
    "ip_country_match_card": "bool"
}
```

### Model Ensemble
- **Gradient Boosted Trees**: Fast, interpretable
- **Neural Network**: Complex patterns
- **Isolation Forest**: Anomaly detection
- **Ensemble weighting**: Combine predictions

### Risk Score Output
```
score range: 0-100
0-30: LOW (auto-approve)
31-60: MEDIUM (monitor)
61-80: HIGH (review)
81-100: CRITICAL (block)
```

## 3D Secure Integration

### 3D Secure Flow
```
Cardholder Checkout
    ↓
Paybox checks 3DS eligibility
    ↓
Issuer ACS challenged
    ↓
ECI + CAVV returned
    ↓
Authorization with liability shift
```

### Authentication Results
```python
three_ds_results = {
    "authenticated": {
        "eci": "05",  # Visa authenticated
        "cavv": "base64_signature",
        "xid": "transaction_id",
        "liability": "SHIFTED_TO_ISSUER"
    },
    "attempted": {
        "eci": "06",  # Attempted authentication
        "liability": "SHIFTED_TO_ISSUER"
    },
    "not_enrolled": {
        "eci": "07",  # Not enrolled
        "liability": "REMAINS_MERCHANT"
    },
    "failed": {
        "eci": "07",
        "liability": "REMAINS_MERCHANT"
    }
}
```

### Liability Shift
- Full 3DS authentication: Liability shift to issuer
- Attempted/failed: Liability remains with merchant
- Fraud loss coverage: Up to £100 for UK under 3DS2

## Risk Scoring Thresholds

### Default Thresholds
```python
risk_thresholds = {
    "auto_approve_max": 30,
    "review_min": 61,
    "review_max": 80,
    "block_min": 81,
    "high_value_flag": 10000,  # Amount in cents
    "high_value_review_min": 61  # Amount threshold for review
}
```

### Merchant Overrides
- High-risk merchants: Stricter thresholds
- Enterprise merchants: Looser thresholds (after negotiation)
- MCC-based adjustments
- Volume-based adjustments

## Blacklist/Whitelist

### Blacklist Types
```python
blacklist = {
    "card_fingerprint": {
        "reason": "fraud_confirmed",
        "added_at": "2026-01-15",
        "expires_at": null  # Permanent
    },
    "ip_address": {
        "reason": "attacking_patterns",
        "added_at": "2026-03-01",
        "expires_at": "2027-03-01"
    },
    "device_id": {
        "reason": "shared_fraud_tool",
        "added_at": "2026-02-01",
        "expires_at": null
    },
    "email_domain": {
        "reason": "disposable_email",
        "added_at": "2026-01-01",
        "expires_at": null
    }
}
```

### Whitelist Types
```python
whitelist = {
    "merchant_id": {
        "purpose": "trusted_partner",
        "fraud_check_level": "REDUCED"
    },
    "card_hash": {
        "purpose": "verified_customer",
        "velocity_multiplier": 2.0
    }
}
```

### List Management
- Automated additions for confirmed fraud
- Manual review for whitelist
- 90-day automatic review for temporal blacklists
- Audit trail for all changes

## Case Management

### Manual Review Queue
```python
review_case = {
    "case_id": str,
    "payment_id": str,
    "merchant_id": str,
    "reviewer_id": str,
    "assigned_at": datetime,
    "status": QUEUED|IN_REVIEW|RESOLVED|ESCALATED,
    "risk_factors": list,
    "evidence": list,
    "decision": APPROVE|DECLINE|FLAG,
    "decision_reason": str,
    "resolved_at": datetime
}
```

### Review Workflow
1. Case enters queue with priority score
2. Auto-assign to available reviewer
3. Reviewer sees transaction details + risk factors
4. Reviewer accesses card issuer portal if needed
5. Decision made with required reason
6. Case archived with full audit trail

### SLA Targets
- Average review time: < 15 minutes
- Queue depth alerts: > 50 cases
- Escalation: > 30 minutes unreviewed

## Chargeback Representment

### Representment Workflow
1. **Evidence Collection**
   - Authorization proof (auth code, AVS/CVV results)
   - Capture proof (signed receipt, delivery confirmation)
   - Transaction receipt (invoice, email confirmation)
   - Customer communication history

2. **Response Submission**
   - Deadline: 7 days (configurable by scheme)
   - Format: Scheme-specific (HISO87 for Visa/MC)
   - Pre-arbitration available for lost cases

3. **Resolution Tracking**
   - Win rate by reason code
   - Response time correlation
   - False positive analysis

### Evidence Types by Reason Code
| Reason | Evidence Required |
|--------|-------------------|
| Fraud | AVS/CVV, 3DS, IP data, device fingerprint |
| Product Not Received | Delivery confirmation, tracking, correspondence |
| Product Unacceptable | Return policy, description vs reality |
| Credit Not Processed | Original receipt, cancellation confirmation |

## Integration with Payment Flow

### Inline Risk Evaluation
```python
async def evaluate_transaction(payment: Payment) -> RiskResult:
    # 1. Rules engine (fast path)
    rule_result = rules_engine.evaluate(payment)
    if rule_result.action == "BLOCK":
        return RiskResult(blocked=True, reason=rule_result.reason)
    
    # 2. ML model (parallel)
    ml_score = ml_model.predict(payment.features)
    
    # 3. 3DS check (if enabled)
    if payment.requires_3ds:
        auth_result = await three_ds.authenticate(payment)
        
    # 4. Combine decisions
    final_score = combine_scores(rule_result, ml_score, auth_result)
    return decide_action(final_score)
```

### Real-Time Decision
- Max decision latency: 100ms
- Decision includes: approve/block/review + score + factors
- Webhook emitted for all non-approved decisions
