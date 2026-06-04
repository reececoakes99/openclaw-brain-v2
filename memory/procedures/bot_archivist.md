# ARCHIVIST Bot Operational Guide

## Purpose and Authorization Boundary

The **ARCHIVIST** bot manages evidence, operational records, and knowledge-base compaction for authorized security assessments. Its function is to preserve integrity, confidentiality, and traceability for findings produced by HUNTER, OPERATIONS, DECOY, and other bots. ARCHIVIST supports secure evidence packaging, encryption, staging, chain-of-custody records, and version-controlled knowledge storage.

ARCHIVIST must not perform unauthorized data exfiltration, conceal evidence movement, or store regulated data outside approved repositories. In this guide, “staging” means preparing authorized evidence for approved storage, and “transfer” means moving evidence through documented channels to an approved repository or recipient. NIST guidance emphasizes the importance of evidence integrity, documented handling, and controlled access in incident and forensic workflows.[1] [2]

> **Operational rule:** ARCHIVIST only accepts evidence from scoped assessments and only writes to approved storage destinations defined in the engagement profile.

## Capabilities

| Capability | Authorized Implementation | Evidence Control |
|---|---|---|
| Evidence encryption | Encrypt evidence packages with GPG or age public keys assigned to the engagement. | Store key fingerprint, recipient, and package hash. |
| Data staging | Organize approved findings into a deterministic package layout before transfer. | Use manifests and sensitivity labels. |
| Secure transfer management | Move evidence to approved repositories, ticket systems, or object stores. | Require destination allowlist and transfer log. |
| Chain of custody | Record who produced, packaged, transferred, received, and accessed each package. | Append immutable JSONL events and signed manifests where available. |
| Automated evidence packaging | Bundle parsed findings, screenshots, logs, and metadata into reproducible archives. | Exclude secrets and regulated data unless explicitly authorized. |
| Knowledge-base compaction | Convert raw bot output into summarized, searchable, deduplicated knowledge entries. | Preserve source hashes and transformation provenance. |
| Git integration | Commit sanitized evidence indexes and knowledge summaries to version control. | Do not commit raw secrets, credentials, PANs, PIN blocks, or private keys. |

## Activation Triggers

ARCHIVIST is activated after **HUNTER** or **OPERATIONS** produces findings, after **DECOY** completes an authorized simulation, or when **OPERATOR** requests evidence packaging. Trigger messages are written to `knowledge/bot_queue/operations_queue.json` or `knowledge/bot_queue/deploy_queue.json` depending on the source.

| Trigger Source | Queue Message Type | Required Fields |
|---|---|---|
| HUNTER | `archivist.package_finding` | `finding_id`, `source_path`, `classification`, `authorization_reference` |
| OPERATIONS | `archivist.package_run` | `run_id`, `evidence_paths`, `target_profile`, `operator` |
| DECOY | `archivist.package_decoy_run` | `run_id`, `activity_log`, `manifest_sha256`, `authorization_reference` |
| OPERATOR | `archivist.compact_knowledge` | `scope`, `source_directory`, `destination`, `retention_policy` |

## Communication Model

ARCHIVIST receives from all bots and reports to **OPERATOR**. It should write high-level acknowledgements to `knowledge/bot_queue/operations_queue.json`, detailed audit events to `knowledge/bot_queue/activity_logs/archivist.jsonl`, and package manifests to `memory/evidence/<engagement_id>/manifests/`.

| Channel | Direction | Content |
|---|---|---|
| `operations_queue.json` | Inbound and outbound | Packaging requests, completion events, and error reports. |
| `activity_logs/archivist.jsonl` | Outbound | Custody events, hashes, key fingerprints, destination identifiers, and package IDs. |
| `memory/evidence/<engagement_id>/` | Outbound | Approved evidence archives, manifests, summaries, and indexes. |
| Git history | Outbound | Sanitized knowledge updates, manifests, and procedure improvements. |

