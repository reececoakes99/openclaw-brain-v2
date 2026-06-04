#!/usr/bin/env python3
"""Guarded runner for authorized ISO8583 lab tooling.

The runner enforces a host allowlist for network operations, executes repository
ISO8583 tools, and appends an auditable JSONL transcript with command metadata,
return code, and SHA-256 hashes of file inputs/outputs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shlex
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
RUN_LOG = ROOT / "knowledge" / "gateway_profiles" / "iso8583_live_tool_runs.jsonl"
TOOLS = {
    "parse": ROOT / "neopay" / "scripts" / "parse_iso8583.py",
    "hsm": ROOT / "neopay" / "scripts" / "hsm_simulator.py",
    "mac": ROOT / "neopay" / "scripts" / "mac_generator.py",
    "spdh": ROOT / "neopay" / "scripts" / "spdh_client.py",
    "pcap": ROOT / "neopay" / "scripts" / "pcap_tools.py",
}
NETWORK_TOOLS = {"spdh"}


@dataclass
class ToolRun:
    timestamp: str
    authorization_reference: str
    tool: str
    command: List[str]
    return_code: int
    stdout_sha256: str
    stderr_sha256: str
    input_hashes: dict
    output_path: Optional[str]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_allowlist(path: Optional[Path]) -> set[str]:
    if not path:
        return set()
    return {line.strip().lower() for line in path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.startswith("#")}


def extract_host(args: List[str]) -> Optional[str]:
    for flag in ("--host", "--target"):
        if flag in args:
            index = args.index(flag)
            if index + 1 < len(args):
                value = args[index + 1]
                return (urlparse(value).hostname or value.split(":", 1)[0]).lower()
    return None


def enforce_authorization(tool: str, passthrough: List[str], allowlist: Optional[Path], authorization_reference: str) -> None:
    if not authorization_reference.strip():
        raise PermissionError("An authorization reference is required for all live tool runs")
    if tool in NETWORK_TOOLS:
        hosts = load_allowlist(allowlist)
        host = extract_host(passthrough)
        if not host:
            raise PermissionError("Network tool invocation must include --host or --target")
        if host.lower() not in hosts:
            raise PermissionError(f"{host} is not present in the authorized allowlist")


def collect_file_hashes(args: List[str]) -> dict:
    hashes = {}
    for flag in ("--input", "--config", "--pcap"):
        if flag in args:
            index = args.index(flag)
            if index + 1 < len(args):
                path = Path(args[index + 1])
                if path.exists() and path.is_file():
                    hashes[str(path)] = sha256_file(path)
    return hashes


def run_tool(tool: str, passthrough: List[str], authorization_reference: str, allowlist: Optional[Path], output_path: Optional[Path], run_log: Path) -> ToolRun:
    if tool not in TOOLS:
        raise ValueError(f"Unknown tool {tool}; expected one of {sorted(TOOLS)}")
    enforce_authorization(tool, passthrough, allowlist, authorization_reference)
    command = ["python3", str(TOOLS[tool]), *passthrough]
    completed = subprocess.run(command, cwd=ROOT, text=False, capture_output=True, check=False)
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(completed.stdout)
    run = ToolRun(
        timestamp=datetime.now(timezone.utc).isoformat(),
        authorization_reference=authorization_reference,
        tool=tool,
        command=command,
        return_code=completed.returncode,
        stdout_sha256=sha256_bytes(completed.stdout),
        stderr_sha256=sha256_bytes(completed.stderr),
        input_hashes=collect_file_hashes(passthrough),
        output_path=str(output_path) if output_path else None,
    )
    run_log.parent.mkdir(parents=True, exist_ok=True)
    with run_log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(run), sort_keys=True) + "\n")
    if completed.stdout and not output_path:
        print(completed.stdout.decode("utf-8", errors="replace"), end="")
    if completed.stderr:
        print(completed.stderr.decode("utf-8", errors="replace"), end="")
    return run


def main() -> int:
    parser = argparse.ArgumentParser(description="Run guarded ISO8583 tools with authorization logging")
    parser.add_argument("tool", choices=sorted(TOOLS))
    parser.add_argument("--authorization-reference", required=True)
    parser.add_argument("--allowlist", type=Path)
    parser.add_argument("--output-capture", type=Path)
    parser.add_argument("--run-log", type=Path, default=RUN_LOG)
    parser.add_argument("tool_args", nargs=argparse.REMAINDER, help="Arguments after -- are passed to the selected tool")
    args = parser.parse_args()
    passthrough = args.tool_args[1:] if args.tool_args[:1] == ["--"] else args.tool_args
    run = run_tool(args.tool, passthrough, args.authorization_reference, args.allowlist, args.output_capture, args.run_log)
    print(json.dumps(asdict(run), indent=2, sort_keys=True))
    return run.return_code


if __name__ == "__main__":
    raise SystemExit(main())
