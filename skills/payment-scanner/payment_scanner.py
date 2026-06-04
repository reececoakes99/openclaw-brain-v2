#!/usr/bin/env python3
"""Authorized payment-surface fingerprint scanner.

Performs non-invasive HTTP/TLS metadata collection for explicitly allowlisted
hosts and writes normalized findings for later enrichment.
"""

from __future__ import annotations

import argparse
import json
import socket
import ssl
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "knowledge" / "gateway_profiles" / "payment_scan_results.json"


@dataclass
class PaymentSurface:
    url: str
    host: str
    observed_at: str
    status_code: Optional[int]
    server: Optional[str]
    tls_subject: Optional[str]
    tls_issuer: Optional[str]
    tls_not_after: Optional[str]
    detected_categories: List[str]
    errors: List[str]


def tls_metadata(host: str, port: int = 443) -> Dict[str, Optional[str]]:
    context = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=8) as sock:
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
    subject = ", ".join("=".join(part) for item in cert.get("subject", []) for part in item)
    issuer = ", ".join("=".join(part) for item in cert.get("issuer", []) for part in item)
    return {"subject": subject, "issuer": issuer, "not_after": cert.get("notAfter")}


def classify(headers: Dict[str, str], body: str) -> List[str]:
    haystack = "\n".join([json.dumps(headers), body[:4096]]).lower()
    categories: List[str] = []
    markers = {
        "checkout": ["checkout", "payment", "pay now"],
        "3ds": ["three-d", "3ds", "acs", "challenge"],
        "tokenization": ["token", "vault", "network token"],
        "iso8583_gateway": ["iso8583", "stan", "retrieval reference"],
        "pci_controls": ["pci", "cardholder", "pan"],
    }
    for category, needles in markers.items():
        if any(needle in haystack for needle in needles):
            categories.append(category)
    return categories


def scan(url: str) -> PaymentSurface:
    parsed = urlparse(url)
    host = parsed.hostname or url
    errors: List[str] = []
    status_code = None
    server = None
    body = ""
    headers: Dict[str, str] = {}
    try:
        response = requests.get(url, timeout=15, headers={"User-Agent": "OpenClaw-Authorized-Scanner/1.0"})
        status_code = response.status_code
        server = response.headers.get("server")
        headers = dict(response.headers)
        body = response.text
    except requests.RequestException as exc:
        errors.append(str(exc))
    tls = {"subject": None, "issuer": None, "not_after": None}
    if parsed.scheme == "https" or parsed.port == 443:
        try:
            tls = tls_metadata(host, parsed.port or 443)
        except Exception as exc:
            errors.append(f"tls: {exc}")
    return PaymentSurface(url, host, datetime.now(timezone.utc).isoformat(), status_code, server, tls["subject"], tls["issuer"], tls["not_after"], classify(headers, body), errors)


def main() -> int:
    parser = argparse.ArgumentParser(description="Non-invasive payment surface scanner")
    parser.add_argument("urls", nargs="+")
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    allowed = {line.strip().lower() for line in args.allowlist.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}
    results = []
    for url in args.urls:
        host = (urlparse(url).hostname or "").lower()
        if host not in allowed:
            raise PermissionError(f"{host} is outside the authorized allowlist")
        results.append(scan(url))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"results": len(results), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
