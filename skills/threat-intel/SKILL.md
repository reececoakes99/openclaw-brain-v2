# Threat Intelligence — Correlate Breach Data and Dark Web Mentions

## Metadata

- **Skill Name:** threat-intel
- **Type:** Threat Intelligence / Breach Monitoring
- **Author:** OpenClaw Brain v2
- **Version:** 1.0.0
- **Last Updated:** 2026-05-09

---

## Overview

The Threat Intelligence skill continuously monitors public breach disclosures, dark web forums, and underground marketplaces for mentions of targets, payment providers, and infrastructure components. It correlates raw intel against active engagement targets and escalates matching indicators to the appropriate priority level.

Payment infrastructure is a high-value target for data breaches. A single credential dump from a payment vendor's internal system can expose thousands of merchant credentials, API keys, or cardholder data. This skill provides the early warning layer needed to act before adversaries weaponize exposed data.

---

## Trigger Conditions

**Autonomous Triggers:**
- Cron job: `0 */6 * * *` (every 6 hours) — dark web + breach monitoring sweep
- New target added to active campaign — initial baseline threat scan
- After campaign-manager skill marks a target as "surface" or "deep" phase

**Manual Triggers:**
- User: "check dark web mentions for <target>"
- User: "any breaches involving <payment provider>"
- User: "recent payment provider breaches?"
- User: "any data for sale from <target's> customers"
- User: "correlate breach intel with active targets"
- User: "is Stripe mentioned on dark web forums?"

---

## When to Use

| Scenario | Action |
|---|---|
| Routine intelligence gathering | Run scheduled sweep every 6 hours |
| New client onboarding | Initial dark web baseline scan for their domain/brand |
| Major payment provider breach announced | Check all active targets for shared infrastructure |
| Campaign escalation to exploit phase | Verify no external breach mentions that could warn target |
| PCI DSS breach notification compliance | Document all intel related to client's data exposure |
| Post-breach incident response | Retroactively search for earliest indicators of compromise |

---

## Operational Procedure

### Phase 1 — HaveIBeenPwned API Integration

**Step 1.1 — API Queries**

```bash
# Check specific domain for breaches (requires HaveIBeenPwned API key)
curl -s -H "hibp-api-key: $HIBP_API_KEY" \
  "https://haveibeenpwned.com/api/v3/getbreaches?domain=targetdomain.com& truncateResponse=false"

# Search for password dump associated with a domain
curl -s -H "hibp-api-key: $HIBP_API_KEY" \
  "https://haveibeenpwned.com/api/v3/pasteaccount(email@example.com)"

# Check for domain-specific paste leaks (Pastebin, Ghostbin)
curl -s -H "hibp-api-key: $HIBP_API_KEY" \
  "https://haveibeenpwned.com/api/v3/pastes?domain=targetdomain.com"
```

**Step 1.2 — HIBP Response Parsing**

```json
{
  "Name": "BreachName",
  "Title": "Breach Title",
  "Domain": "target.com",
  "BreachDate": "2024-01-15",
  "AddedDate": "2024-02-01T00:00:00Z",
  "ModifiedDate": "2024-02-01T00:00:00Z",
  "PwnCount": 15234567,
  "Description": "Description of breach",
  "DataClasses": ["Email addresses", "Passwords", "Payment records"],
  "IsVerified": true,
  "IsFabricated": false,
  "IsSensitive": false,
  "IsRetired": false,
  "IsSpamList": false
}
```

---

### Phase 2 — Dark Web Forum Monitoring

**Step 2.1 — Structured Source Monitoring**

Monitor these patterns across intelligence sources:

```bash
# TOR hidden service discovery (use onionoo for Tor network stats)
curl -s "https://onionoo.torproject.org/details?search=${TARGET_KEYWORD}"

# Dark web forum aggregator / custom scrapers
# Note: Use authenticated access only; maintain operational security

# Paste site monitoring
curl -s "https://psbdmp.ws/api/search/${TARGET_KEYWORD}"
curl -s "https://dpaste.org/api/?{TARGET_KEYWORD}"          # direct paste search

# GitHub secret scanning alerts
curl -s -H "Authorization: token $GITHUB_TOKEN" \
  "https://api.github.com/orgs/${TARGET_ORG}/repos?type=private" \
  | jq '.[] | .name'  # Check for leaked credentials in private repos
```

**Step 2.2 — Pastebin/Ghostbin Monitoring**

```bash
# Monitor Pastebin for target keywords (rotate user-agents)
curl -s -A "Mozilla/5.0 (compatible; MonitoringBot/1.0)" \
  "https://pastebin.com/archive" | grep -i "stripe\|payment\|braintree\|merchant\|card"

# Search specific pastebin archives
curl -s "https://psbdmp.ws/api/search/${TARGET_DOMAIN}"
# Returns: paste content, creation date, "sensitive" classification
```

---

### Phase 3 — Payment Provider-Specific Breach Tracking

**Step 3.1 — Monitored Providers**

