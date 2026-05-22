# Test Data — Payment Gateway

## Card Test Numbers

| Network | Number | Type | Description |
|---------|--------|------|-------------|
| Visa | 4111111111111111 | Credit | Standard test card |
| Visa | 4012888888881881 | Credit | Test card (2-series) |
| Visa | 4222222222222 | Debit | 13-digit Visa |
| Mastercard | 5555555555554444 | Credit | Standard test card |
| Mastercard | 5105105105105100 | Credit | 2-series test card |
| Mastercard | 2221000000000009 | Credit | Extended range test |
| Amex | 378282246310005 | Credit | 15-digit Amex |
| Amex | 371449635398431 | Credit | Amex corporate |
| Amex | 340000000000009 | Credit | Short test card |
| Discover | 6011111111111117 | Credit | Standard |
| Discover | 6500000000000002 | Credit | 16-digit |
| Diners | 36227206271667 | Credit | 14-digit |
| JCB | 3566002020360505 | Credit | 16-digit |
| UnionPay | 6200000000000005 | Credit | 16-digit |
| Maestro | 5018000000000007 | Debit | 18-digit |

## ISO8583 Message Templates

### HISO93 Binary — Authorization Request (0100)
```
MTI: 0100 (2 bytes, BCD)
Bitmap: 8 bytes, primary + secondary
DE3: 6 digits — processing code
DE4: 12 digits — transaction amount (no decimal)
DE7: 10 digits — transmission date+time MMDDhhmmss
DE11: 6 digits — system trace audit number (STAN)
DE12: 6 digits — local transaction time HHMMSS
DE13: 4 digits — local transaction date MMDD
DE14: 4 digits — card expiration date YYMM
DE18: 4 digits — merchant category code
DE19: 3 digits — acquiring institution country code
DE22: 3 digits — POS entry mode (020/050/901)
DE32: variable — acquiring institution ID
DE35: variable — track 2 data
DE37: 12 digits — reference number (RRN)
DE41: 8 digits — terminal ID
DE42: 15 digits — merchant ID
DE49: 3 digits — currency code (840/USD, 978/EUR, 826/GBP)
DE60: variable — reserved national (batch number)
DE61: variable — reserved national (POS data)
```

### HISO87 ASCII — Authorization Response (0110)
```
Format: LLLL + MTI + Bitmap + Fields
LLLL: 4-digit ASCII message length (0000-9999)
MTI: 4-digit ASCII
Bitmap: 32 hex chars (uncompressed, 128 DEs)
Fields: ASCII with length indicators for variable fields
```

## Test Amounts

| Category | Values |
|----------|--------|
| Normal | 1000, 5000, 10000, 25000, 50000, 100000 |
| Boundary | 0.01, 9999999999.99 |
| Decline amounts | 10001 (insufficient funds), 10051 (card blocked) |
| Timeout test | 99999 (no response expected) |

## Currency Codes

USD (840), EUR (978), GBP (826), JPY (392), CNY (156), CHF (756), AUD (036), CAD (124), BRL (986), INR (356)

## Test Merchant Profiles

```json
{
  "merchants": [
    {
      "merchant_id": "mer_test_001",
      "name": "Test Electronics Store",
      "mcc": "5734",
      "environment": "test",
      "fee_schedule": {
        "interchange_plus": 0.015,
        "scheme_fee": 0.001,
        "acquiring_margin": 0.005,
        "monthly_minimum": 25.00
      },
      "settlement_terms": {
        "frequency": "daily",
        "currency": "USD",
        "rolling_reserve_pct": 0
      },
      "api_key": "pk_test_xxxxxxxxxxxxxxxxxxxxxxxx"
    },
    {
      "merchant_id": "mer_test_002",
      "name": "Test Travel Agency",
      "mcc": "4722",
      "environment": "test",
      "fee_schedule": {
        "interchange_plus": 0.020,
        "scheme_fee": 0.002,
        "acquiring_margin": 0.010
      },
      "rolling_reserve_pct": 5,
      "webhook_url": "https://webhook.test/mer002"
    }
  ]
}
```

## Mock HSM Responses

| Operation | Request | Mock Response |
|-----------|---------|--------------|
| PIN encrypt | Encrypt PIN block under TPK | Success, encrypted PIN block |
| MAC generate | Generate MAC over message | Success, 8-byte MAC |
| MAC verify | Verify MAC | Success/Failure |
| Key translate | Translate PIN from TPK to ZPK | Success, translated block |
| ARQC verify | Verify ARQC from chip card | Success, ARPC generated |
| Key generate | Generate working key (TAK/TPK) | Success, key encrypted under ZMK |

## Test Scenarios

```json
{
  "scenarios": [
    {
      "name": "Happy Path Authorization",
      "mti_request": "0100",
      "mti_expected_response": "0110",
      "expected_field_39": "00",
      "description": "Standard approved authorization"
    },
    {
      "name": "Insufficient Funds",
      "mti_request": "0100",
      "de4_amount": "000000000101",
      "expected_field_39": "51"
    },
    {
      "name": "Invalid Card",
      "mti_request": "0100",
      "de14_expired": "2401",
      "expected_field_39": "54"
    },
    {
      "name": "Full Capture",
      "mti_request": "0200",
      "de4_amount": "000000001000",
      "expected_field_39": "00"
    },
    {
      "name": "Partial Capture",
      "mti_request": "0200",
      "de4_amount": "000000000500",
      "de37_orig_rrn": "000000000001",
      "expected_field_39": "00"
    },
    {
      "name": "Reversal",
      "mti_request": "0400",
      "de37_orig_rrn": "000000000001",
      "expected_field_39": "00"
    }
  ]
}
```