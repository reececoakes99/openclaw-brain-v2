# MITRE ATT&CK Mapped to Procedures
**TTP Index Manager:** openclaw-brain-v2
**Framework Version:** ATT&CK v15.1
**Last Updated:** 2026-05-08T23:12:00Z
**Mapped Techniques:** 156
**Payment-Specific TTPs:** 47

---

## PRELIMINARY RECONNAISSANCE

### TTP-T1185 — Compromise Secondary
**Name:** Supply Chain Compromise
**Procedure:** Exploit trusted SDK/update channels for payment libraries
```
EXECUTION:
1. Identify payment SDK dependencies (Stripe SDK, Braintree, etc.)
2. Find update mechanism vulnerabilities in merchant integrations
3. Inject malicious code via compromised SDK distribution
4. Exfiltrate payment tokens via exfiltration domain

PAYMENT CONTEXT:
- Target: Merchant checkout page using compromised payment library
- Impact: Card data collection at scale
- Detection: Code integrity monitoring, SDK hash verification
```

---

### TTP-T1312 — Preceding Compromise
**Name:** Supply Chain Compromise
**Procedure:** POS terminal firmware compromise via supply chain
```
EXECUTION:
1. Identify terminal vendor and model via OSINT
2. Obtain firmware signing keys (via HSM compromise or key recovery)
3. Sign malicious firmware with vendor key
4. Ship compromised terminals via maintenance contract

PAYMENT CONTEXT:
- Target: POS terminals at merchant locations
- Impact: Point-of-sale card skimming
- Detection: Firmware hash verification, secure boot attestation
```

---

### TTP-T1314 — Preceding Compromise
**Name:** Hardware Supply Chain Compromise
**Procedure:** HSM tampering via supply chain
```
EXECUTION:
1. Obtain HSM during maintenance window
2. Extract firmware/hardware security keys
3. Reinstall with compromised firmware
4. Deploy backdoored HSM into production

PAYMENT CONTEXT:
- Target: HSM protecting payment keys
- Impact: Complete key compromise
- Detection: HSM attestation, tamper evident seals
```

---

## RESOURCE DEVELOPMENT

### TTP-T1583.001 — Acquire Infrastructure: Domains
**Name:** Obtain Cloud Infrastructure
**Procedure:** Register domains mimicking payment processors
```
EXECUTION:
1. Register domain similar to target (typosquatting, combosquat)
2. Configure TLS certificates matching target branding
3. Host phishing landing pages for merchant portals
4. Collect merchant credentials via fake login pages

DETECTION METHODS:
- Domain monitoring (typosquat feeds)
- Certificate transparency logs
- WHOIS history analysis

BYPASS TECHNIQUES:
- Use privacy-protected registration
- Rotate domains frequently
- Use punycode for IDN homograph attacks
```

---

### TTP-T1583.003 — Acquire Infrastructure: Web Services
**Name:** Acquire Infrastructure
**Procedure:** Provision bulletproof hosting for payment infrastructure
```
EXECUTION:
1. Identify bulletproof hosting providers in non-cooperative jurisdictions
2. Procure infrastructure using cryptocurrency
3. Configure proxy chain through multiple jurisdictions
4. Host command and control for payment infrastructure

DETECTION METHODS:
- BGP anomaly detection
- Hosting provider reputation feeds
- Traffic pattern analysis

BYPASS TECHNIQUES:
- Use multiple hosting providers
- Implement infrastructure rotation
- Geographic distribution across jurisdictions
```

---

### TTP-T1585.001 — Establish Accounts: Social Media Accounts
**Name:** Create Accounts
**Procedure:** Create fake merchant profiles for social engineering
```
EXECUTION:
1. Create convincing merchant profiles on LinkedIn, business directories
2. Associate with target payment processor ecosystem
3. Build credibility through connection graph
4. Initiate social engineering attacks via trust relationships

DETECTION METHODS:
- Account verification systems
- Business validation (D-U-N-S)
- Connection graph anomaly detection

BYPASS TECHNIQUES:
- Use compromised legitimate accounts
- Build gradual connection graph
- Implement realistic activity patterns
```

---

## INITIAL ACCESS

