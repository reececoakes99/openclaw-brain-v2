#!/usr/bin/env python3
"""Rate-limited API validation fuzzer for authorized scopes.

The fuzzer requires an explicit allowlist file and confines requests to those
hosts. It performs boundary-condition validation and records reproducible results
without bypass, credential stuffing, or destructive payloads.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from urllib.parse import urlparse

import requests

SAFE_PAYLOADS = ["", "0", "1", "-1", "null", "true", "false", "A" * 256, "../", "'", '"', "<test>"]


@dataclass
class FuzzResult:
    url: str
    method: str
    parameter: str
    payload: str
    status_code: int
    elapsed_ms: float
    length: int
    evidence: str


def load_allowlist(path: Path) -> List[str]:
    hosts = [line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")]
    if not hosts:
        raise ValueError("Allowlist is empty")
    return hosts


def assert_allowed(url: str, allowlist: Iterable[str]) -> None:
    host = (urlparse(url).hostname or "").lower()
    if host not in set(allowlist):
        raise PermissionError(f"{host} is outside the authorized allowlist")


def fuzz(url: str, method: str, parameters: List[str], allowlist: List[str], headers: Optional[Dict[str, str]] = None, rate: float = 1.0) -> List[FuzzResult]:
    assert_allowed(url, allowlist)
    session = requests.Session()
    results: List[FuzzResult] = []
    method = method.upper()
    for parameter in parameters:
        for payload in SAFE_PAYLOADS:
            start = time.perf_counter()
            if method == "GET":
                response = session.get(url, params={parameter: payload}, headers=headers, timeout=20)
            else:
                response = session.request(method, url, json={parameter: payload}, headers=headers, timeout=20)
            elapsed_ms = (time.perf_counter() - start) * 1000
            body = response.text[:2048]
            evidence = "server_error" if response.status_code >= 500 else "client_rejected" if response.status_code >= 400 else "accepted"
            results.append(FuzzResult(url, method, parameter, payload, response.status_code, round(elapsed_ms, 2), len(response.content), evidence))
            time.sleep(max(0.0, rate + random.uniform(0, rate * 0.1)))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Authorized API boundary-condition fuzzer")
    parser.add_argument("--url", required=True)
    parser.add_argument("--method", default="GET")
    parser.add_argument("--param", action="append", required=True)
    parser.add_argument("--allowlist", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rate", type=float, default=1.0, help="Minimum delay between requests in seconds")
    args = parser.parse_args()
    allowlist = load_allowlist(args.allowlist)
    results = fuzz(args.url, args.method, args.param, allowlist, rate=args.rate)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps([asdict(result) for result in results], indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({"results": len(results), "output": str(args.output)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
