# Red Team Testing Framework

Complete offensive security coverage for payment switch infrastructure. 110 items across Skills, Tools, and Bots.

---

## Skills (65 Total)

### A. Protocol Converters & Bridges (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| A1 | Malicious ISO8583 Grammatical Mutator | Systematic DE mutation with grammar rules — field lengths, bitmap entries, MTI values, encoding types — to trigger parser crashes | HIGH |
| A2 | Replay Attack Engine | Capture valid transactions, replay with same STAN, incremented STAN, same/shifted timestamp to test replay protection | HIGH |
| A3 | Cryptographic Downgrade Tester | Systematically test MAC stripping, weakening, PIN block format downgrade, TLS cipher suite weakening | HIGH |
| A4 | Boundary Value Exploiter | Generate messages at exact field length boundaries (min, max, max+1, max-1, zero) for every DE | MEDIUM |
| A5 | Protocol Fuzzing Framework | Systematic fuzzing of every DE independently, find parser edge cases | MEDIUM |

### B. Infrastructure & Automation (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| B1 | Built-in Echo/Mock Server | TCP loopback listener for ISO8583, configurable responses/delays, field echoing | HIGH |
| B2 | MITM Proxy for ISO8583 | Transparent TCP proxy, real-time decode, on-the-fly message modification | HIGH |
| B3 | Connection Stress Tester | Rapid connect/disconnect, half-open connections, slow-read attacks, connection floods | MEDIUM |
| B4 | Protocol Fingerprinter | Probe messages to identify target vendor/version/quirks from response patterns | MEDIUM |
| B5 | PCAP Import/Export | Extract ISO8583 from pcap, export crafted messages for Wireshark/tcpreplay | MEDIUM |

### C. Web-Layer Payment Testing (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| C1 | OWASP ZAP Integration | Automated scanning of payment admin panels, REST APIs, webhook endpoints | HIGH |
| C2 | SQL/XXE Injection | Inject into fields that reach DB (DE48, DE62, ISO20022 XML payloads) | HIGH |
| C3 | Session Hijacking | Capture and replay admin session tokens from payment flow captures | MEDIUM |
| C4 | CSRF on Admin Panels | Identify CSRF on state-changing admin endpoints (key rotation, config changes) | MEDIUM |
| C5 | Admin Panel Enumeration | Brute-force admin URLs, credential stuffing on payment admin interfaces | MEDIUM |

### D. Payment Gateway API Testing (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| D1 | REST API Fuzzing | Fuzz all PISP/AISP/link endpoints, find injection, overflow, auth bypass | HIGH |
| D2 | Webhook Hijacking | Test webhook signature bypass, replay attacks on notification endpoints | HIGH |
| D3 | Rate Limit Bypass | Test rate limit headers, find enumeration, brute-force on payment IDs | MEDIUM |
| D4 | JSON/XML Tampering | Modify payment amounts, currencies, beneficiary details in flight | MEDIUM |
| D5 | Open Redirect on Payment Links | Find open redirect on payment link pages for phishing workflows | MEDIUM |

### E. Authentication & Verification Testing (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| E1 | 3DS Bypass Testing | Test 3DS authentication flow bypass, MPI tampering, fall-down attacks | HIGH |
| E2 | OAuth2/OpenID Exploitation | Token leakage from callback URLs, scope escalation, redirect_uri bypass | HIGH |
| E3 | JWT Manipulation | Algorithm confusion (RS256→HS256), null signature, key confusion | HIGH |
| E4 | API Key Enumeration | Brute-force or guess API keys for scheme/Merchant endpoints | MEDIUM |
| E5 | mTLS Certificate Bypass | Test client certificate validation, CN mismatch, expired cert acceptance | MEDIUM |

### F. Tokenization & Encryption Testing (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| F1 | Token Vault Audit | Test tokenization API — enumerate tokens, test token→PAN reversibility | HIGH |
| F2 | Encryption Strength Testing | Test AES-256-GCM vs AES-128, CBC padding oracle, weak key derivation | HIGH |
| F3 | HSM Command Injection | Inject arbitrary commands into HSM interface if accessible | HIGH |
| F4 | Key Rotation Bypass | Test behavior during key rotation — find transactions processed with old key | MEDIUM |
| F5 | CVV/CVV2 Cracking | Test offline CVV generation if algorithm is derivable from captured data | LOW |

### G. PCI DSS & Compliance Testing (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| G1 | Full PCI-DSS Gap Assessment | Evaluate against PCI-DSS v4.0 12 requirements, identify gaps | HIGH |
| G2 | Card Data Discovery | Find unencrypted PANs in logs, memory dumps, DB backups | HIGH |
| G3 | Network Segmentation Testing | Verify cardholder data environment is isolated from general network | HIGH |
| G4 | Log Retention Audit | Verify transaction logs are retained ≥1 year, tamper-evident | MEDIUM |
| G5 | Incident Response Runbook | Test actual IRP execution time, communication chain, containment steps | MEDIUM |

