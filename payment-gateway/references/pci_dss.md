# PCI DSS Compliance — Requirements & Implementation

## PCI DSS Overview

PCI DSS v4.0 has 12 requirements across 6 goals. Version 4.0 became mandatory March 2025.

## Scoping

```
SCOPE BOUNDARY:
┌─────────────────────────────────────────────────────────┐
│  IN SCOPE (CDE — Cardholder Data Environment)           │
│  ├── message-engine (PAN processing)                    │
│  ├── vault-service (card data storage)                  │
│  ├── hsm-service (key management)                      │
│  ├── rest-api (card data transit)                       │
│  ├── connector-spdh (terminal encryption)               │
│  ├── Any server/DB storing PAN, cardholder data         │
│  └── Any jump server into CDE                           │
│                                                         │
│  OUT OF SCOPE                                           │
│  ├── admin-ui (no PAN access)                           │
│  ├── fraud-engine (tokenized data only)                  │
│  ├── settlement engine (amounts only, no PAN)           │
│  ├── reporting (aggregated data, no card data)         │
│  └── Infrastructure (K8s, monitoring — if isolated)     │
└─────────────────────────────────────────────────────────┘

SCOPING RULES:
- Anything connecting to CDE → IN SCOPE
- Shared hosting (co-lo) → All in same scope
- Network segmentation must be documented and tested
- Scope reduction via network segmentation (VLANs, firewalls)
```

## Goals & Requirements

### Goal 1: Build & Maintain Secure Network

**Req 1: Firewall Configuration**
```
- Documented firewall rules (allow/deny)
- Default deny all
- Perimeter firewalls between CDE and DMZ
- NAT/PAT rules to prevent external access to internal
- Personal firewall on all laptops with CDE access
- No direct route from external net to CDE
```

**Req 2: Default Vendor Settings**
```
- Change all default passwords before deployment
- Remove unnecessary default accounts
- Remove/disable unused services/protocols
- Remove sample apps/test code
- Remove default SNMP community strings
```

### Goal 2: Protect Account Data

**Req 3: Stored Account Data**
```
REQUIREMENTS:
- Minimize stored data: only what's business-essential
- CARD NUMBER: Store only last 4 digits (after auth)
- EXPIRY: Store only if strictly needed
- CVV: NEVER store post-authorization (must delete immediately)
- Full PAN stored only in HSM/vault with AES-256

RETENTION & DELETION:
- Define retention period by legal/regulatory requirements
- Automate deletion after retention period
- Document what data is kept and why
- Secure deletion (overwrite 3x or crypto erase)
```

**Req 4: Card Data in Transit**
```
- Encrypt all cardholder data over public networks (TLS 1.2+)
- No unencrypted PAN transmission (even internally)
- SSH for server access (SFTP, SCP)
- mTLS for all internal CDE services
- Certificate pinning for external connections
```

**Req 5: Protect Against Malware**
```
- Anti-virus on all systems commonly targeted
- Keep anti-virus signatures updated
- Regular scans
- No personal email/browsing on CDE servers
```

### Goal 3: Maintain Vulnerability Management

**Req 6: Patch Management**
```
- Critical patches: < 30 days
- All patches: < 90 days
- Critical vulnerabilities: < 72 hours (v4.0)
- Document exception process for delayed patching
- Patch testing in non-prod before production
```

### Goal 4: Implement Access Controls

**Req 7: Need-to-Know Access**
```
- Restrict access to systems by business need
- Role-based access (RBAC)
- Principle of least privilege
- Document which roles need access to CDE
- Privileged access management (PAM) for admin actions
```

**Req 8: User ID & Authentication**
```
- Unique user IDs (no shared accounts)
- MFA for all remote access to CDE
- MFA for admin access (console, API)
- Password policy: min 12 chars, complexity, rotation
- No default passwords
- User access reviews every 90 days
- Immediate revocation on termination
- Lockout after 6 failed attempts (15 min)
- Session timeout: 15 min inactivity
```

**Req 9: Physical Access**
```
- Physical security controls for CDE (datacenter)
- Badge/access logs
- CCTV for server rooms
- Visitor escort requirements
- Media destruction procedures (certificate required)
- POS terminal physical security
```

### Goal 5: Monitor & Test Networks

**Req 10: Logging & Monitoring**
```
REQUIRED LOGS:
- All individual user access to cardholder data
- All admin/root actions
- All access to audit trails
- Invalid logical access attempts
- Use of/change to identification (user IDs)
- Initialization of audit logs
- Creation/deletion of system-level accounts

LOG RETENTION: 1 year (3 months immediately accessible)
LOG PROTECTION: Read-only, tamper-proof (WORM storage or cryptographic hash chain)
ALERTING: Automated response to anomalies

KEY LOG SOURCES:
- Application logs (payment engine)
- Database audit (PostgreSQL audit)
- OS logs (syslog, auditd)
- HSM audit (key ceremonies, operations)
- Firewall/network logs
```

**Req 11: Regular Testing**
```
- Quarterly: Internal vulnerability scans
- Annual: External vulnerability scan (by approved vendor)
- Annual: Penetration test (network + application)
- Annual: Segmentation tests (CDE isolation verification)
- Monthly: Wireless scans (no unauthorized APs)
- File integrity monitoring (AIDE, tripwire)
```