```
Primary Payment Providers:
- Stripe (stripe.com, stripe.network)
- Braintree / PayPal (braintree.com)
- Adyen (adyen.com)
- Worldpay (worldpay.com, worldpay.hybris.com)
- Square (squareup.com)
- Authorize.Net (authorize.net)
- CyberSource (cybersource.com)
- Checkout.com (checkout.com)
- NMI / Network Merchants (nmi.com)
- Elavon
- Global Payments (globalpaymentsinc.com)
- Fiserv (fiserv.com)
- Mollie (mollie.com)
- Recurly (recurly.com)
- Chargebee (chargebee.com)
```

**Step 3.2 — Provider Breach Search Pattern**

```bash
# Search breach databases for payment provider mentions
for provider in "stripe" "braintree" "adyen" "worldpay" "square"; do
  echo "=== Checking $provider ===" 
  curl -s -H "hibp-api-key: $HIBP_API_KEY" \
    "https://haveibeenpwned.com/api/v3/breach/${provider}" \
    | jq '{name, breachDate, pwnCount, dataClasses}'
done
```

**Step 3.3 — Linked Target Correlation**

```bash
# For each active campaign target, check if they use a breached provider
for target in /root/.nanobot/workspace/openclaw-brain-v2/knowledge/gateway_profiles/*/; do
  TARGET_NAME=$(basename "$target")
  USED_PROVIDERS=$(jq -r '.payment_providers[]?' "$target/provider_info.json" 2>/dev/null)
  
  for provider in $USED_PROVIDERS; do
    BREACH_STATUS=$(check_provider_breach "$provider")
    if [ "$BREACH_STATUS" == "BREACHED" ]; then
      echo "ALERT: $TARGET_NAME uses $provider which has an active breach"
    fi
  done
done
```

---

### Phase 4 — Dark Web Marketplace Pattern Matching

**Step 4.1 — Card Data Patterns**

Monitor for these patterns in paste sites, forums, and dumps:

```
# Card data regex patterns (for monitoring feeds, NOT for processing actual card data)
[0-9]{13,19}\s{0,2}[0-9]{1,4}\s{0,2}[0-9]{2}\s{0,2}[0-9]{4}   # PAN pattern
\d{2}/\d{2}                                                   # Expiry
\d{3,4}                                                      # CVV
^\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}$                    # Full PAN
```

**Step 4.2 — Gift Card & Loyalty Patterns**

```
# Gift card number patterns
GIFT-\d{16}-\d{4}
GC_\d{12}_[A-Z0-9]{8}

# Loyalty/points program patterns  
LOYALTY-\d{10}
POINTS-\d{4}-\d{6}
```

**Step 4.3 — Marketplace Listings**

```bash
# Monitor known dark web marketplace listing patterns
# (These require custom scraping infrastructure — see Phase 5 for sources)

MARKETPLACE_PATTERNS=(
  "dump"          # Credit card dumps
  "cvv"           # Card verification value
  "fullz"         # Full cardholder info with SSN/DOB
  "logs"          # Banking logs
  " RDP "         # Remote Desktop Protocol access
  "shell"         # Web shell sales
  "cPanel"        # Hosting control panel access
  "WHM"           # Web Host Manager access
  "merchant"      # Payment processor access
  "gateway"       # Payment gateway access
  "stripe"        # Stripe account access
  "shopify"       # Shopify merchant access
  "api key"       # API key sales
  "2fa bypass"    # 2FA bypass tools
)
```

---

### Phase 5 — Exploit Kit Fingerprint Correlation

**Step 5.1 — EK Pattern Database**

Maintain a pattern database of known exploit kit fingerprints:

```bash
# Angler EK patterns
ANGLER_PATTERNS=(
  "angler" "ek-angler" "ng-ek" "cryptobot"
  "base64.*eval"  # Angler encoded payload
  "window.atob"   # Base64 decode in Angler
)

# Neutrino EK patterns  
NEUTRINO_PATTERNS=(
  "neutrino" "neutrino-ek" "n3utr1n0" "boson"
  "cookie.*neutrino" "neutrino_rc" 
)

# RIG EK patterns
RIG_PATTERNS=(
  "rig" "rig-ek" "white rig" "sunshine"
  "iframe.*rig" "rigredirect"
  "302.*redirect.*flash"  # RIG redirect pattern
)

# Search for EK infrastructure in campaign network logs
for pattern in "${RIG_PATTERNS[@]}"; do
  grep -rli "$pattern" /root/.nanobot/workspace/openclaw-brain-v2/knowledge/network_logs/ 2>/dev/null
done
```

---

### Phase 6 — Correlation and Escalation

**Step 6.1 — Breach-to-Target Mapping**

When a breach mention is found:

1. **Identify affected provider/technology** from breach data
2. **Cross-reference** with all active target profiles
3. **Check for shared infrastructure** (CDN, hosting, third-party scripts)
4. **Escalation decision:**

| Condition | Action |
|---|---|
| Direct brand/domain mention | P1 escalation + immediate Telegram alert |
| Provider mention (target uses that provider) | P2 escalation + campaign update |
| Infrastructure overlap (shared CDN/IP range) | P3 escalation + note in tracker |
| No direct link | Log to breach_correlation with "monitoring" status |

---

### Phase 7 — Output Format

