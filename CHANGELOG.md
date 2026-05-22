# CHANGELOG.md — OpenClaw Brain v2

All notable changes to the brain are documented here.

---

## [Unreleased]

### Added
- `BOOT.md` — Agent initialization and binding protocol with 5-phase load order, state machine, write protocol, multi-model routing, context budget, hot-reload triggers, error recovery
- `NEOPAY_COMMANDS.md` — Unified command reference for all neopay offensive scripts (ISO8583, HSM, POS, traffic interception, load testing, command chaining)
- `NEOPAY_FEEDBACK.md` — Result ingestion protocol with classification system, knowledge update rules, confidence adjustment, evidence chain integration, queue promotion logic
- `PIPELINE_BINDING.md` — Pipeline-to-brain integration with bot-stage mapping, path alignment, trigger interface, failure semantics, capability refresh protocol
- `.env.example` — Environment variable template (secrets never committed)
- `.gitignore` — Security exclusions for secrets, databases, captures, temp files
- `knowledge/bot_queue/intel_pending.json` — Missing INTEL bot queue file (fleet symmetry)
- Payment-specific confidence indicators in `CONFIDENCE_FRAMES.md`
- Pipeline and neopay tracking in `HEARTBEAT.md`
- Neopay cost awareness section in `COST_GOVERNOR.md`

### Changed
- `IDENTITY.md` — Removed hardcoded Telegram bot token, replaced with `${TELEGRAM_BOT_TOKEN}`
- `IDENTITY.md` — Removed hardcoded chat ID, replaced with `${OPERATOR_CHAT_ID}`
- `TOOLS.md` — Removed hardcoded Tailscale IP, replaced with `${TAILSCALE_IP}`
- `TOOLS.md` — Removed hardcoded chat ID, replaced with `${OPERATOR_CHAT_ID}`
- `TOOLS.md` — Sanitized environment variables section (no literal credentials)
- `COST_GOVERNOR.md` — Removed hardcoded Telegram token and chat ID
- `bot_evasion.md` — Populated from empty with 8 operational evasion categories (TLS fingerprint, HTTP fingerprint, timing, network, application, payment-specific, detection avoidance, anti-forensics)
- `knowledge/targets/active_targets.json` — Purged fake demo data (.example.com domains)

### Fixed
- OPSEC violation: Telegram bot token was exposed in plaintext in IDENTITY.md and COST_GOVERNOR.md
- Empty operational file: bot_evasion.md was 0 bytes (critical gap for offensive agent)
- Missing queue file: INTEL bot had no queue file while RECON, HUNTER, OPS did
- Fake data: active_targets.json contained RFC 2606 reserved domains

---

## [2.1.0] — 2026-05-13

### Added
- Initial v2.1 Payment Warfare Edition
- 4-bot fleet architecture (RECON, INTEL, HUNTER, OPERATIONS)
- Embedded neopay payment attack framework
- 20 specialized skills
- knowledge_updater system (cert_spider, cve_spider, darkweb_spider)
- memory/ operational state system
- protocol-engineering/ scripts and references
