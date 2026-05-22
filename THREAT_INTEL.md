# THREAT_INTEL.md — Live Threat Feed + Correlation Engine

---

## Purpose

Every CVE, breach, and dark web mention is actionable intelligence. This file defines how threat data is collected, correlated, and turned into attack opportunities.

---

## Threat Feed Sources

### 1. NVD (National Vulnerability Database)
- **URL:** `https://services.nvd.nist.gov/rest/json/cves/2.0`
- **Refresh:** Daily at 06:00 UTC
- **Scope:** CVEs affecting payment technology stack
- **Filters:** CWE-79 (XSS), CWE-89 (SQLi), CWE-78 (Command Injection), CWE-287 (Auth Bypass)

### 2. Shodan Exploits
- **URL:** `https://exploits.shodan.io/`
- **Refresh:** Every 6 hours
- **Scope:** Exploits matching payment gateway fingerprints

### 3. Exploit-DB / SearchSploit
- **Command:** `searchsploit --u` (update) + `searchsploit <term>`
- **Refresh:** Weekly
- **Scope:** Local exploit database for identified tech stacks

### 4. Dark Web / Leak Forums
- **Source:** Monitored paste sites, breach forums, leak markets
- **Scope:** Payment gateway operator data, credential dumps, database leaks
- **Legal constraint:** Public data only, no active crawling of illegal markets

### 5. Certificate Transparency
- **Source:** `https://crt.sh/`, `https://transparencyreport.google.com/`
- **Scope:** New payment domain discovery
- **Trigger:** New cert for payment processor → new target → RECON queue

### 6. Payment Scheme Advisory Feeds
- **Visa CSP:** `https://www.visa.com/security/advisories/`
- **Mastercard MCS:** `https://developer.mastercard.com/`
- **PCI SSC:** `https://www.pcisecuritystandards.org/`
- **Scope:** Scheme-specific vulnerabilities and compliance requirements

---

## CVE Correlation Engine

When a new CVE is published:

```
1. Parse CVE metadata (CVE-ID, CVSS, CWE, affected versions)
2. Match against knowledge base — which targets use affected component?
3. If match found:
   a. Create/update knowledge/cve_tracker/<CVE-ID>.md
   b. Calculate priority impact: CVSS × AffectedTargets × ExploitAvailability
   c. If impact > 400: trigger HUNTER escalation for affected targets
   d. Alert Operator if P1
4. If no match: log in knowledge/cve_tracker/archive/ for future reference
```

---

## Breach Data Correlation

When breach data is discovered:

```
1. Identify affected organization/domains from breach data
2. Check knowledge/targets/ for existing profile
3. If exists:
   a. Update exposure_timeline.md with breach context
   b. Re-score target (breach often increases target value)
   c. Trigger HUNTER if P1-P2
4. If new:
   a. Create gateway profile from available breach data
   b. Run RECON scan cycle
   c. Add to targets/active/
```

---

## Threat Intel Output Format

Every threat intelligence entry in `knowledge/cve_tracker/<CVE-ID>.md`:

```markdown
# [CVE-ID] — [Product] — [Severity]

**Published:** [YYYY-MM-DD]
**CVSS:** [score] — [vector]
**CWE:** [CWE-ID] — [description]
**Affected:** [versions]
**Public Exploit:** [Yes/No — source link if Yes]
**Affected Targets:** [list from knowledge base]

## Intelligence Assessment

**Attack feasibility:** [High/Medium/Low]
**Primary vector:** [how it would be exploited]
**Payment relevance:** [None/Low/Medium/High/Critical]

## Response

- [ ] Targets using affected component identified
- [ ] RECON scan updated with CVE context
- [ ] HUNTER queued for affected targets
- [ ] Operator notified if P1
```

---

## Threat Feed Automation

```bash
# Daily (06:00 UTC)
python3 neopay/scripts/cve_tracker.py --fetch-nvd --correlate --alert

# Every 6 hours
python3 neopay/scripts/cve_tracker.py --shodan-exploits --update-registry

# Hourly
python3 neopay/scripts/ct_monitor.py --new-certs --payment-filter --queue-recon

# Weekly
searchsploit --u
python3 neopay/scripts/threat_report.py --weekly-summary --telegram
```

---

## Threat Score Calculation

```
ThreatScore = (CVSS × Exploitability × TargetValue × PaymentRelevance)

Exploitability:
  - Public PoC: 10
  - Exploit-DB: 7
  - NVD no PoC: 5
  - Theoretical: 2

TargetValue:
  - Enterprise gateway: 10
  - Mid-market processor: 7
  - Small merchant: 3
  - Demo/test: 1

PaymentRelevance:
  - Direct payment component: 10
  - Core infrastructure: 8
  - Supporting service: 5
  - Unrelated: 1

Thresholds:
  - 700+ = P1 CRITICAL — immediate HUNTER + Operator alert
  - 400-699 = P2 HIGH — HUNTER queue
  - 200-399 = P3 MEDIUM — monitor
  - <200 = P4/P5 — archive
```