### H. OSINT & Reconnaissance (5)
| # | Skill | Description | Priority |
|---|-------|-------------|----------|
| H1 | Merchant BIN Recon | Identify merchant BIN ranges, acquirer connections, scheme memberships | HIGH |
| H2 | Scheme Endpoint Mapping | Discover Visa Base I, MC Wire, Amex API endpoints via DNS/logs | HIGH |
| H3 | Certificate Transparency | Find issuer certificates, internal hostnames from CT logs | MEDIUM |
| H4 | Threat Intel Correlation | Correlate captured IOCs against known payment threat feeds | MEDIUM |
| H5 | Personnel Recon | Identify payment engineering staff from LinkedIn/GitHub for social engineering | LOW |

---

## Tools (27 Total)

### OSINT & Reconnaissance (5)
| # | Tool | Description |
|---|------|-------------|
| T1 | BIN Database Scanner | Query public BIN databases to map card ranges to issuers, card types |
| T2 | Scheme Endpoint Discovery | DNS enum, WHOIS, SSL cert enumeration for scheme connection endpoints |
| T3 | GitHub/Repo Scanner | Search for leaked API keys, connection strings, HSM credentials in repos |
| T4 | PCAP Network Analyzer | Deep packet analysis of captured ISO8583 flows to map transaction patterns |
| T5 | Threat Feed Aggregator | Aggregate feeds (VirusTotal, AlienVault, PCI Council IOCs) into usable format |

### Web Security Testing (5)
| # | Tool | Description |
|---|------|-------------|
| T6 | OWASP ZAP | Automated scanner for payment admin panels, REST endpoints, webhook URLs |
| T7 | SQLMap | Automated SQL injection detection and exploitation against payment DB fields |
| T8 | Burp Suite Pro | Intercept, modify, replay HTTP traffic for admin panel testing |
| T9 | XXE Tester | Inject XML entities into ISO20022 XML payloads to test XXE in parser |
| T10 | JWT Decoder/Forger | Decode, analyze, forge JWTs for auth bypass on payment APIs |

### Network & Infrastructure (5)
| # | Tool | Description |
|---|------|-------------|
| T11 | Wireshark/tshark | Decode ISO8583 over TCP, analyze protocol quirks, extract credentials |
| T12 | Nmap/NSE Scripts | Scan payment infrastructure, identify open ports, run ISO8583 probes |
| T13 | OpenSSL s_client | Test TLS configuration of scheme connections, test cipher suite negotiation |
| T14 | Scapy | Craft custom ISO8583 packets, inject malformed messages, test network filters |
| T15 | Masscan | Rapid port scanning of large IP ranges for payment endpoint discovery |

### Payment-Specific & Crypto (5)
| # | Tool | Description |
|---|------|-------------|
| T16 | ISO8583 Parser/Builder | Parse binary/ASCII messages, build custom messages, validate bitmaps |
| T17 | PIN Block Calculator | ISO9564 format translation, PIN block encryption/decryption under ZMK |
| T18 | MAC Generator/Verifier | ISO9797-1 M1/M2/M3 MAC generation and verification |
| T19 | HSM Command Tester | Test PayShield commands, verify key injection, check command allowlist |
| T20 | EMV Cryptogram Validator | Verify ARQC/ARPC generation, test offline data authentication |

### Forensic & Incident Response (4)
| # | Tool | Description |
|---|------|-------------|
| T21 | Log Correlation Engine | Correlate logs across Kafka, PostgreSQL, HSM, and SIEM for incident timelines |
| T22 | Memory Forensic Toolkit | Volatility plugins for payment application memory (find decrypted PANs) |
| T23 | SIEM Query Library | Pre-built Splunk/Elastic queries for payment attack pattern detection |
| T24 | RansomOps Simulator | Simulate ransomware encryption patterns on isolated backup systems |

---

## Bots (18 Total)

### Monitoring & Reconnaissance (5)
| # | Bot | Description |
|---|-----|-------------|
| B1 | Real-time Anomaly Detector | Monitor Kafka/RabbitMQ for TPS spikes, scheme timeout rate, HSM errors — alert to Slack/SIEM |
| B2 | Scheme Response Code Tracker | Track 2xx/5xx/timeout rates per scheme (Visa/MC/Amex), detect degradation |
| B3 | HSM Health Monitor | Monitor HSM command latency, error rates, queue depth — alert on threshold breach |
| B4 | Log完整性 Watchdog | Verify log files are being written, detect truncation or tampering |
| B5 | Certificate Expiry Watcher | Track TLS and client certificates approaching expiry (30/14/7 day warnings) |

