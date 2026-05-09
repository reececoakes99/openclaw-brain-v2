# Compliance & Governance Reference

PCI-DSS, FIPS 140-2, Scheme Certification, and Data Privacy requirements.

## PCI-DSS Requirements Summary

| Requirement | Domain | Key Controls |
|------------|--------|-------------|
| Req 1 | Firewalls | Network segmentation, inbound/outbound rules |
| Req 2 | Defaults | No vendor defaults, hardened configs |
| Req 3 | PAN Storage | Masked display, encrypted storage, tokenization |
| Req 4 | Transmission | TLS 1.2+, HSM-grade transport for ISO8583 |
| Req 5 | Malware | Anti-virus, patch management |
| Req 6 | Vulnerabilities | Patch management, secure coding |
| Req 7 | Access Control | Role-based, least privilege |
| Req 8 | Authentication | MFA for admin, complex passwords |
| Req 9 | Physical Security | HSM cage, server room access logs |
| Req 10 | Logging | All system events, ≥99% uptime logging |
| Req 11 | Testing | Quarterly ASV scans, penetration testing |
| Req 12 | Policy | Security policy, risk assessments |

### PAN Handling Rules

```
✓ NEVER log PAN in plain text
✓ ALWAYS mask: `......1234` (first 6 + last 4)
✓ Store ONLY: tokenized PAN or AES-256 encrypted PAN
✓ PCI scope: Only components touching PAN/card data
✓ Token vault: AES-256 GCM, HSM-backed KEK
```

## FIPS 140-2 Level 3

All cryptographic modules (HSMs) must be FIPS 140-2 Level 3 certified:

- Physical security: tamper-responsive, tamper-evident enclosure
- Role-based authentication: Cryptographic Officer + User roles
- Cryptographic boundary: all key ops confined to HSM
- Zeroization: immediate on tamper detection

## Scheme Certification Process

### Visa

```
ADVT (Acquirer Device Validation Tool)
  ↓
V.I.P. (Visa Integrated Payments) testing
  ↓
VTD (Visa Terminal Device) approval
  ↓
Acquirer certification with Visa
  ↓
Production connectivity
```

### MasterCard

```
M-TIP (MasterCard Terminal Integration Program)
  ↓
MEM (Mastercard Engineering Mobile) testing
  ↓
UAT with acquiring bank
  ↓
Production certification
```

## Data Privacy (GDPR / CCPA)

| Data Category | Examples | Handling |
|---------------|---------|---------|
| PAN | Card number | Tokenize or encrypt (AES-256), never log |
| PII | Name, email, address | Pseudonymize, access-controlled |
| CVV | 3-digit security code | Never stored post-auth |
| PIN | Card PIN | HSM-only, encrypted under LMK, never logged |
| Track Data | Magnetic stripe data | Encrypted, PCI scope |
| Geolocation | IP → country | Anonymize after risk decision |

## Key Certifications Checklist

- [ ] PCI DSS Level 1 (merchant/processor)
- [ ] PCI P2PE (point-to-point encryption)
- [ ] Visa ADVT / VTD
- [ ] MasterCard M-TIP / MEM
- [ ] Amex Digital Secure / OLB
- [ ] FIPS 140-2 Level 3 (HSM)
- [ ] ISO 27001 (information security)
- [ ] SOC 2 Type II (if applicable)
- [ ] PSD2 (for EU open banking)