### Goal 6: Maintain Information Security Policy

**Req 12: Risk Assessment & Security Policy**
```
- Annual risk assessment (documented)
- Security policies (reviewed annually)
- Security awareness training (annual)
- Background checks for employees
- Incident response plan (tested annually)
- Third-party security reviews (annual)
- Security policy for vendors
```

## Tokenization — Best Approach

```python
# Tokenization replaces PAN with a token
# The token has no value without the vault

TOKEN_TYPES = {
    "network_token": "Token generated by card network (Visa/MC)"
                      "Linked to specific merchant/device. Used in digital wallets.",
    
    "vault_token": "Our own generated token. No network meaning."
                    "Used for our internal processing and merchant storage.",
    
    "merchant_token": "Deterministic token per merchant. Allows merchant "
                      "to match transactions without storing PAN."
}

class TokenVault:
    """PCI DSS-compliant tokenization service."""
    
    def tokenize(self, pan: str) -> TokenizedCard:
        # Validate PAN format
        assert re.match(r'^\d{13,19}$', pan)
        assert luhn_check(pan)  # ISO/IEC 7812
        
        # Generate token (no link to PAN in token itself)
        token = self.token_generator.generate(pan)
        
        # Store mapping (encrypted in HSM-backed vault)
        self.vault_store.store(
            token=token,
            pan_hash=sha256(pan),  # For lookup without storing PAN
            pan_last4=pan[-4:],
            expiry_month=self.get_expiry_month(pan),  # from DE55 or DE14
            card_type=self.detect_card_type(pan),
            created_at=datetime.utcnow(),
            created_by=self.context.user_id  # Audit
        )
        
        # Return token + last4 for display purposes
        return TokenizedCard(
            token=token,
            last4=pan[-4:],
            card_type=self.detect_card_type(pan),
            vault_id=self.vault_id
        )
    
    def detokenize(self, token: str) -> str:
        # Requires: audit logging, MFA, role-based access
        assert self.has_detokenize_permission(self.context.user)
        
        # Log the detokenization event
        self.audit_log.log(
            action="DETOKENIZE",
            token=token,
            user=self.context.user_id,
            timestamp=datetime.utcnow(),
            ip=self.context.source_ip
        )
        
        return self.vault_store.get_pan(token)
    
    def delete_token(self, token: str):
        # Support right to be forgotten / card replacement
        self.vault_store.delete(token)
        self.audit_log.log(action="TOKEN_DELETE", token=token)
```

## Network Segmentation Checklist

```
SEGMENTATION REQUIREMENTS:
- CDE in isolated VLAN/zone
- Firewall rules between CDE and corporate LAN
- No direct route from Internet → CDE
- All traffic between zones via explicit ACLs
- Tested quarterly

VERIFICATION TEST:
1. Place test machine in each zone outside CDE
2. Attempt to reach CDE systems (ping, TCP, UDP)
3. Document all allowed paths
4. Block unexpected paths
5. Re-test after changes
```

## SAQ Types (Self-Assessment Questionnaire)

| SAQ | Description | Requirements |
|-----|-------------|-------------|
| A | Card-not-present (e-commerce merchants using third-party) | 22 questions |
| A-EP | E-commerce with direct merchant server | 22 + additional |
| B | Standalone dial-out terminals | 22 + additional |
| B-IP | IP-connected standalone terminals | 22 + additional |
| C-VT | Virtual terminal (browser-based, manual entry) | 22 + additional |
| C | Merchant with networked payment systems | 22 + additional |
| D | All other merchants + all service providers | 22 + additional |
| P2PE | Approved P2PE solution (hardware-based encryption) | 22 + additional |

## Compliance Validation

```python
# Quarterly compliance check
def run_compliance_check() -> ComplianceReport:
    
    checks = [
        FirewallRuleCheck(),          # Req 1
        PasswordPolicyCheck(),        # Req 2, 8
        StoredCardDataCheck(),        # Req 3
        EncryptionCheck(),            # Req 4
        MalwareProtectionCheck(),     # Req 5
        PatchLevelCheck(),            # Req 6
        AccessControlCheck(),         # Req 7, 8
        PhysicalSecurityCheck(),      # Req 9
        LoggingCheck(),               # Req 10
        SegmentationTestCheck(),      # Req 11
        PolicyReviewCheck(),          # Req 12
    ]
    
    results = []
    for check in checks:
        result = check.run()
        results.append(result)
    
    return ComplianceReport(
        date=datetime.utcnow(),
        checked_by=get_current_user(),
        results=results,
        status="PASS" if all(r.passed for r in results) else "FAIL"
    )
```

## Key Dates & Version History

| Version | Effective Date | Key Changes |
|---------|---------------|-------------|
| v1.0 | 2004 | Original |
| v2.0 | 2013 | Clarifications |
| v3.0 | 2014 | More rigorous, multi-factor |
| v3.2.1 | 2018 | Targeted risk analysis |
| v4.0 | 2022 | Future-dated reqs |
| v4.0 mandatory | March 2025 | All requirements enforced |

## Reporting Requirements

- Annual: SAQ or ROC (Report on Compliance) by QSA
- Quarterly: Network vulnerability scans by ASV
- Annual: Penetration test report
- Immediate: Incident notification to card brands if breach suspected