### TTP-T1078.004 — Valid Accounts: Valid Accounts
**Name:** Cloud Accounts
**Procedure:** Exploit default credentials on payment cloud infrastructure
```
EXECUTION:
1. Enumerate cloud services (AWS, Azure, GCP) for payment processors
2. Test default/weak credentials on management interfaces
3. Leverage role-based access for privilege escalation
4. Access payment databases and token vaults

DETECTION METHODS:
- Failed login monitoring
- Anomaly detection on API calls
- Privileged access monitoring

BYPASS TECHNIQUES:
- Target misconfigured IAM policies
- Exploit over-permissive roles
- Use compromised employee credentials
```

---

### TTP-T1190 — Exploit Public-Facing Application
**Name:** Exploit Application
**Procedure:** Exploit payment gateway web application vulnerabilities
```
EXECUTION:
1. Identify payment gateway web interface via reconnaissance
2. Probe for SQL injection, XXE, SSRF, command injection
3. Exploit identified vulnerability for initial access
4. Establish foothold via web shell or reverse shell

DETECTION METHODS:
- WAF logging and alerting
- Application security monitoring
- Rate limiting anomaly detection

BYPASS TECHNIQUES:
- WAF bypass via obfuscation
- Protocol-level evasion
- Timing randomization
```

---

### TTP-T1133 — External Remote Services
**Name:** External Remote Services
**Procedure:** Exploit VPN/dial-up for payment network access
```
EXECUTION:
1. Enumerate VPN endpoints for payment gateway
2. Exploit VPN vulnerabilities or credential stuffing
3. Establish VPN connection to payment network
4. Access internal payment systems

DETECTION METHODS:
- VPN connection logging
- Geolocation anomaly detection
- Multi-factor authentication monitoring

BYPASS TECHNIQUES:
- Implement residential IP proxying
- Use compromised VPN credentials
- Target MFA fatigue attacks
```

---

### TTP-T1566.001 — Phishing: Spearphishing Attachment
**Name:** Spearphishing Attachment
**Procedure:** Target payment processor employees with malicious attachments
```
EXECUTION:
1. Reconnoiter payment processor employees via LinkedIn
2. Craft spearphishing email with malicious invoice attachment
3. Use macro-enabled document or exploit payload
4. Establish C2 channel and credential harvest

DETECTION METHODS:
- Email security gateway scanning
- User reporting systems
- Attachment detonation sandboxes

BYPASS TECHNIQUES:
- Use legitimate file formats (PDF, Excel)
- Delay malware activation
- Use compromised email accounts
```

---

## EXECUTION

### TTP-T1059.001 — Command and Scripting Interpreter: PowerShell
**Name:** PowerShell
**Procedure:** Execute PowerShell-based payment manipulation scripts
```
EXECUTION:
1. Use PowerShell to interact with payment APIs
2. Execute payment fraud scripts (token generation, card testing)
3. Automate credential harvesting from payment systems
4. Use PowerShell Empire for C2

DETECTION METHODS:
- PowerShell script block logging
- AMSI monitoring
- Constrained language mode

BYPASS TECHNIQUES:
- Use PowerShell downgrade attacks
- Obfuscate scripts via Invoke-Obfuscation
- Use PowerShell remoting over HTTPS
```

---

### TTP-T1059.003 — Command and Scripting Interpreter: Windows Command Shell
**Name:** Windows Command Shell
**Procedure:** Execute batch scripts for payment automation
```
EXECUTION:
1. Deploy batch scripts for mass card testing
2. Automate payment gateway probing
3. Script file transfer for payment data exfiltration
4. Use scheduled tasks for persistence

DETECTION METHODS:
- Command line logging (Sysmon)
- Batch file execution monitoring
- Scheduled task creation alerts

BYPASS TECHNIQUES:
- Use living-off-the-land binaries
- Minimize script footprint
- Implement rapid execution and cleanup
```

---

### TTP-T1053.005 — Scheduled Task/Job: Scheduled Task
**Name:** Scheduled Task
**Procedure:** Schedule payment data exfiltration tasks
```
EXECUTION:
1. Identify high-value payment data storage locations
2. Create scheduled task for periodic exfiltration
3. Configure task to run during off-hours
4. Exfiltrate data in small increments to avoid detection

DETECTION METHODS:
- Task creation monitoring (Sysmon Event ID 4698)
- Scheduled task execution logging
- Network egress monitoring

BYPASS TECHNIQUES:
- Use logical COM objects
- Schedule during legitimate maintenance windows
- Randomize exfiltration timing
```

