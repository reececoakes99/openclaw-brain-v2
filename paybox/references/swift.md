# SWIFT Messaging Reference

## Overview

SWIFT FIN (Financial Messaging) uses the MT (Message Type) standard for cross-border payments. Key messages:

| MT | Name | Usage |
|----|------|-------|
| MT103 | Single Customer Credit Transfer | Cross-border wire (our primary) |
| MT202 | General Financial Institution Transfer | Cover payments |
| MT940 | Customer Statement | Account statements |
| MT942 | Interim Transaction Report | Real-time account activity |
| MT300 | Foreign Exchange Contract | FX confirmation |
| MT400 | Payment Control Message | Advice of Payment |
| MT700 | Documentary Credit | Letter of Credit |
| MT900 | Debit Note | Account debit |
| MT910 | Credit Note | Account credit |

## MT103 — Single Customer Credit Transfer

The workhorse of international wire transfers.

```
{1:F01ABCUS33XXXX0000000000}{2:I103BANKDEFFXXXXN}{3:{108:MSGID-001}{111:20260505}}
{4:
:20:MSGID-001
:23B:CRED
:32A:060505EUR1000,00
:33B:EUR1000,00
:50K:/123456789
JOHN DOE
MAIN STREET 1
BERLIN DE
:52A:DEUTDEFFXXX
:53A:COBADEFFXXX
:57A:BNPAFRPPXXX
:59:/FR7612345678901234567890123
CLAUDE DUPONT
PARIS FR
:70:PAYMENT FOR ORDER 12345
:71A:OUR
:72:SPE//BETWEEN OURS AND YOURS
-}
```

## Field-by-Field Breakdown (MT103)

| Tag | Name | Format | Description |
|-----|------|--------|-------------|
| :20 | Transaction Reference | 16x | Unique sender reference |
| :21 | Related Reference | 16x | Optional, links related transactions |
| :23B | Bank Operation Code | 4!c3!c | CRED=credit transfer, CRDR=card |
| :32A | Value Date/Currency/Amount | 6!n3!a15d | Date in YYMMDD, e.g. 060505 = May 5 2006 |
| :33B | Instructed Amount | 3!a15d | If different from :32A (conversion) |
| :50K | Ordering Customer | /34x4*35x | K = multiline, F = formatted |
| :50F | Ordering Customer (formatted) | /[code] | With structured address |
| :52A | Ordering Institution | 4!a2!a2!c[3!c] | BIC of sender's bank |
| :53A | Sender's Correspondent | 3!a[/1!a] | Intermediary bank |
| :53D | Sender's Correspondent | 4*35x | BIC or address |
| :54A | Receiver's Correspondent | 4!a2!a2!c[3!c] | Beneficiary's bank correspondent |
| :54D | Receiver's Correspondent | 4*35x | Address |
| :55A | Third Reimbursement Institution | 4!a... | Further intermediary |
| :56A | Intermediary Institution | 4!a... | Intermediate bank |
| :57A | Beneficiary Institution | 4!a2!a2!c[3!c] | Beneficiary's bank BIC |
| :57D | Beneficiary Institution | 4*35x | Address (if no BIC) |
| :59 | Beneficiary Customer | /34x4*35x | Account number + name + address |
| :70 | Remittance Information | 4*35x | Payment reference (unstructured) |
| :71A | Beneficiary Bank Charge | OUR/SHA/BEN | OUR=we pay, SHA=shared, BEN=they pay |
| :71F | Sender Charges | 3!a15d | Our bank's charge |
| :71G | Receiver Charges | 3!a15d | Their bank's charge |
| :72 | Bank-to-Bank Info | 6*35x | Info for beneficiary's bank |
| :77B | Regulatory Reporting | 3!a | Regulatory requirements |

## SWIFT BIC Format