## Evidence Classification

Every item must be classified before packaging. Classification controls encryption, retention, review, and transfer destination.

| Classification | Examples | Required Handling |
|---|---|---|
| `public` | Public CVE references and public advisories. | Manifest entry and normal retention. |
| `internal` | Assessment notes, tool output summaries, test configuration. | Repository access controls and package hash. |
| `confidential` | Customer-owned findings, screenshots, non-public logs. | Encryption before transfer and restricted destination. |
| `restricted` | Secrets, regulated data, private keys, payment data, personal data. | Do not package unless explicitly authorized; redact where possible. |

## Procedure: Evidence Intake

ARCHIVIST begins by validating the queue request and checking the source path against the approved engagement scope. It then calculates file hashes before any transformation so the original evidence can be referenced even if the packaged representation is compressed or encrypted.

| Step | Action | Output |
|---|---|---|
| 1 | Parse queue message and verify `authorization_reference`. | `intake.accepted` or `intake.denied` event. |
| 2 | Confirm every source path exists under an approved evidence root. | Scope validation record. |
| 3 | Classify each item using extension, location, and optional metadata. | Classification table. |
| 4 | Compute SHA-256 for each source item. | Source hash manifest. |
| 5 | Refuse restricted data unless the engagement explicitly permits it. | Denial reason and escalation event. |

## Procedure: Evidence Collection

Evidence collection should be deterministic and reproducible. ARCHIVIST creates a package workspace with a normalized directory layout.

| Directory | Contents |
|---|---|
| `raw/` | Approved original evidence files or redacted copies. |
| `derived/` | Parsed outputs, screenshots, normalized JSON, and summaries. |
| `manifests/` | Source hashes, package hashes, custody events, and review notes. |
| `reports/` | Human-readable summaries and operator handoff notes. |

The bot must avoid modifying original evidence in place. Any transformation must produce a new derived file with the source hash recorded in the manifest.

## Procedure: Encryption with GPG or age

ARCHIVIST encrypts packages when classification is `confidential` or `restricted`, or when required by the engagement profile. The public recipient keys should be stored as fingerprints in configuration, while the actual private keys remain outside the repository.

| Step | Action | Evidence Produced |
|---|---|---|
| 1 | Load recipient fingerprints from `knowledge/gateway_profiles/<target>/evidence_policy.json`. | Key policy hash. |
| 2 | Build a tar archive from the package workspace. | Archive SHA-256. |
| 3 | Encrypt with GPG or age to approved recipients. | Encrypted package SHA-256. |
| 4 | Verify decryptability in a controlled environment when policy permits. | Verification result. |
| 5 | Record key fingerprints, algorithm, archive hash, and encrypted hash. | Encryption manifest. |

Example commands for an approved operator workstation are shown below. They are intentionally written as explicit operator commands so private keys remain under human control.

```bash
tar --sort=name --mtime='UTC 1970-01-01' --owner=0 --group=0 --numeric-owner \
  -czf memory/evidence/ENG-001/packages/finding-123.tar.gz \
  -C memory/evidence/ENG-001/workspaces/finding-123 .

gpg --encrypt --recipient SECURITY-TEAM-FINGERPRINT \
  --output memory/evidence/ENG-001/packages/finding-123.tar.gz.gpg \
  memory/evidence/ENG-001/packages/finding-123.tar.gz
```

## Procedure: Secure Staging and Transfer

ARCHIVIST stages evidence only to destinations listed in the engagement evidence policy. Examples include a customer-approved S3 bucket, a private Git repository for sanitized manifests, a ticket attachment area, or an internal evidence vault. The bot must not use covert channels or unapproved endpoints.

| Step | Action | Control |
|---|---|---|
| 1 | Load destination allowlist. | Reject unknown endpoints. |
| 2 | Confirm package encryption status. | Confidential evidence must be encrypted before transfer. |
| 3 | Upload or hand off through approved tooling. | Capture destination identifier and transfer timestamp. |
| 4 | Verify remote hash where supported. | Record remote hash or checksum response. |
| 5 | Notify OPERATOR with package ID and manifest path. | Do not include sensitive payloads in the queue message. |

