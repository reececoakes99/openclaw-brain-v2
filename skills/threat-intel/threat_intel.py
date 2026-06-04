#!/usr/bin/env python3
"""Threat intelligence collection helpers for authorized OpenClaw workflows.

The collector normalizes indicators, queries public/API-backed intelligence
sources when credentials are available, and writes deterministic JSON output that
can be consumed by the knowledge updater and bot queue. Network calls are rate
limited by source and never fabricate results when credentials are absent.
"""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import quote

import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "knowledge" / "threat_intel" / "indicators.jsonl"

DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))*\.[A-Za-z]{2,63}$")
HASH_RE = re.compile(r"^[A-Fa-f0-9]{32}$|^[A-Fa-f0-9]{40}$|^[A-Fa-f0-9]{64}$")


@dataclass
class IntelRecord:
    indicator: str
    indicator_type: str
    source: str
    observed_at: str
    verdict: str
    confidence: float
    categories: List[str]
    raw: Dict[str, Any]


def indicator_type(value: str) -> str:
    stripped = value.strip()
    try:
        ipaddress.ip_address(stripped)
        return "ip"
    except ValueError:
        pass
    if HASH_RE.match(stripped):
        return "hash"
    if DOMAIN_RE.match(stripped):
        return "domain"
    if stripped.startswith(("http://", "https://")):
        return "url"
    raise ValueError(f"Unsupported indicator format: {value}")


class ThreatIntelClient:
    def __init__(self, timeout: float = 20.0, sleep_seconds: float = 1.0) -> None:
        self.session = requests.Session()
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds

    def query_virustotal(self, indicator: str, kind: str) -> Optional[IntelRecord]:
        token = os.getenv("VIRUSTOTAL_API_KEY")
        if not token:
            return None
        vt_type = {"ip": "ip_addresses", "domain": "domains", "url": "urls", "hash": "files"}[kind]
        identifier = hashlib.sha256(indicator.encode()).hexdigest() if kind == "url" else indicator
        url = f"https://www.virustotal.com/api/v3/{vt_type}/{quote(identifier, safe='')}"
        response = self.session.get(url, headers={"x-apikey": token}, timeout=self.timeout)
        if response.status_code == 404:
            return IntelRecord(indicator, kind, "virustotal", now(), "unknown", 0.2, [], {"status": 404})
        response.raise_for_status()
        data = response.json()
        stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        malicious = int(stats.get("malicious", 0) or 0)
        suspicious = int(stats.get("suspicious", 0) or 0)
        total = sum(int(v or 0) for v in stats.values()) or 1
        score = min(1.0, (malicious + suspicious * 0.5) / total)
        verdict = "malicious" if malicious else "suspicious" if suspicious else "benign"
        return IntelRecord(indicator, kind, "virustotal", now(), verdict, round(score, 3), ["reputation"], data)

    def query_urlhaus(self, indicator: str, kind: str) -> Optional[IntelRecord]:
        if kind not in {"url", "domain", "ip"}:
            return None
        endpoint = "https://urlhaus-api.abuse.ch/v1/"
        if kind == "url":
            path, payload = "url/", {"url": indicator}
        elif kind == "domain":
            path, payload = "host/", {"host": indicator}
        else:
            path, payload = "host/", {"host": indicator}
        response = self.session.post(endpoint + path, data=payload, timeout=self.timeout)
        response.raise_for_status()
        data = response.json()
        status = data.get("query_status")
        verdict = "malicious" if status == "ok" else "unknown"
        confidence = 0.85 if status == "ok" else 0.1
        categories = ["malware_distribution"] if status == "ok" else []
        return IntelRecord(indicator, kind, "urlhaus", now(), verdict, confidence, categories, data)

    def query_indicator(self, indicator: str) -> List[IntelRecord]:
        kind = indicator_type(indicator)
        records: List[IntelRecord] = []
        for func in (self.query_virustotal, self.query_urlhaus):
            try:
                result = func(indicator, kind)
                if result:
                    records.append(result)
            except requests.HTTPError as exc:
                records.append(IntelRecord(indicator, kind, func.__name__.replace("query_", ""), now(), "error", 0.0, ["collection_error"], {"error": str(exc), "status_code": getattr(exc.response, "status_code", None)}))
            except requests.RequestException as exc:
                records.append(IntelRecord(indicator, kind, func.__name__.replace("query_", ""), now(), "error", 0.0, ["collection_error"], {"error": str(exc)}))
            time.sleep(self.sleep_seconds)
        if not records:
            records.append(IntelRecord(indicator, kind, "local_classifier", now(), "unqueried", 0.0, ["missing_credentials"], {"reason": "No configured API key or supported public source"}))
        return records


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_jsonl(records: Iterable[IntelRecord], output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output.open("a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(asdict(record), sort_keys=True) + "\n")
            count += 1
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect threat intelligence for authorized indicators")
    parser.add_argument("indicators", nargs="*", help="IP addresses, domains, URLs, or hashes")
    parser.add_argument("--input", type=Path, help="Text file containing one indicator per line")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--sleep", type=float, default=1.0)
    args = parser.parse_args()
    indicators = list(args.indicators)
    if args.input:
        indicators.extend(line.strip() for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#"))
    if not indicators:
        raise SystemExit("Provide at least one indicator or --input file")
    client = ThreatIntelClient(sleep_seconds=args.sleep)
    all_records: List[IntelRecord] = []
    for indicator in indicators:
        all_records.extend(client.query_indicator(indicator))
    count = write_jsonl(all_records, args.output)
    print(json.dumps({"written": count, "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