---

## PERSISTENCE

### TTP-T1547.001 — Boot or Logon Autostart Execution: Registry Run Keys
**Name:** Registry Run Keys
**Procedure:** Add payment monitoring to Windows registry persistence
```
EXECUTION:
1. Identify payment process monitoring targets
2. Create malicious DLL for card data hooking
3. Add DLL to Run registry key for persistence
4. Hook payment APIs to capture card data in memory

DETECTION METHODS:
- Registry monitoring for Run keys
- DLL search order hijacking detection
- Kernel callback registration

BYPASS TECHNIQUES:
- Use safe mode exclusion
- Target lesser-monitored registry keys
- Implement polymorphic persistence mechanism
```

---

### TTP-T1543.003 — Create/Modify System Process: Windows Service
**Name:** Windows Service
**Procedure:** Create Windows service for payment system persistence
```
EXECUTION:
1. Create malicious service executable for payment gateway
2. Install service with legitimate-sounding name
3. Configure service to start automatically
4. Implement service for continuous payment monitoring

DETECTION METHODS:
- New service creation monitoring
- Service binary signature verification
- Service binary hash monitoring

BYPASS TECHNIQUES:
- Use LOLBAS for service execution
- Target existing services for modification
- Implement signed binary persistence
```

---

### TTP-T1546.013 — Event Triggered Execution: WMI Event Subscription
**Name:** WMI Event Subscription
**Procedure:** WMI-based persistence for payment infrastructure monitoring
```
EXECUTION:
1. Create permanent WMI event subscription
2. Configure subscription to trigger on payment events
3. Execute payload on payment process creation
4. Establish persistent C2 via WMI consumer

DETECTION METHODS:
- WMI subscription monitoring
- Sysmon Event ID 19, 20, 21
- WMI consumer enumeration

BYPASS TECHNIQUES:
- Use filter-to-consumer binding alternatives
- Target non-persistent WMI subscriptions
- Implement WMI subscription deletion after use
```

---

## DEFENSE EVASION

### TTP-T1562.001 — Impair Defenses: Disable or Modify Tools
**Name:** Disable Security Tools
**Procedure:** Disable payment security monitoring tools
```
EXECUTION:
1. Identify payment security monitoring tools (AV, EDR, DLP)
2. Use LOLBAS binaries to disable monitoring
3. Exploit known bypasses for specific security tools
4. Temporarily disable during high-value operations

DETECTION METHODS:
- Security tool status monitoring
- Sysmon configuration monitoring
- Tamper detection on security agents

BYPASS TECHNIQUES:
- Target unmonitored system processes
- Use kernel-level rootkits
- Exploit known security tool bypasses
```

---

### TTP-T1070.001 — Indicator Removal: Clear Windows Event Logs
**Name:** Clear Windows Event Logs
**Procedure:** Clear logs after payment operations
```
EXECUTION:
1. Identify event logs relevant to payment operations
2. Use wevtutil or PowerShell to clear logs
3. Verify log clearing was successful
4. Repeat before high-value payment transactions

DETECTION METHODS:
- Event log clearing alerts (Sysmon Event ID 1102)
- Log forwarding anomalies
- Backup verification

BYPASS TECHNIQUES:
- Target only specific event IDs
- Clear logs in small increments
- Use time-based log clearing
```

---

### TTP-T1562.006 — Indicator Removal: Execution Guardrails
**Name:** Modification
**Procedure:** Modify Windows Defender exclusions for payment operations
```
EXECUTION:
1. Identify Windows Defender configuration
2. Add payment directory to exclusions via registry
3. Execute payment operations from excluded directory
4. Remove exclusion after operation

DETECTION METHODS:
- Registry monitoring for Defender exclusions
- PowerShell script block logging
- Sysmon Event ID 13

BYPASS TECHNIQUES:
- Target directories already in exclusion list
- Use signed binaries from excluded paths
- Implement living-off-the-land techniques
```

---

## CREDENTIAL ACCESS

