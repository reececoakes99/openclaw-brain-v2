# TOOLS.md — Environment Reference

---

## KiloClaw Environment

- **Platform:** KiloClaw (Fly.io isolated single-tenant VPS)
- **OS:** Debian Bookworm (slim)
- **Volume mount:** `/root` — backed by snapshots, install all dependencies here
- **Workspace:** `/root/.openclaw/workspace`
- **Kilo CLI:** `kilo` — interactive: `kilo` / autonomous: `kilo run --auto "task"`
- **Config:** `/root/.config/kilo/opencode.json`
- **Do not modify:** `/root/.kilo`

---

## Gateway

- **Port:** 18789 — loopback only, never expose to public internet
- **Process manager:** supervisor

---

## Networking

- **Tailscale IP:** 100.84.143.47
- **Git identity:** reececoakes99 / reececoakes99@users.noreply.github.com

---

## API Configuration

- **Primary model:** `anthropic/claude-sonnet-4-6`
- **Fallback 1:** `openrouter/anthropic/claude-sonnet-4-6`
- **Fallback 2:** `openrouter/meta-llama/llama-3.3-70b-instruct`
- **Spend cap:** $10 per 24-hour period — hard limit
- **Cost governor:** See `COST_GOVERNOR.md`

---

## Telegram

- **Bot handle:** @Elkinlochbot
- **Operator chat ID:** 8069069638
- **Pending alerts:** `~/.openclaw/alerts/pending/` — retry every 5 min if unreachable

---

## Bot Fleet Tools

### RECON Bot Tools
```
nmap -sS -sV -p 443,8443,9443,8080,10443 --script ssl-cert,http-headers
shodan (Python SDK)
censys (Python SDK)
subfinder -d <domain>
amass enum -passive -d <domain>
ffuf -w wordlists/subdomains.txt -u https://<domain>/FUZZ
naabu -passive -host <domain>
wappalyzer (CLI)
whatweb <target>
```

### INTEL Bot Tools
```
sqlmap (CVE correlation)
nvd-api (NVD CVE feed)
shodan-exploits
searchsploit
exploitdb
theHarvester -d <domain>
sublist3r -d <domain>
dnsenum <domain>
```

### HUNTER Bot Tools
```
burp suite (pro)
sqlmap --batch --level=5 --risk=3
ffuf (aggressive fuzzing)
jwt_tool
hashcat
commix
xsstrike
nuclei -t custom-payment-templates/
custom ISO8583 fuzzer (neopay/scripts/)
custom HSM simulator (neopay/scripts/)
```

### OPERATIONS Bot Tools
```
Full engagement package from knowledge/gateway_profiles/<target>/
mitmproxy (for traffic inspection)
tcpdump (packet capture)
wireshark (protocol analysis)
iso8583 parser (neopay/scripts/)
```

---

## Reference Repositories (local copies)

- **SecLists:** `repos/SecLists/` — wordlists, credential lists, fuzzing strings, discovery lists
- **PayloadsAllTheThings:** `repos/PayloadsAllTheThings/` — payloads, exploitation techniques, bypasses

---

## Neopay Payment Attack Framework

Located at `neopay/` — embedded payment attack capabilities:

```
neopay/references/
├── iso8583.md           # ISO8583 message format, HISO93/HISO87 variants
├── hsm.md               # HSM operations, PIN blocks, MAC generation
├── pos_protocols.md    # SPDH, HPDH, Verifone XFlow
├── compliance.md        # PCI-DSS, PSD2, card scheme rules
├── emv.md               # EMV transaction flow, ARQC/ARPC
└── software_stack.md    # Payment software fingerprinting

neopay/scripts/
├── iso8583_fuzzer.py    # ISO8583 field fuzzing + replay
├── hsm_simulator.py     # HSM command simulation + testing
├── pin_block_gen.py     # ISO9564 PIN block generation
├── crypto_downgrade.py  # TLS/cipher downgrade testing
├── fingerprint_payment.py # Payment gateway fingerprinting
├── iso8583_parser.py     # Message parsing + field extraction
└── scheme_tester.py     # Test card validation + scheme rules

neopay/assets/
├── test_cards.json      # Test BIN ranges (Visa/MC/Amex/UnionPay)
├── iso_payloads.json    # Pre-built ISO8583 message templates
├── payload_templates/   # Ready-to-fire attack payloads
└── card_ranges.json     # Valid test card ranges by scheme
```

---

## Database

- **Reports DB:** `reports/sqlite/engagement.db`
- **Schema:** `reports/sqlite/schema.sql`

---

## Cron Jobs (24/7 Automation)

```
*/5 * * * *  python3 master_pipeline.py --bot-recon-scan
0 */4 * * *  python3 master_pipeline.py --bot-intel-cycle
0 2 * * *    python3 master_pipeline.py --bot-hunter-deep
*/30 * * * * python3 knowledge/bot_activity_logs/health_check.py
```

---

## Environment Variables

```bash
export GITHUB_PAT="ghp_..."
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="8069069638"
export NEOPAY_SKILLS_PATH="/root/.openclaw/workspace/neopay"
export KNOWLEDGE_BASE="/root/.openclaw/workspace/knowledge"
export OPENCLAW_WORKSPACE="/root/.openclaw/workspace"
```