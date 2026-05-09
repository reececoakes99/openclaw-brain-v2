# TARGET SCORING — Priority Algorithm

## Scoring Philosophy

Every discovered payment gateway gets scored ruthlessly. The score determines where it goes in the queue and how fast it gets worked. High score = fast action. Low score = archived.

Score is not static. It updates every time new intel arrives.

---

## Scoring Formula

```
Priority Score = (ThreatSurface × 0.30) + (Exploitability × 0.25) + (TargetValue × 0.25) + (ExposureLevel × 0.20)
```

**Final Score Range: 0-1000**

Weight justification:
- ThreatSurface (30%): How dangerous are the known vulnerabilities?
- Exploitability (25%): How hard is it to exploit?
- TargetValue (25%): What's the payoff if we compromise it?
- ExposureLevel (20%): How accessible is it?

---

## Factor Scoring

### ThreatSurface (1-10)

How exposed and vulnerable is this target?

| Score | Classification | Indicators |
|---|---|---|
| **10** | CRITICAL | RCE confirmed, admin panel open, known active exploits |
| **9** | CRITICAL | Remote code injection potential, unauthenticated access |
| **8** | HIGH | SQL injection confirmed, command injection potential |
| **7** | HIGH | Authenticated RCE possible, privilege escalation easy |
| **6** | MEDIUM | XSS/SSRF confirmed, limited impact |
| **5** | MEDIUM | Business logic flaws identified, requires chaining |
| **4** | LOW-MEDIUM | Information disclosure, weak crypto identified |
| **3** | LOW | Minor misconfigurations, hardened target |
| **2** | LOW | Standard hardening present, no immediate risk |
| **1** | MINIMAL | Fully patched, WAF/IPS active, isolated, secured |

Scoring checklist:
- [ ] RCE/exec vulnerabilities confirmed?
- [ ] Admin panel exposed without auth?
- [ ] SQL injection present?
- [ ] Command injection possible?
- [ ] XSS/SSRF/LFI confirmed?
- [ ] Default credentials found?
- [ ] Outdated software with known CVEs?
- [ ] Business logic vulnerabilities?
- [ ] Information disclosure?
- [ ] Crypto weaknesses?
- [ ] Misconfigurations?

### Exploitability (1-10)

How easy is it to actually exploit?

| Score | Classification | Indicators |
|---|---|---|
| **10** | TRIVIAL | Public PoC exploit, no auth, works first try |
| **9** | TRIVIAL | Known exploit, slight modification needed |
| **8** | EASY | Tooling available, tested technique, reliable |
| **7** | EASY | Known approach, reliable results with effort |
| **6** | MEDIUM | Requires custom approach, moderate reliability |
| **5** | MEDIUM | Custom exploit needed, testing required |
| **4** | HARD | Deep knowledge required, complex chain |
| **3** | HARD | Multiple conditions must align |
| **2** | VERY HARD | Academic exploit, theoretical only |
| **1** | THEORETICAL | Virtually unexploitable in practice |

Scoring checklist:
- [ ] Public PoC available?
- [ ] Existing tooling works directly?
- [ ] Technique documented and tested?
- [ ] Custom modifications needed?
- [ ] Can be reliably replicated?
- [ ] Requires specific conditions?
- [ ] Chaining multiple vulns required?
- [ ] Zero-day required?

### TargetValue (1-10)

What's the operational value of compromising this target?

| Score | Classification | Indicators |
|---|---|---|
| **10** | ENTERPRISE | Major processor, thousands of merchants, high-value data |
| **9** | ENTERPRISE | Payment switch/aggregator, bulk transaction data |
| **8** | HIGH | Mid-market gateway, hundreds of merchants |
| **7** | HIGH | Specialized gateway (crypto, high-risk, international) |
| **6** | MEDIUM | Regional processor, tens of thousands of transactions |
| **5** | MEDIUM | Small gateway, dozens of merchants |
| **4** | LOW-MEDIUM | Individual high-value merchant |
| **3** | LOW | Individual standard merchant |
| **2** | LOW | Demo/test environment |
| **1** | MINIMAL | Honeypot/lab environment |

Scoring checklist:
- [ ] Processor/aggregator (thousands of merchants)?
- [ ] High transaction volume (millions/year)?
- [ ] Enterprise-level customers?
- [ ] High-value data (card data, PII, financial)?
- [ ] Token vault accessible?
- [ ] HSM integration (master keys)?
- [ ] Multiple integrations (bank connections)?
- [ ] Cross-border transactions?
- [ ] High-risk merchant categories?

### ExposureLevel (1-10)

How accessible is this target right now?

| Score | Classification | Indicators |
|---|---|---|
| **10** | FULLY EXPOSED | Direct internet, no WAF, confirmed vulnerable |
| **9** | FULLY EXPOSED | Internet with basic WAF, exploit works through |
| **8** | EXPOSED | Cloud-hosted, basic auth, exploitable |
| **7** | PARTIALLY EXPOSED | Authenticated access, limited attack surface |
| **6** | PARTIALLY EXPOSED | Partner network, some access available |
| **5** | RESTRICTED | Requires specific credentials |
| **4** | RESTRICTED | Geographically limited access |
| **3** | ISOLATED | VPN/internal network required |
| **2** | ISOLATED | Isolated network, physical access needed |
| **1** | AIRGAPPED | Fully isolated, no network access |

