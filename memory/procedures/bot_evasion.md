# DECOY Bot Operational Guide

## Purpose and Authorization Boundary

The **DECOY** bot provides counter-intelligence, misdirection, and operational security support for **authorized security assessments, purple-team exercises, and defensive deception programs**. Its role is to reduce unnecessary exposure of assessment infrastructure, create benign deception telemetry for blue-team validation, and signal risk conditions to the broader bot fleet. It must not be used to hide unauthorized access, bypass monitoring on third-party systems, pollute production logs, or evade lawful detection.

> **Operational rule:** DECOY may only run inside an approved engagement scope with written authorization, an allowlisted set of targets, a configured traffic ceiling, and a human operator who can stop the activity immediately.

This guide intentionally frames evasion-related capabilities as **defensive OPSEC and deception controls**. Techniques such as proxy rotation, traffic shaping, fingerprint management, and decoy traffic generation are limited to approved lab ranges, owned infrastructure, and customer-approved test windows. MITRE ATT&CK documents adversary use of proxying and ingress tooling, while NIST and CISA guidance emphasize logging, authorization, and defensive monitoring as core control requirements.[1] [2] [3]

## Capabilities

| Capability | Authorized Use | Required Control |
|---|---|---|
| Proxy rotation | Validate whether defensive controls correctly attribute traffic traversing approved egress nodes. | Only use owned VPN, corporate egress, approved cloud NAT, or contractually authorized residential test networks. |
| Traffic obfuscation | Reduce tool-specific signatures in **lab replay traffic** so detectors are tested against realistic variance. | Do not conceal unauthorized activity; preserve run logs and payload hashes. |
| Decoy traffic generation | Produce benign canary requests and honey-token interactions that help blue teams verify detection pipelines. | Mark all generated traffic with an internal campaign identifier and rate limit. |
| Fingerprint management | Normalize user agents, TLS profiles, and headers to reproduce approved browser or device profiles in a lab. | Use only approved profiles and never impersonate real users or bypass access controls. |
| Log enrichment, not pollution | Add clear, structured engagement markers to owned logs so analysts can separate test telemetry from production events. | Do not delete, corrupt, flood, or falsify logs. |
| Timing randomization | Avoid unrealistic periodic traffic during simulations and load-safe validation. | Enforce minimum and maximum intervals configured in `knowledge/bot_queue/deploy_queue.json`. |

## Activation Triggers

DECOY is activated when the **OPERATIONS** bot begins an approved active validation phase or when the **OPERATOR** requests deception coverage for an assessment. The activation request must be written to `knowledge/bot_queue/deploy_queue.json` and must include the target profile, authorization reference, traffic ceiling, allowed egress methods, and expiration time.

| Trigger Source | Queue Message Type | Required Fields |
|---|---|---|
| OPERATIONS | `decoy.activate` | `authorization_reference`, `target_profile`, `allowed_egress`, `max_requests_per_minute`, `expires_at` |
| OPERATOR | `decoy.configure` | `engagement_id`, `owner`, `scope_file`, `change_ticket`, `approval_contact` |
| ARCHIVIST | `decoy.archive` | `run_id`, `evidence_package`, `hash_manifest`, `storage_policy` |

## Communication Model

DECOY reports status and telemetry summaries to **OPERATIONS** and posts fleet signals through `knowledge/bot_queue/`. It writes machine-readable events to `knowledge/bot_queue/activity_logs/decoy.jsonl` and never stores credentials, production secrets, payment data, or unauthorized payloads.

| Channel | Direction | Content |
|---|---|---|
| `deploy_queue.json` | Inbound | Activation requests and approved OPSEC profiles. |
| `operations_queue.json` | Outbound | Status, risk alerts, stop acknowledgements, and rate-limit notices. |
| `activity_logs/decoy.jsonl` | Outbound | Timestamped hashes, counters, egress identifiers, and authorization references. |
| `health_state.json` | Outbound | Liveness, last run, error count, and current operating mode. |

## Operating Modes

| Mode | Description | Network Access |
|---|---|---|
| `dry_run` | Validates configuration, scope, allowlists, and queue messages without generating network traffic. | None |
| `lab_replay` | Replays approved synthetic traffic against owned ranges or lab systems. | Approved lab targets only |
| `deception_validation` | Generates canary and honey-token interactions for blue-team monitoring validation. | Approved deception assets only |
| `egress_validation` | Tests approved egress controls through owned proxy, VPN, or cloud NAT endpoints. | Approved egress and target pairs only |

## Procedure: Authorization and Scope Validation

DECOY must validate every run before performing any action. The procedure begins by loading the engagement profile from `knowledge/gateway_profiles/<target>/authorization.json`, then verifying that the current time is inside the approved window, that the target appears in the allowlist, and that the requested operating mode is one of the approved modes. If any validation fails, DECOY must write a `decoy.denied` event to `operations_queue.json` and stop.

| Step | Action | Evidence Produced |
|---|---|---|
| 1 | Read the queue activation message and parse `authorization_reference`. | Queue event hash. |
| 2 | Load target allowlist and scope file. | SHA-256 of scope file. |
| 3 | Confirm operating window and traffic ceiling. | Validation decision. |
| 4 | Confirm selected egress method is approved. | Egress identifier and approval record. |
| 5 | Emit `decoy.ready` or `decoy.denied`. | JSONL audit event. |

## Procedure: Proxy Rotation for Approved Egress Validation

Proxy rotation is limited to approved egress nodes. The objective is to verify that monitoring, rate limiting, and attribution controls behave correctly when an authorized test uses multiple known egress points.