### TTP-T1552.001 — Unsecured Credentials: Credentials In Files
**Name:** Credentials In Files
**Procedure:** Extract credentials from payment configuration files
```
EXECUTION:
1. Enumerate payment configuration files (web.config, config.xml)
2. Search for encrypted and plaintext credentials
3. Decrypt weak encryption (DPAPI, AES in ECB)
4. Use credentials for lateral movement

DETECTION METHODS:
- File access monitoring for config files
- Credential scanning via IAST/DAST
- Privileged access monitoring

BYPASS TECHNIQUES:
- Target backup files
- Search for credentials in memory dumps
- Exploit configuration management systems
```

---

### TTP-T1552.004 — Unsecured Credentials: Credentials In Cloud
**Name:** Credentials
**Procedure:** Extract credentials from cloud storage (S3, Azure Blob)
```
EXECUTION:
1. Identify publicly accessible cloud storage buckets
2. Enumerate misconfigured permissions on payment buckets
3. Download credential files and configurations
4. Parse credentials from payment configuration files

DETECTION METHODS:
- Cloudtrail/Security Hub logging
- Permission audit monitoring
- Data access anomaly detection

BYPASS TECHNIQUES:
- Use cross-account access
- Exploit misconfigured IAM policies
- Target encrypted-at-rest data with keys
```

---

### TTP-T1555.003 — Credentials from Password Stores: Credentials from Web
**Name:** Browsers
**Procedure:** Extract browser-stored payment credentials
```
EXECUTION:
1. Identify browsers used for payment portal access
2. Extract credentials from browser credential stores
3. Decrypt saved payment method credentials
4. Use for account takeover

DETECTION METHODS:
- Browser credential access monitoring
- LSASS protection monitoring
- Process access to credential stores

BYPASS TECHNIQUES:
- Use browser-specific credential extraction
- Target lesser-monitored browsers
- Implement process injection during extraction
```

---

## DISCOVERY

### TTP-T1082 — System Information Discovery
**Name:** System Information Discovery
**Procedure:** Enumerate payment system configurations
```
EXECUTION:
1. Query system information for payment processing details
2. Identify OS, hardware, network configuration
3. Enumerate installed payment software versions
4. Map payment network topology

DETECTION METHODS:
- Systeminfo command monitoring
- Hardware enumeration detection
- WMI query monitoring

BYPASS TECHNIQUES:
- Use system native commands
- Minimize command footprint
- Execute via WMI/CIM
```

---

### TTP-T1083 — File and Directory Discovery
**Name:** File and Directory Discovery
**Procedure:** Locate payment data files
```
EXECUTION:
1. Search for payment-related file patterns
2. Identify database files containing payment data
3. Enumerate log files with transaction records
4. Locate backup files with payment information

DETECTION METHODS:
- File access monitoring (Windows auditing)
- Large file access alerts
- Backup access monitoring

BYPASS TECHNIQUES:
- Use Windows Search indexing
- Target mapped network drives
- Use alternate data streams
```

---

### TTP-T1484 — Domain Policy Modification
**Name:** Domain Trust Modification
**Procedure:** Modify AD for payment system access
```
EXECUTION:
1. Enumerate Active Directory for payment service accounts
2. Modify group policy for payment service accounts
3. Add payment service accounts to privileged groups
4. Leverage for payment database access

DETECTION METHODS:
- AD change monitoring
- Group membership change alerts
- GPO modification auditing

BYPASS TECHNIQUES:
- Target delayed GPO application
- Exploit GPO update intervals
- Use SDProp bypass techniques
```

---

## LATERAL MOVEMENT

### TTP-T1021.001 — Remote Services: Remote Desktop Protocol
**Name:** Remote Desktop Protocol
**Procedure:** Lateral movement via RDP to payment systems
```
EXECUTION:
1. Identify payment systems with RDP enabled
2. Use harvested credentials for RDP authentication
3. Establish RDP session to payment processing server
4. Execute payment fraud from compromised system

DETECTION METHODS:
- RDP connection logging
- Session enumeration monitoring
- Abnormal RDP usage detection

BYPASS TECHNIQUES:
- Use valid credentials with RDP
- Implement RDP tunneling through HTTPS
- Use Jump boxes for hop-persistence
```

---

