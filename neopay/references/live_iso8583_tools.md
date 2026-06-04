# Live ISO8583 Tool Integration Guide

This guide describes how to run the repository’s ISO8583 tooling against **authorized payment test environments** and controlled lab gateways. The workflow is intended for protocol validation, compliance evidence generation, and defensive assessment. Operators must confirm written authorization, approved network ranges, rate limits, and test-card usage before connecting to any endpoint.

## Toolchain Overview

| Capability | Repository Tool | Primary Input | Primary Output |
|---|---|---|---|
| Message parsing | `neopay/scripts/parse_iso8583.py` | Raw HISO87/HISO93 message bytes | Parsed MTI, bitmap, data elements, and response-code interpretation |
| Message authentication | `neopay/scripts/mac_generator.py` | Message bytes and configured key material | DE64 or DE128 MAC value for integrity validation |
| HSM simulation | `neopay/scripts/hsm_simulator.py` | Authorized lab commands and local HSM config | Deterministic cryptographic test responses |
| POS protocol testing | `neopay/scripts/spdh_client.py` | Authorized host, port, dialect, and request profile | Network response trace and timing metadata |
| Packet evidence | `neopay/scripts/pcap_tools.py` | PCAP/PCAPNG captures from approved tests | Extracted protocol payloads and metadata |

## Authorization Gate

Before invoking live tools, create an allowlist file under `knowledge/gateway_profiles/<target>/allowlist.txt` containing one approved hostname or IP address per line. The operator should also capture the authorization reference in `knowledge/gateway_profiles/<target>/authorization.json`, including the assessment window, approver, permitted ports, and traffic ceilings.

```json
{
  "target": "lab-switch.example.net",
  "authorization_reference": "AUTH-2026-ISO8583-LAB-001",
  "approved_by": "Security Engineering",
  "valid_from": "2026-06-04T00:00:00Z",
  "valid_until": "2026-06-10T00:00:00Z",
  "permitted_ports": [7000, 7010],
  "max_requests_per_minute": 30
}
```

## Live Parser Workflow

The parser can decode captured or lab-generated messages without transmitting network traffic. Use this first to confirm dialect and field layouts.

```bash
python3 neopay/scripts/parse_iso8583.py \
  --dialect ascii \
  --input knowledge/gateway_profiles/lab-switch/samples/auth_response.bin \
  --explain \
  --json-output knowledge/gateway_profiles/lab-switch/parsed/auth_response.json
```

The resulting JSON should be committed only when it contains sanctioned test data. Do not store production PANs, PIN blocks, cardholder data, or secrets.

## MAC and HSM Validation Workflow

Use the HSM simulator for deterministic lab validation when no certified test HSM is available. Keys must come from local test configuration, environment variables, or a secrets manager; do not hard-code production keys.

```bash
python3 neopay/scripts/hsm_simulator.py \
  --config neopay/assets/hsm_config.yaml \
  --command MAC_GENERATE \
  --key-index 1 \
  --data "$(base64 -w0 knowledge/gateway_profiles/lab-switch/messages/auth_request.bin)" \
  --algorithm ISO9797_1
```

After generating or verifying a MAC, record only the hash of the message and the validation outcome in the evidence package.

## Controlled Live Transmission

When a lab endpoint is explicitly authorized, use rate-limited POS protocol tooling and retain request/response hashes for chain-of-custody.

```bash
python3 neopay/scripts/spdh_client.py \
  --host lab-switch.example.net \
  --port 7000 \
  --dialect hiso93 \
  --input knowledge/gateway_profiles/lab-switch/messages/network_test_0800.bin \
  --output knowledge/gateway_profiles/lab-switch/responses/network_test_0810.bin \
  --timeout 5
```

All live runs should be accompanied by a timestamped note in `knowledge/gateway_profiles/<target>/run_log.jsonl` containing the authorization reference, command, request hash, response hash, and operator.

## Evidence Packaging

Package the parser output, command transcript, request/response hashes, and authorization file with the evidence-chain skill.

```bash
python3 skills/evidence-chain/evidence_chain.py \
  knowledge/gateway_profiles/lab-switch/authorization.json \
  knowledge/gateway_profiles/lab-switch/parsed \
  knowledge/gateway_profiles/lab-switch/run_log.jsonl \
  --label lab-switch-iso8583-validation
```

## Operational Safeguards

Operators should prefer offline parsing and lab simulation before any network test. Live transmission must be bounded by the allowlist, assessment window, and request-rate ceiling. Any unexpected approval response, MAC anomaly, malformed authorization message, or production-data exposure must be escalated to the operator and recorded as a security event rather than retested repeatedly.