| Step | Action | Safety Requirement |
|---|---|---|
| 1 | Load `allowed_egress` from the queue message. | Each entry must map to an owned VPN, approved cloud NAT, or contractually authorized provider. |
| 2 | Assign a stable run identifier and bind it to each egress node. | The run identifier must appear in user-agent comments or a custom internal header when allowed. |
| 3 | Rotate only at configured intervals. | Do not rotate faster than the approved ceiling. |
| 4 | Write the egress node, target, and request hash to the activity log. | Do not write secrets or full payloads. |
| 5 | Stop immediately on denylist hit, HTTP 429, authentication prompt, or analyst stop signal. | Emit `decoy.stop` to `operations_queue.json`. |

## Procedure: Traffic Obfuscation for Lab Replay

Traffic obfuscation means introducing benign variance into authorized lab traffic so detectors are not overfit to a single tool signature. It does not mean bypassing controls on systems outside the engagement scope.

| Step | Action | Implementation Detail |
|---|---|---|
| 1 | Select a lab profile from `knowledge/gateway_profiles/<target>/decoy_profiles.yaml`. | Profiles define allowed headers, payload templates, and timing ranges. |
| 2 | Randomize non-sensitive header ordering and harmless request metadata. | Preserve explicit campaign markers. |
| 3 | Add jitter within approved timing bounds. | Use bounded random delays, never unbounded sleep loops. |
| 4 | Hash each generated request. | Store the hash and profile name in `activity_logs/decoy.jsonl`. |
| 5 | Compare detector results after the run. | Report only aggregate findings to OPERATIONS. |

## Procedure: Decoy Traffic Generation

Decoy traffic is used to validate blue-team telemetry and deception assets. It should never be directed at non-consenting systems.

| Step | Action | Output |
|---|---|---|
| 1 | Load canary endpoint inventory. | `decoy.asset_inventory_hash` event. |
| 2 | Generate benign HTTP, DNS, or application-level canary interactions. | Request hash and response status. |
| 3 | Tag every request with the engagement identifier when protocol-safe. | Analyst correlation key. |
| 4 | Confirm SIEM ingestion or alert generation. | Detection status summary. |
| 5 | Archive run metadata with ARCHIVIST. | Evidence package reference. |

## Procedure: Fingerprint Management

Fingerprint management is used to reproduce approved client profiles such as a corporate browser, mobile test device, or lab POS terminal. It must not impersonate real customers or bypass access controls.

| Step | Action | Control |
|---|---|---|
| 1 | Load an approved fingerprint profile. | Profiles must be reviewed and committed to the target knowledge profile. |
| 2 | Apply allowed user-agent, locale, TLS, and header settings. | Do not use stolen cookies, real user identifiers, or session artifacts. |
| 3 | Execute a dry run to confirm generated metadata. | Store generated fingerprint hash. |
| 4 | Run bounded validation traffic. | Respect rate limits and stop conditions. |
| 5 | Report drift against expected detector behavior. | Submit summary to OPERATIONS. |

## Procedure: Log Enrichment and Audit Marking

DECOY does not perform log pollution. Instead, it writes structured engagement markers that help analysts distinguish authorized test telemetry from organic production events.

| Step | Action | Required Field |
|---|---|---|
| 1 | Generate a run identifier. | `run_id` |
| 2 | Attach the authorization reference to local activity logs. | `authorization_reference` |
| 3 | Include safe campaign markers where protocol-appropriate. | `campaign_id` |
| 4 | Write immutable event hashes. | `event_sha256` |
| 5 | Send the final manifest to ARCHIVIST. | `manifest_sha256` |

## Procedure: Timing Randomization

Timing randomization avoids unrealistic periodicity in authorized simulations. It must remain bounded by the queue request and should never be used to bypass rate limits.

| Step | Action | Default Guardrail |
|---|---|---|
| 1 | Read `min_delay_ms`, `max_delay_ms`, and `max_requests_per_minute`. | Reject missing or zero ceilings. |
| 2 | Generate bounded jitter with a cryptographically strong random source. | Clamp to approved range. |
| 3 | Apply backoff on throttling, errors, or blue-team stop signals. | Prefer stopping over retrying. |
| 4 | Emit periodic status events. | No more than once per minute. |

## Integration with TOR, Residential Proxies, and Cloud Functions

DECOY treats all egress mechanisms as controlled infrastructure. TOR, residential proxies, and cloud functions may only be used when the engagement contract explicitly approves them and when the provider terms allow the activity. The default configuration should prefer owned VPN, corporate NAT, and dedicated cloud egress over public anonymity systems.

| Egress Type | Allowed Scenario | Disallowed Scenario |
|---|---|---|
| TOR | Internal lab simulation of anonymity-network detection. | Contacting third-party production targets or bypassing access controls. |
| Residential proxy | Contract-approved fraud-control validation with provider authorization. | Concealing unauthorized activity or impersonating customers. |
| Cloud function | Approved IP-rotation resilience testing against owned endpoints. | Circumventing rate limits or account controls. |
| Corporate VPN | Standard authorized egress validation. | Any use outside scoped assets. |

## Stop Conditions

DECOY must stop immediately if authorization expires, a target is outside scope, a denylist indicator appears, production credentials are encountered, a rate limit is exceeded, blue-team or OPERATOR sends a stop signal, or any tool produces unexpected sensitive data. A stop event must include the reason, run identifier, and last safe event hash.

## References

[1]: https://attack.mitre.org/techniques/T1090/ "MITRE ATT&CK: Proxy"
[2]: https://attack.mitre.org/tactics/TA0005/ "MITRE ATT&CK: Defense Evasion"
[3]: https://www.cisa.gov/resources-tools/resources/secure-by-design "CISA: Secure by Design"