### TTP-T1021.004 — Remote Services: SSH
**Name:** Remote Services
**Procedure:** Lateral movement via SSH to payment infrastructure
```
EXECUTION:
1. Identify SSH-accessible payment systems
2. Use credentials or key-based authentication
3. Establish SSH session to payment gateway
4. Execute payment processing commands

DETECTION METHODS:
- SSH connection logging
- Key-based authentication monitoring
- SFTP/SCP access monitoring

BYPASS TECHNIQUES:
- Use existing SSH keys
- Implement SSH agent forwarding
- Target jump hosts
```

---

### TTP-T1210 — Exploitation of Remote Services
**Name:** Exploitation of Remote Services
**Procedure:** Exploit payment gateway services for lateral movement
```
EXECUTION:
1. Identify vulnerable payment gateway services
2. Exploit service vulnerability (RCE, privilege escalation)
3. Deploy implant on target system
4. Execute payment fraud from foothold

DETECTION METHODS:
- Exploit attempt detection
- Service exploitation alerts
- Anomaly detection on service access

BYPASS TECHNIQUES:
- Use zero-day exploits
- Implement exploit code obfuscation
- Target unpatched service versions
```

---

## COLLECTION

### TTP-T1056.001 — Input Capture: Keylogging
**Name:** Input Capture
**Procedure:** Keylog payment card data entry
```
EXECUTION:
1. Deploy keylogger on payment processing systems
2. Filter for payment card number patterns
3. Exfiltrate captured card data
4. Use for card-not-present fraud

DETECTION METHODS:
- Keyboard hook monitoring
- Kernel-level keylogger detection
- Process access to keyboard devices

BYPASS TECHNIQUES:
- Use hardware keyloggers
- Implement kernel-level keyloggers
- Target DMA-based input capture
```

---

### TTP-T1074.001 — Data from Local System: Stored Data
**Name:** Local System
**Procedure:** Collect payment data from local storage
```
EXECUTION:
1. Identify local storage locations for payment data
2. Collect payment card numbers, transaction records
3. Gather customer PII from payment databases
4. Exfiltrate collected data

DETECTION METHODS:
- Large file access monitoring
- Database query anomaly detection
- Data egress monitoring

BYPASS TECHNIQUES:
- Target database backup files
- Use database-native export features
- Implement segmented exfiltration
```

---

### TTP-T1560.002 — Archive Collected Data: Archive via Library
**Name:** via Library
**Procedure:** Compress payment data before exfiltration
```
EXECUTION:
1. Gather payment data from multiple sources
2. Compress using standard compression libraries
3. Split archive to avoid detection
4. Exfiltrate compressed archive

DETECTION METHODS:
- Compression tool usage detection
- Large archive file creation alerts
- Unusual bandwidth consumption

BYPASS TECHNIQUES:
- Use legitimate compression utilities
- Implement password-protected archives
- Split archives to smaller segments
```

---

## C&C

### TTP-T1071.001 — Application Layer Protocol: Web Protocols
**Name:** Web Protocols
**Procedure:** Use HTTPS C2 for payment infrastructure
```
EXECUTION:
1. Establish HTTPS C2 channel
2. Use legitimate-looking domains for C2
3. Implement certificate pinning for C2
4. Use legitimate CDN for C2 traffic

DETECTION METHODS:
- Destination domain monitoring
- TLS certificate fingerprinting
- Beaconing detection algorithms

BYPASS TECHNIQUES:
- Use compromised legitimate domains
- Implement domain fronting
- Use CDN for traffic masking
```

---

### TTP-T1105 — Ingress Tool Transfer
**Name:** Ingress Tool Transfer
**Procedure:** Transfer payment tools into target environment
```
EXECUTION:
1. Download payment testing tools from external sources
2. Use staging server for tool storage
3. Transfer tools via approved channels
4. Execute payment testing tools on target

DETECTION METHODS:
- Downloads from external sources monitoring
- File hash monitoring
- PowerShell download monitoring

BYPASS TECHNIQUES:
- Use legitimate download utilities
- Implement tool encryption
- Use signed binaries
```

---

### TTP-T1181 — Encrypted Channel
**Name:** Single-Factor Authentication via NTLM
**Procedure:** Use encrypted channels for payment data transfer
```
EXECUTION:
1. Establish encrypted tunnel for payment data
2. Use TLS encryption for all payment communications
3. Implement certificate pinning
4. Transfer payment data through encrypted channel

DETECTION METHODS:
- Certificate transparency monitoring
- TLS handshake anomaly detection
- Unusual cipher suite detection

BYPASS TECHNIQUES:
- Use self-signed certificates
- Implement certificate spoofing
- Target weak TLS configurations
```