### Automated Attack & Fuzzing (5)
| # | Bot | Description |
|---|-----|-------------|
| B6 | Continuous ISO8583 Fuzzer | Run A1/A4/A5 attack tools on loop, log crashes, report new findings |
| B7 | Replay Attack Loop | Continuously replay captured transactions with variations, test replay protection |
| B8 | Crypto Downgrade Tester | Scheduled crypto downgrade attacks against live scheme connections |
| B9 | Credential Stuffing Bot | Automated credential attacks on admin login endpoints |
| B10 | Rate Limit Probe | Continuous probing of API rate limits to find enumeration vectors |

### Intelligence & Compliance (4)
| # | Bot | Description |
|---|-----|-------------|
| B11 | BIN Intelligence Feed | Real-time BIN updates, flag high-risk BINs, new issuer alerts |
| B12 | Threat Intel Correlator | Correlate in-flight transactions against PCI Council IOCs and fraud feeds |
| B13 | Fraud Pattern Detector | ML-free rule-based detection: velocity, geography, amount anomalies |
| B14 | GDPR Data Subject Watchdog | Monitor that no PII leaks into logs or analytics pipelines |

### Reporting & Orchestration (4)
| # | Bot | Description |
|---|-----|-------------|
| B15 | Attack Summary Generator | Aggregate findings from all tools, generate executive + technical reports |
| B16 | Regulatory Report Bot | Auto-generate PCI-DSS compliance reports, incident reports for regulators |
| B17 | Executive Dashboard Bot | Push daily KPI summary (TPS, latency, error rates, alerts) to leadership |
| B18 | Remediation Tracker | Track finding → fix → verification lifecycle, auto-close resolved items |

---

## Attack Tool Specifications

### A1: Grammatical ISO8583 Mutator
```
Input: Valid ISO8583 message (hex or ASCII)
Process:
  1. Parse message into MTI, bitmap, DE fields
  2. For each DE, apply mutation rules:
     - Length mutations: 0, min-1, min, max-1, max, max+1
     - Encoding mutations: swap BCD↔ASCII if applicable
     - Content mutations: null bytes, special chars, overflow patterns
     - Bitmap mutations: flip each bit independently, add secondary bitmap
  3. Re-encode and send
  4. Log response + detect crash indicators
Output: Crash report (DE, mutation type, response, payload)
```

### A2: Replay Attack Engine
```
States: IDLE → CAPTURED → REPLAYING → VALIDATED/BLOCKED
  - Verbatim: same STAN, same timestamp, same amount
  - Increment STAN: +1, +100, +10000
  - Shift timestamp: -1s, -1min, +1min, +1hr
  - Amount shift: +0.01, -0.01, 2x, 0.5x
Detection mechanisms to test:
  - Duplicate STAN within time window (e.g., 5 min)
  - Timestamp out of range (e.g., ±24hr from server time)
  - Same card + same merchant within velocity window
  - Duplicate ARQC (if captured)
```

### A3: Cryptographic Downgrade Tester
```
Test cases:
  1. MAC strip: Remove DE64 entirely, send to issuer
  2. MAC zero: Replace MAC with 0x0000000000000000
  3. MAC weak: Replace with XOR of PAN bytes instead of DES output
  4. PIN format downgrade: F0 → F3 (removes PAN from block)
  5. PIN format strip: Remove DE52 PIN data entirely
  6. TLS downgrade: Offer only TLS 1.0 ciphers, test acceptance
  7. Certificate trust bypass: Send self-signed cert, test if rejected
Report: Attack ID, Original MAC, Modified MAC, Server Response, Status
```

### A4: Boundary Value Exploiter
```
For each DE with known length constraints:
  1. Generate: zero-length, 1 byte (if min>1), min-1, min, max-1, max, max+1
  2. For numeric fields: negative values, decimal overflow
  3. For date fields: past, future, leap year, Feb 30, invalid month
  4. For BCD fields: non-BCD hex (A-F values)
  5. For LLVAR/LLLVAR: underflow and overflow by 1 byte
Track: DE number, test value, response code, crash indicator
```

### A5: Protocol Fuzzer
```
Mutation strategies:
  - Single DE fuzz: Mutate one DE, hold others constant
  - Multi DE fuzz: Correlated mutations across related fields
  - Semantic fuzz: Invalid country codes, invalid currencies, invalid card brands
  - Encoding fuzz: ASCII in BCD field, BCD in ASCII field, null padding
  - Protocol state fuzz: Send financial MTI with reversal codes
Fuzz corpus stored in: assets/test_data/fuzzing_corpus/
```