Scoring checklist:
- [ ] Direct internet access?
- [ ] No WAF/IPS?
- [ ] Basic auth or no auth on admin?
- [ ] API publicly accessible?
- [ ] Registration/enrollment open?
- [ ] Test/sandbox environment exposed?
- [ ] Partner/merchant portal accessible?
- [ ] Requires VPN/creds?

---

## Priority Thresholds

| Score Range | Priority | Action |
|---|---|---|
| **700-1000** | P1 CRITICAL | Immediate HUNTER escalation → Reece alert |
| **500-699** | P2 HIGH | HUNTER queue (within 24h) |
| **300-499** | P3 MEDIUM | Monitor + quarterly deep scan |
| **150-299** | P4 LOW | Archive + annual review |
| **0-149** | P5 MONITOR | Track for changes, 90-day recheck |

---

## Scoring Process

### RECON → INTEL Handoff

When RECON flags a new target:

```
1. RECON adds to knowledge/targets/active/<domain>.json
2. RECON pushes to knowledge/bot_queue/recon_pending.json
3. INTEL picks up from queue
4. INTEL runs full scoring algorithm
5. INTEL moves target to appropriate queue
6. INTEL alerts Reece for P1 targets
```

### Scoring Update Triggers

Scores update when:
- New CVE published for tech stack
- New vulnerability discovered by HUNTER
- Breach data matches target
- Tech stack changes detected
- Engagement completes
- Time-based recheck (quarterly for P4-P5)

---

## Target Lifecycle

```
NEW → RECON flags it
  ↓
SCORED → INTEL calculates score
  ↓
P1-P2 → HUNTER queue (fast track)
P3 → Monitor queue
P4-P5 → Archive
  ↓
HUNTED → HUNTER builds exploit
  ↓
READY → OPERATIONS receives package
  ↓
OPERATED → Engagement executed
  ↓
COMPLETE → Archived with findings
  ↓
RECHECK → Score recalculated after 90 days
```

---

## Scoring Template

Use this template for each target:

```yaml
target: <domain>
scored_at: YYYY-MM-DD HH:MM

threat_surface:
  score: <1-10>
  indicators:
    - <finding>
    - <finding>
  notes: <justification>

exploitability:
  score: <1-10>
  indicators:
    - <finding>
    - <finding>
  notes: <justification>

target_value:
  score: <1-10>
  indicators:
    - <finding>
    - <finding>
  notes: <justification>

exposure_level:
  score: <1-10>
  indicators:
    - <finding>
    - <finding>
  notes: <justification>

calculation:
  (Threat × 0.30) + (Exploit × 0.25) + (Value × 0.25) + (Exposure × 0.20)
  (<TS> × 0.30) + (<EX> × 0.25) + (<TV> × 0.25) + (<EL> × 0.20)
  = <FINAL SCORE>

priority: P1-P5
queue: <active/hunter/ops/archive>
next_action: <what happens next>
next_review: YYYY-MM-DD
```

---

## Auto-Scoring (INTEL Bot)

INTEL bot runs auto-scoring on all active targets:

```python
# Pseudo-code for auto-scoring
for target in active_targets:
    score = (
        target.threat_surface * 0.30 +
        target.exploitability * 0.25 +
        target.target_value * 0.25 +
        target.exposure_level * 0.20
    ) * 100
    
    if score >= 700:
        target.priority = 'P1'
        target.queue = 'HUNTER_URGENT'
        alert_operator(target)
    elif score >= 500:
        target.priority = 'P2'
        target.queue = 'HUNTER_QUEUE'
    elif score >= 300:
        target.priority = 'P3'
        target.queue = 'MONITOR'
    else:
        target.priority = 'P4-P5'
        target.queue = 'ARCHIVE'
```

---

## Override Rules

In some cases, manual override is needed:

| Override | Reason | Who |
|---|---|---|
| Score UP | High-value target with limited vulns | Reece |
| Score DOWN | Low-value target despite surface vulns | Reece |
| Force P1 | Time-critical engagement | Reece |
| Force ARCHIVE | Out of scope / abandoned | Reece |

Override must be documented with reason in target file.

---

## Reporting

Weekly scoring report to Reece via Telegram:

```
📊 TARGET SCORE REPORT — <date>

P1 CRITICAL: <N targets>
  - <domain> (<score>) — <reason>

P2 HIGH: <N targets>
  - <domain> (<score>)

P3 MEDIUM: <N targets>
  - <domain> (<score>)

P4-P5: <N targets> (archived)

Top movers:
  ⬆️ <domain> — score increased by <N> (reason)
  ⬇️ <domain> — score decreased by <N> (reason)
  🆕 <domain> — new target added

Total active: <N> | Total scanned: <N>
```