**Step 7.1 — Telegram Alert**

```markdown
🔴🚨 BREACH INTEL ALERT — P1 ESCALATION

📛 Breach Source: <breach_name>
🏢 Affected Provider: <provider_name>
📅 Breach Date: <date>
👥 Records Exposed: <count>
📦 Data Types: <comma-separated list>
🎯 Linked Targets: <comma-separated list>
🔗 IOC: <domain/ip/credential_hash>
⚠️ Escalation Reason: <why P1>
📌 Recommended Action: <containment_steps>
⏰ Intel Timestamp: <discovery_time>
```

**Step 7.2 — Tracker JSON Update**

```json
{
  "last_scan": "2026-05-09T06:00:00Z",
  "scan_type": "scheduled_6h",
  "sources_checked": [
    "haveibeenpwned",
    "pastebin_monitoring", 
    "dark_web_forums",
    "marketplace_patterns"
  ],
  "breaches_found": [
    {
      "breach_id": "breach_2024_007",
      "source": "haveibeenpwned",
      "breach_name": "PaymentProcessorXYZ",
      "breach_date": "2024-11-20",
      "discovery_date": "2026-05-09T06:00:00Z",
      "affected_provider": "PaymentProcessorXYZ",
      "data_types": ["Email addresses", "API keys", "Encrypted payment tokens"],
      "pwn_count": 234000,
      "linked_targets": ["target-alpha", "target-gamma"],
      "priority": "P1",
      "status": "active_investigation",
      "cve_correlation": ["CVE-2024-44123"],
      "correlation_notes": "Target-alpha uses PaymentProcessorXYZ API; tokens may be compromised"
    }
  ],
  "summary": {
    "p1_count": 1,
    "p2_count": 2,
    "p3_count": 4,
    "total_intel_items": 7
  }
}
```

---

### Phase 8 — Cron Configuration

```bash
# Every 6 hours
0 */6 * * * /root/.nanobot/workspace/openclaw-brain-v2/skills/threat-intel/run_intel_scan.sh >> /root/.nanobot/workspace/openclaw-brain-v2/knowledge/breach_correlation/scan.log 2>&1
```

---

## Error Handling

| Error | Cause | Resolution |
|---|---|---|
| HIBP API 401 | Invalid API key | Verify key; fall back to web search for breach data |
| HIBP API 429 | Rate limit (1 req/min free tier) | Add `sleep 60` between requests; use paid tier for production |
| TOR network unreachable | Exit node down | Rotate to alternative TOR bridges; use cached data |
| Dark web scrape blocked | Anti-bot detection | Rotate User-Agent; implement request delays |
| Paste search returns no results | Indexed incorrectly | Try alternative paste search services (Pastebin PRO API) |
| Tracker JSON write fails | Permissions or disk space | Check filesystem; use `jq -M` for atomic writes |
| Pattern match false positive | Generic keyword collision | Refine regex; add context validation (surrounding text) |

---

## Cross-References

- **THREAT_INTEL.md** — Strategy and framework for threat intelligence operations
- **memory/TTP_INDEX.md** — TTP mappings (T1199 — Trusted Relationship, T1078 — Valid Accounts)
- **memory/ERRORS.md** — Known error patterns that may indicate prior compromise
- **cve-tracker skill** — Breach mention often correlates to specific CVE; trigger CVE scan
- **campaign-manager skill** — Breach intel updates affect campaign phase decisions
- **knowledge/breach_correlation/tracker.json** — Central breach correlation database
- **knowledge/gateway_profiles/<target>/** — Provider data for correlation

---

## Example Session

**Query:** `"any breaches involving Adyen or Stripe in the last 90 days?"`

**Output:**
```
[+] Searching HaveIBeenPwned for payment provider breaches...
[+] Checking Adyen-related breaches...
[!] BREACH FOUND: "AdyenMerchant2024"
    Date: 2024-08-15 | Records: 340,000
    Data: Email addresses, Merchant IDs, API credentials
    Status: VERIFIED
    
[+] Checking Stripe-related breaches...
[!] BREACH FOUND: "StripeDeveloperForum"  
    Date: 2024-10-22 | Records: 89,000
    Data: Email addresses, Hashed passwords, 2FA tokens
    Status: VERIFIED
    
[+] Correlating with active targets...
[+] TARGET-ALPHA: Uses Adyen — MATCH FOUND ⚠️
    Correlation: Merchant ID prefix "ADY-" matches target-alpha profile
    Escalation: P1 — API credentials potentially exposed
    
[+] TARGET-BETA: No provider match (uses Authorize.Net only)
[+] TARGET-GAMMA: Uses Stripe — MATCH FOUND ⚠️
    Correlation: Developer forum account email matches target-gamma infrastructure
    Escalation: P2 — Monitor for credential stuffing attempts
    
[+] Telegram alerts sent:
    - P1: Target-alpha + Adyen breach
    - P2: Target-gamma + Stripe breach
    
[+] Tracker updated: knowledge/breach_correlation/tracker.json
[✓] Intel scan complete. 2 provider breaches, 2 linked targets, 1 P1, 1 P2.
```
