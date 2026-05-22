# EVIDENCE_CHAIN.md — Defensible Evidence Protocol

---

## Why It Matters

Every finding must be defensible — if Reece ever needs to explain how a vulnerability was discovered, evidence must prove it was authorized, methodical, and within scope. This protocol ensures clean chain of custody.

---

## Evidence Categories

| Category | Description | Examples |
|---|---|---|
| **A — Critical** | Direct proof of exploitation success | Access confirmation, data retrieved, shell obtained |
| **B — High** | Technical proof of vulnerability | Screenshot of injection, CVE PoC, error output |
| **C — Medium** | Supporting technical evidence | Port scan output, HTTP headers, technology fingerprint |
| **D — Low** | Context and correlation | WHOIS data, ASN info, historical timeline |

---

## Evidence File Naming

Format: `YYYY-MM-DD_HHMMSS_[category]_[type]_[target]_[description].[ext]`

Examples:
```
2026-05-08_143022_A_shell_confirmation_paymentgw.local_pwn.txt
2026-05-08_143045_B_sqli_error_output_paymentgw.local_union.txt
2026-05-08_142830_C_nmap_scan_paymentgw.local_443.txt
2026-05-08_142000_D_whois_registration_paymentgw.com.txt
```

---

## Required Fields Per Evidence File

Every evidence file must contain a header:

```markdown
---
Evidence ID: [UUID]
Collected: [YYYY-MM-DD HH:MM:SS UTC]
Target: [target domain/IP]
Category: [A/B/C/D]
Type: [screenshot/log/pcap/code/config/hashdump/other]
Engagement ID: [elkin-YYYYMMDD-xxx-###]
Collector: Elkin v2 (openclaw-brain-v2)
Authorization: [engagement_config scope reference]
Tool: [tool name + version]
Hash (SHA256): [hash of original file]
Sanitized: [yes/no — if no, reason]
---
```

---

## Chain of Custody Log

Maintain `knowledge/gateway_profiles/<target>/evidence/chain_of_custody.json`:

```json
[
  {
    "action": "evidence_collected",
    "timestamp": "2026-05-08T14:30:22Z",
    "evidence_id": "[UUID]",
    "file": "[filename]",
    "collector": "RECON bot"
  },
  {
    "action": "evidence_reviewed",
    "timestamp": "2026-05-08T14:35:00Z",
    "evidence_id": "[UUID]",
    "reviewer": "Elkin",
    "findings": "Valid — represents confirmed access"
  },
  {
    "action": "evidence_sanitized",
    "timestamp": "2026-05-08T14:40:00Z",
    "evidence_id": "[UUID]",
    "sanitizer": "OPSEC script",
    "changes": "IP addresses redacted to /24, PII removed"
  },
  {
    "action": "evidence_committed",
    "timestamp": "2026-05-08T15:00:00Z",
    "evidence_id": "[UUID]",
    "git_commit": "[hash]",
    "pushed_to": "reececoakes99/openclaw-brain-v2"
  }
]
```

---

## Timestamping Requirements

- All timestamps in UTC
- Use ISO 8601 format: `YYYY-MM-DDTHH:MM:SSZ`
- System clock must be accurate — sync with NTP regularly
- For protocol evidence (PCAP files): include absolute timestamp from packet capture
- For log files: include system time from log header

---

## What To Preserve

**Always capture for every exploit:**
1. Full command/script used (exact version)
2. Target response (raw output, unedited)
3. Timestamp (UTC, precise to second)
4. Network trace if available (PCAP)
5. Screenshot if UI involved
6. Hash of original unmodified capture

**Always capture for data access:**
1. Exact data accessed (file listing, query results)
2. Access method (how access was obtained)
3. Time of access
4. Scope of data (how many records, what types)
5. Verification hash of data

---

## What NOT To Include In Evidence

- Raw PII (real names, real card numbers, real addresses)
- Credentials that could be used to access live systems
- Evidence that could harm individuals if released
- Any data that could violate privacy laws outside authorized scope

---

## Post-Engagement Evidence Review

Before finalizing engagement package:

1. Verify every evidence file has required header
2. Verify chain_of_custody.json is complete
3. Run sanitization check on all files
4. Verify SHA256 hashes match collected files
5. Confirm no PII in any committed file
6. Generate evidence package manifest

---

## Legal Defensibility Checklist

- [ ] Target was in `engagement_config.json` authorized_domains
- [ ] Operator approved engagement (explicit or documented implicit)
- [ ] All actions scoped to authorization boundaries
- [ ] No actions taken outside defined rules of engagement
- [ ] Evidence preserved immediately upon discovery
- [ ] Evidence not modified after collection (hash verification)
- [ ] Chain of custody documented from collection to report
- [ ] Sanitization applied before any git push
- [ ] Final report reflects actual findings accurately