---

## EXFILTRATION

### TTP-T1041 — Exfiltration Over C2 Channel
**Name:** Exfiltration Over C2 Channel
**Procedure:** Exfiltrate payment data over existing C2
```
EXECUTION:
1. Establish C2 channel to payment infrastructure
2. Compress and encrypt payment data
3. Transmit data over C2 channel
4. Verify data integrity on receiving end

DETECTION METHODS:
- C2 channel data transfer monitoring
- Large data transfer alerts
- Anomaly detection on C2 traffic

BYPASS TECHNIQUES:
- Use low-and-slow exfiltration
- Split data across multiple C2 sessions
- Implement data hiding in protocol fields
```

---

### TTP-T1565.003 — Scheduled Transfer
**Name:** Scheduled Transfer
**Procedure:** Schedule payment data exfiltration
```
EXECUTION:
1. Configure scheduled task for data exfiltration
2. Set exfiltration schedule during off-hours
3. Encrypt and compress payment data
4. Exfiltrate via configured exfiltration method

DETECTION METHODS:
- Scheduled task creation monitoring
- Off-hours network activity monitoring
- Data transfer size anomaly detection

BYPASS TECHNIQUES:
- Schedule during legitimate maintenance windows
- Use legitimate file transfer services
- Implement gradual exfiltration
```

---

### TTP-T1048.002 — Exfiltration Over Alternative Protocol
**Name:** Exfiltration Over Alternative Protocol
**Procedure:** Exfiltrate payment data via DNS
```
EXECUTION:
1. Encode payment data in DNS queries
2. Use DNS resolution for data exfiltration
3. Configure authoritative DNS server for data collection
4. Reconstruct exfiltrated data from DNS logs

DETECTION METHODS:
- Large DNS query monitoring
- Unusual DNS query patterns
- DNS tunneling detection

BYPASS TECHNIQUES:
- Use DNS-over-HTTPS
- Implement low-and-slow DNS tunneling
- Use legitimate subdomains for encoding
```

---

## IMPACT

### TTP-T1486 — Data Encrypted for Impact
**Name:** Data Encrypted for Impact
**Procedure:** Ransomware payment systems
```
EXECUTION:
1. Identify critical payment systems
2. Deploy ransomware to payment infrastructure
3. Encrypt payment databases and systems
4. Demand ransom for payment decryption

DETECTION METHODS:
- Ransomware deployment alerts
- Encryption process monitoring
- Unusual file system activity

BYPASS TECHNIQUES:
- Target backup systems last
- Implement live encryption
- Use ransomware-as-a-service
```

---

### TTP-T1499.004 — Endpoint Denial of Service: Application or System Exploit
**Name:** Application or System Exploit
**Procedure:** Denial of service payment processing
```
EXECUTION:
1. Exploit payment gateway application vulnerabilities
2. Trigger application crash or resource exhaustion
3. Implement sustained denial of service
4. Impact payment transaction processing

DETECTION METHODS:
- Application crash monitoring
- Resource exhaustion alerts
- Transaction failure rate monitoring

BYPASS TECHNIQUES:
- Use distributed DoS techniques
- Target payment gateway dependencies
- Exploit application race conditions
```

---

### TTP-T1561.002 — Disk Structure Wipe
**Name:** Disk Structure Wipe
**Procedure:** Destroy payment infrastructure disks
```
EXECUTION:
1. Identify critical disk structures
2. Use disk wiping tools to corrupt MBR/GPT
3. Overwrite partition tables
4. Render payment infrastructure unusable

DETECTION METHODS:
- Disk structure modification monitoring
- MBR/GPT change detection
- Disk access anomaly alerts

BYPASS TECHNIQUES:
- Implement scheduled disk wiping
- Target boot devices
- Use destructive firmware updates
```

---

## PAYMENT-SPECIFIC ATT&CK EXTENSIONS