```
8 characters:  AAAABBCC DDD
  AAAA = Bank code
  BB   = Country code (ISO 3166-1 alpha-2)
  CC   = Location code
  DDD  = Branch (optional, XXX = head office)
```

## Building an MT103

```python
from datetime import datetime

class MT103:
    def __init__(self, sender_bic: str, receiver_bic: str):
        self.sender_bic = sender_bic
        self.receiver_bic = receiver_bic
        self.fields = {}

    def set_field(self, tag: str, value: str):
        self.fields[tag] = value

    def build(self) -> str:
        lines = []
        for tag in ['20', '21', '23B', '32A', '33B',
                    '50K', '52A', '53A', '54A', '56A', '57A', '59',
                    '70', '71A', '72']:
            if tag in self.fields:
                lines.append(f":{tag}:{self.fields[tag]}")

        # Format value date (YYMMDD)
        vd = self.fields.get('32A', '')
        cur = self.fields.get('currency', 'EUR')
        amt = self.fields.get('amount', '0,00')

        # Build block 1 (sender info) and block 2 (receiver info)
        block1 = f"F01{self.sender_bic}XXXX0000000000"
        block2 = f"I103{self.receiver_bic}XXXXN"
        block3 = f"{{108:{self.fields['20']}}}"

        block4 = "\n".join(lines)

        return (
            f"{{1:{block1}}}"
            f"{{2:{block2}}}"
            f"{{3:{block3}}}"
            f"{{4:\n{block4}\n-}}"
        )

    def validate(self) -> list[str]:
        errors = []
        required = ['20', '32A', '59', '71A']
        for tag in required:
            if tag not in self.fields:
                errors.append(f"Missing required tag: {tag}")

        # Value date must be today or future
        vd = self.fields.get('32A', '')[:6]
        if vd:
            try:
                year = int('20' + vd[:2])
                month = int(vd[2:4])
                day = int(vd[4:6])
                vdate = datetime(year, month, day)
                if vdate.date() < datetime.now().date():
                    errors.append("Value date cannot be in the past")
            except:
                errors.append(f"Invalid value date: {vd}")

        return errors


# Example usage
mt = MT103("PAYBOXDEFFXXX", "BNPAFRPPXXX")
mt.set_field('20', 'MSG-20260505-001')
mt.set_field('23B', 'CRED')
mt.set_field('32A', '260505EUR5000,00')
mt.set_field('50K', '/123456789\nJOHN DOE\nMAIN ST 1\nBERLIN DE')
mt.set_field('52A', 'PAYBOXDEFFXXX')
mt.set_field('59', '/FR7612345678901234567890123\nCLAUDE DUPONT\nPARIS FR')
mt.set_field('70', 'PAYMENT FOR ORDER-12345')
mt.set_field('71A', 'OUR')
errors = mt.validate()
if errors:
    print("Validation errors:", errors)
else:
    print(mt.build())
```

## MT940 — Account Statement

```swift
:20:STMT-20260505-001
:25:123456789/EUR
:28C:1/5
:60F:C250505EUR1234567,89
:61:2605050526C1000,00NTRFMSGID-001//REF123
:86:Payment from customer
:61:2605050527D500,00NTRFMSGID-002//REF456
:86:Refund
:62F:C260505EUR1235467,89
```

## SWIFT Testing

- [ ] MT103 format validation (field presence, length)
- [ ] BIC validation (8 or 11 chars, known in SWIFTRef)
- [ ] Value date in future (max T+2 business days)
- [ ] Amount format (comma as decimal separator, no spaces)
- [ ] Correspondent chain (chained routing)
- [ ] Cover payment handling (MT202 + MT103)
- [ ] Duplicate detection (same :20 within 30 days)
- [ ] Field 72 maximum length (6 lines × 35 chars)
- [ ] :71A OUR/SHA/BEN implications for fees
- [ ] Regulatory reporting (China, India, etc.)
- [ ] FIN header/authentication (SWIFTNet / SWIFTAlliance)