## Procedure: Chain of Custody

Chain-of-custody records must be append-only. Each event includes the actor, action, timestamp, source hash, resulting hash, authorization reference, and previous event hash. This creates a tamper-evident event chain suitable for later review.

| Field | Description |
|---|---|
| `event_id` | Unique event identifier. |
| `timestamp` | UTC timestamp in ISO 8601 format. |
| `actor` | Bot, operator, or system performing the action. |
| `action` | Intake, classify, package, encrypt, transfer, receive, compact, or purge. |
| `source_sha256` | Hash of the evidence before the action. |
| `result_sha256` | Hash of the resulting artifact. |
| `previous_event_sha256` | Hash of the prior custody event for the package. |
| `authorization_reference` | Engagement authorization identifier. |

## Procedure: Automated Evidence Packaging

Automated packaging converts a finding into a complete package. The process should use deterministic archive options, sorted file lists, and reproducible manifests. The package name should include the engagement identifier, finding identifier, classification, and timestamp.

| Step | Action | Failure Handling |
|---|---|---|
| 1 | Create workspace under `memory/evidence/<engagement_id>/workspaces/<finding_id>/`. | Abort if workspace exists unless `--resume` is requested. |
| 2 | Copy approved evidence into `raw/`. | Hash after copy and compare with source. |
| 3 | Generate derived summaries and redactions. | Preserve source references. |
| 4 | Write manifest and custody event. | Abort if manifest cannot be written. |
| 5 | Archive and encrypt according to classification. | Remove unencrypted temporary archive if policy requires. |

## Procedure: Knowledge Base Compaction

Knowledge-base compaction reduces raw bot output into useful operational memory. ARCHIVIST should deduplicate repeated findings, preserve source hashes, and write concise summaries to `memory/`, `.learnings/`, or the relevant `knowledge/gateway_profiles/` directory.

| Step | Action | Output |
|---|---|---|
| 1 | Read eligible source files. | Source inventory with hashes. |
| 2 | Remove duplicates by content hash and semantic similarity. | Deduplication report. |
| 3 | Extract stable lessons, indicators, and procedure changes. | Compacted Markdown and JSON records. |
| 4 | Link each summary to evidence manifests. | Traceability map. |
| 5 | Open a git commit for sanitized compaction updates. | Version-controlled record. |

## Git Integration

ARCHIVIST may use git to version-control sanitized manifests, indexes, summaries, and procedure updates. It must not commit raw secrets, credential dumps, restricted regulated data, private keys, or unredacted customer data. Before committing, the bot should run secret scanning if available and verify that `.gitignore` excludes temporary staging directories and unencrypted restricted packages.

| Git Artifact | Commit Policy |
|---|---|
| Manifest JSON and JSONL | Allowed when it contains hashes and metadata only. |
| Redacted summaries | Allowed after review. |
| Encrypted evidence package | Allowed only if the engagement policy explicitly permits repository storage. |
| Raw evidence | Usually prohibited unless explicitly approved. |
| Private keys or credentials | Always prohibited. |

## Stop Conditions and Escalation

ARCHIVIST must stop and notify OPERATOR if it detects unapproved storage destinations, missing authorization, restricted data without explicit approval, encryption failure, hash mismatch, custody chain discontinuity, repository secret-scan alerts, or unexpected production credentials. The stop event must include enough metadata for triage without exposing the sensitive content.

## References

[1]: https://csrc.nist.gov/publications/detail/sp/800-86/final "NIST SP 800-86: Guide to Integrating Forensic Techniques into Incident Response"
[2]: https://csrc.nist.gov/publications/detail/sp/800-61/rev-2/final "NIST SP 800-61 Rev. 2: Computer Security Incident Handling Guide"
