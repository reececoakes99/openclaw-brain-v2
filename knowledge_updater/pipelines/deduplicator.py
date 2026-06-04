#!/usr/bin/env python3
"""Content-aware deduplication for OpenClaw knowledge updates.

The deduplicator accepts heterogeneous intelligence records, computes stable
content hashes over canonicalized fields, performs fuzzy similarity comparison,
and resolves conflicts by timestamp and source confidence. It is deterministic
and usable both as a library and as a CLI for JSON/JSONL files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Tuple

Record = Dict[str, Any]

TIMESTAMP_FIELDS = ("updated_at", "last_seen", "collected_at", "timestamp", "created_at", "first_seen")
VOLATILE_FIELDS = {
    "collected_at",
    "updated_at",
    "last_seen",
    "timestamp",
    "scan_id",
    "run_id",
    "uuid",
    "_hash",
    "content_hash",
    "dedup_key",
}
IDENTITY_FIELDS = ("id", "ioc", "cve_id", "domain", "host", "ip", "url", "fingerprint", "asset_id")


def parse_timestamp(value: Any) -> datetime:
    """Parse common timestamp formats; unknown values become the Unix epoch."""
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value), tz=timezone.utc)
    if isinstance(value, str) and value.strip():
        text = value.strip().replace("Z", "+00:00")
        for fmt in (None, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                if fmt is None:
                    parsed = datetime.fromisoformat(text)
                else:
                    parsed = datetime.strptime(text, fmt)
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed.astimezone(timezone.utc)
            except ValueError:
                continue
    return datetime.fromtimestamp(0, tz=timezone.utc)


def best_timestamp(record: Mapping[str, Any]) -> datetime:
    for field_name in TIMESTAMP_FIELDS:
        if field_name in record:
            return parse_timestamp(record[field_name])
    return datetime.fromtimestamp(0, tz=timezone.utc)


def normalize_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return re.sub(r"\s+", " ", value.strip().lower())
    return value


def canonicalize(value: Any, *, drop_volatile: bool = True) -> Any:
    """Return a JSON-serializable representation with stable ordering."""
    if isinstance(value, Mapping):
        result: Dict[str, Any] = {}
        for key in sorted(value):
            if drop_volatile and key in VOLATILE_FIELDS:
                continue
            if value[key] in (None, "", [], {}):
                continue
            result[str(key)] = canonicalize(value[key], drop_volatile=drop_volatile)
        return result
    if isinstance(value, list):
        return sorted((canonicalize(item, drop_volatile=drop_volatile) for item in value), key=lambda item: json.dumps(item, sort_keys=True))
    return normalize_scalar(value)


def content_hash(record: Mapping[str, Any]) -> str:
    payload = json.dumps(canonicalize(record), sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def identity_key(record: Mapping[str, Any]) -> Optional[str]:
    for field_name in IDENTITY_FIELDS:
        value = record.get(field_name)
        if isinstance(value, str) and value.strip():
            return f"{field_name}:{value.strip().lower()}"
        if value is not None and not isinstance(value, (dict, list)):
            return f"{field_name}:{value}"
    return None


def similarity(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    left_text = json.dumps(canonicalize(left), sort_keys=True, ensure_ascii=False)
    right_text = json.dumps(canonicalize(right), sort_keys=True, ensure_ascii=False)
    return SequenceMatcher(None, left_text, right_text).ratio()


def confidence(record: Mapping[str, Any]) -> float:
    value = record.get("confidence", record.get("score", 50))
    try:
        return max(0.0, min(100.0, float(value)))
    except (TypeError, ValueError):
        return 50.0


def merge_records(existing: Record, incoming: Record) -> Record:
    """Merge duplicate records using newest timestamp, confidence, and provenance."""
    existing_ts = best_timestamp(existing)
    incoming_ts = best_timestamp(incoming)
    primary, secondary = (incoming, existing) if incoming_ts >= existing_ts else (existing, incoming)
    merged: Record = dict(secondary)
    merged.update({k: v for k, v in primary.items() if v not in (None, "", [], {})})

    sources = set()
    for record in (existing, incoming):
        source = record.get("source") or record.get("provider")
        if isinstance(source, str) and source:
            sources.add(source)
        for item in record.get("sources", []) if isinstance(record.get("sources"), list) else []:
            if isinstance(item, str):
                sources.add(item)
    if sources:
        merged["sources"] = sorted(sources)

    merged["confidence"] = max(confidence(existing), confidence(incoming))
    merged["first_seen"] = min(best_timestamp(existing), best_timestamp(incoming)).isoformat()
    merged["last_seen"] = max(existing_ts, incoming_ts).isoformat()
    merged["content_hash"] = content_hash(merged)
    return merged


@dataclass
class DeduplicationReport:
    input_count: int = 0
    output_count: int = 0
    exact_duplicates: int = 0
    fuzzy_duplicates: int = 0
    identity_collisions: int = 0
    records: List[Record] = field(default_factory=list)


class Deduplicator:
    def __init__(self, fuzzy_threshold: float = 0.88) -> None:
        self.fuzzy_threshold = fuzzy_threshold

    def deduplicate(self, records: Iterable[Mapping[str, Any]]) -> DeduplicationReport:
        report = DeduplicationReport()
        by_hash: Dict[str, Record] = {}
        by_identity: Dict[str, str] = {}

        for raw in records:
            report.input_count += 1
            record: Record = dict(raw)
            hsh = content_hash(record)
            record["content_hash"] = hsh
            ident = identity_key(record)

            if hsh in by_hash:
                by_hash[hsh] = merge_records(by_hash[hsh], record)
                report.exact_duplicates += 1
                continue

            if ident and ident in by_identity:
                current_hash = by_identity[ident]
                by_hash[current_hash] = merge_records(by_hash[current_hash], record)
                report.identity_collisions += 1
                continue

            fuzzy_match: Optional[Tuple[str, Record]] = None
            for candidate_hash, candidate in by_hash.items():
                if similarity(candidate, record) >= self.fuzzy_threshold:
                    fuzzy_match = (candidate_hash, candidate)
                    break

            if fuzzy_match:
                candidate_hash, candidate = fuzzy_match
                merged = merge_records(candidate, record)
                new_hash = merged["content_hash"]
                if new_hash != candidate_hash:
                    del by_hash[candidate_hash]
                by_hash[new_hash] = merged
                if ident:
                    by_identity[ident] = new_hash
                report.fuzzy_duplicates += 1
                continue

            by_hash[hsh] = record
            if ident:
                by_identity[ident] = hsh

        report.records = sorted(by_hash.values(), key=lambda item: best_timestamp(item), reverse=True)
        report.output_count = len(report.records)
        return report


def load_records(path: Path) -> List[Record]:
    text = path.read_text(encoding="utf-8")
    if path.suffix == ".jsonl":
        return [json.loads(line) for line in text.splitlines() if line.strip()]
    data = json.loads(text)
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("records", "items", "findings", "cves", "targets", "iocs"):
            if isinstance(data.get(key), list):
                return data[key]
        return [data]
    raise ValueError(f"Unsupported JSON payload in {path}")


def write_records(path: Path, records: List[Record], report: DeduplicationReport) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input_count": report.input_count,
        "output_count": report.output_count,
        "exact_duplicates": report.exact_duplicates,
        "fuzzy_duplicates": report.fuzzy_duplicates,
        "identity_collisions": report.identity_collisions,
        "records": records,
    }
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Deduplicate OpenClaw knowledge records")
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--threshold", type=float, default=0.88)
    args = parser.parse_args()
    report = Deduplicator(args.threshold).deduplicate(load_records(args.input))
    write_records(args.output, report.records, report)
    print(json.dumps({
        "input_count": report.input_count,
        "output_count": report.output_count,
        "exact_duplicates": report.exact_duplicates,
        "fuzzy_duplicates": report.fuzzy_duplicates,
        "identity_collisions": report.identity_collisions,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