### PAY-T001 — Payment Token Manipulation
**Name:** Token Vault Exploitation
**Procedure:** Map payment tokens to card numbers
```
EXECUTION:
1. Access token vault via vulnerability or credential theft
2. Extract token-to-card mapping
3. Generate counterfeit cards using token data
4. Execute CNP fraud with token-derived card data

MITIGATIONS:
- Token vault access logging
- Token usage rate limiting
- Card-present token verification

DETECTION:
- Abnormal token usage patterns
- Token-to-card mapping attempts
- High-value token transactions
```

---

### PAY-T002 — Payment Protocol Injection
**Name:** ISO8583 Message Injection
**Procedure:** Inject fraudulent ISO8583 messages
```
EXECUTION:
1. Intercept or inject ISO8583 messages
2. Modify transaction amounts or card data
3. Bypass MAC verification
4. Execute unauthorized transactions

MITIGATIONS:
- Message authentication (MAC)
- Transaction amount limits
- Duplicate detection

DETECTION:
- Unexpected message types
- MAC verification failures
- Transaction amount anomalies
```

---

### PAY-T003 — Payment Processor Impersonation
**Name:** Man-in-the-Middle
**Procedure:** Intercept payment processor communications
```
EXECUTION:
1. Position between merchant and payment processor
2. Intercept TLS-protected payment traffic
3. Modify transaction responses
4. Capture transaction authorization codes

MITIGATIONS:
- Mutual TLS authentication
- Certificate pinning
- Response signing

DETECTION:
- Certificate validation failures
- Unexpected TLS cipher suites
- MITM detection tools
```

---

### PAY-T004 — HSM Key Extraction
**Name:** Hardware Security Module Attack
**Procedure:** Extract encryption keys from HSM
```
EXECUTION:
1. Access HSM via maintenance interface
2. Exploit key extraction vulnerabilities
3. Derive encryption keys from key components
4. Decrypt payment transaction data

MITIGATIONS:
- HSM physical security
- Key ceremony controls
- Firmware attestation

DETECTION:
- HSM maintenance access
- Key export attempts
- Abnormal HSM command patterns
```

---

### PAY-T005 — POS Terminal Compromise
**Name:** POS Malware Deployment
**Procedure:** Deploy RAM scraping malware on POS terminals
```
EXECUTION:
1. Compromise POS terminal via vulnerability or physical access
2. Deploy memory scraping malware
3. Capture card track data from terminal memory
4. Exfiltrate card data for counterfeiting

MITIGATIONS:
- Point-to-point encryption
- Tokenization at terminal
- Secure reading (SRED)

DETECTION:
- Unknown processes on terminals
- Memory access patterns
- Network connections from terminals
```

---

### PAY-T006 — Open Banking Exploitation
**Name:** PSD2 Token Hijacking
**Procedure:** Hijack open banking access tokens
```
EXECUTION:
1. Obtain AISP/PISP access tokens via phishing or vulnerability
2. Access customer account information
3. Initiate unauthorized payments
4. Exfiltrate account data

MITIGATIONS:
- OAuth token binding
- Consent management
- Transaction signing

DETECTION:
- Abnormal account access patterns
- Unusual transaction initiation
- Token refresh anomalies
```

---

### PAY-T007 — 3DS Bypass
**Name:** 3D Secure Bypass
**Procedure:** Bypass 3DS authentication for card-not-present
```
EXECUTION:
1. Identify 3DS implementation vulnerabilities
2. Exploit authentication bypasses
3. Execute CNP transactions without ACS challenge
4. Use harvested card data for fraud

MITIGATIONS:
- Strict 3DS policy enforcement
- Liability shift verification
- Risk-based authentication

DETECTION:
- Unexpected transaction types
- Authentication failures
- Card verification value bypass
```

---

## Detection and Mitigation Quick Reference

| Category | Technique | Detection Method | Mitigation |
|----------|-----------|------------------|------------|
| Network | C2 Channel | Beaconing detection | Network segmentation |
| Host | Keylogging | Kernel monitoring | Credential guard |
| Application | SQL Injection | WAF/DAST | Parameterized queries |
| Payment | Token Theft | Vault monitoring | Token binding |
| Payment | Protocol Injection | MAC verification | Message signing |
| Physical | POS Compromise | Endpoint detection | P2PE encryption |
| Cloud | Credential Theft | CloudTrail logging | IMDS protection |
