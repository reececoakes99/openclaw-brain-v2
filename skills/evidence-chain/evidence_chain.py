#!/usr/bin/env python3
"""Evidence chain packaging, hashing, and optional local encryption.

This module supports authorized assessments by producing tamper-evident evidence
packages with SHA-256 manifests and optional GPG/age encryption when the operator
has configured recipients. It does not transmit evidence; staging locations are
local filesystem paths that can be version controlled or reviewed before export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tarfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE = ROOT / "knowledge" / "evidence" / "packages"


@dataclass
class EvidenceItem:
    path: str
    sha256: str
    size: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect_items(paths: Iterable[Path]) -> List[EvidenceItem]:
    items: List[EvidenceItem] = []
    for source in paths:
        if source.is_dir():
            for path in sorted(p for p in source.rglob("*") if p.is_file()):
                items.append(EvidenceItem(str(path), sha256_file(path), path.stat().st_size))
        elif source.is_file():
            items.append(EvidenceItem(str(source), sha256_file(source), source.stat().st_size))
        else:
            raise FileNotFoundError(source)
    return items


def create_package(paths: List[Path], stage_dir: Path = DEFAULT_STAGE, label: str = "evidence") -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    package_dir = stage_dir / f"{label}_{timestamp}"
    package_dir.mkdir(parents=True, exist_ok=True)
    manifest_items = collect_items(paths)
    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "label": label,
        "items": [asdict(item) for item in manifest_items],
        "chain_sha256": hashlib.sha256("".join(item.sha256 for item in manifest_items).encode()).hexdigest(),
    }
    manifest_path = package_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    archive_path = stage_dir / f"{label}_{timestamp}.tar.gz"
    with tarfile.open(archive_path, "w:gz") as tar:
        tar.add(manifest_path, arcname="manifest.json")
        for source in paths:
            tar.add(source, arcname=source.name)
    (archive_path.with_suffix(archive_path.suffix + ".sha256")).write_text(f"{sha256_file(archive_path)}  {archive_path.name}\n", encoding="utf-8")
    shutil.rmtree(package_dir)
    return archive_path


def encrypt_package(archive: Path, recipient: Optional[str] = None, passphrase_file: Optional[Path] = None) -> Optional[Path]:
    if recipient and shutil.which("gpg"):
        output = archive.with_suffix(archive.suffix + ".gpg")
        subprocess.run(["gpg", "--batch", "--yes", "--trust-model", "always", "--recipient", recipient, "--encrypt", "--output", str(output), str(archive)], check=True)
        return output
    if passphrase_file and shutil.which("gpg"):
        output = archive.with_suffix(archive.suffix + ".gpg")
        subprocess.run(["gpg", "--batch", "--yes", "--symmetric", "--cipher-algo", "AES256", "--passphrase-file", str(passphrase_file), "--output", str(output), str(archive)], check=True)
        return output
    if recipient and shutil.which("age"):
        output = archive.with_suffix(archive.suffix + ".age")
        subprocess.run(["age", "-r", recipient, "-o", str(output), str(archive)], check=True)
        return output
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Package authorized evidence with manifest hashing")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--label", default="evidence")
    parser.add_argument("--stage-dir", type=Path, default=DEFAULT_STAGE)
    parser.add_argument("--recipient", help="GPG or age recipient for encryption")
    parser.add_argument("--passphrase-file", type=Path, help="GPG symmetric passphrase file")
    args = parser.parse_args()
    archive = create_package(args.paths, args.stage_dir, args.label)
    encrypted = encrypt_package(archive, args.recipient, args.passphrase_file)
    print(json.dumps({"archive": str(archive), "encrypted": str(encrypted) if encrypted else None, "sha256": sha256_file(encrypted or archive)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
