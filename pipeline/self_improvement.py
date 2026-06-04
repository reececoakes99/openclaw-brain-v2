#!/usr/bin/env python3
"""OpenClaw self-improvement engine.

The engine turns operational error logs into reusable prevention rules, scans the
repository for recurrence, applies deterministic safe repairs, and records the
result in the learning ledger. It intentionally limits automatic modification to
low-risk, mechanically verifiable changes; higher-risk findings are emitted as
reviewable patch plans rather than silently changing behavior.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
LEARNINGS_DIR = ROOT / ".learnings"
ERRORS_MD = LEARNINGS_DIR / "ERRORS.md"
LEARNINGS_MD = LEARNINGS_DIR / "LEARNINGS.md"
PATTERNS_JSON = LEARNINGS_DIR / "PATTERNS.json"
REPORTS_DIR = LEARNINGS_DIR / "reports"

ERROR_HEADER_RE = re.compile(r"^### \[(?P<date>[^\]]+)\]\s+(?P<kind>[^—\n]+?)\s+—\s+(?P<component>.+)$")
FIELD_RE = re.compile(r"^- \*\*(?P<key>[^*]+)\*\*:\s*(?P<value>.*)$")
LINE_CONTINUATION_RE = re.compile(r"\\\s+$")
TRAILING_WS_RE = re.compile(r"[ \t]+$", re.MULTILINE)
INVALID_BYTES_ESCAPE_RE = re.compile(r"b(['\"])(.*?)(?<!\\)\\x(?![0-9a-fA-F]{2})", re.DOTALL)


@dataclass
class ErrorEntry:
    date: str
    kind: str
    component: str
    fields: Dict[str, str] = field(default_factory=dict)

    @property
    def pattern_key(self) -> str:
        seed = f"{self.kind}:{self.component}:{self.fields.get('Root Cause', '')}:{self.fields.get('Prevention', '')}"
        slug = re.sub(r"[^a-z0-9]+", "-", seed.lower()).strip("-")[:72]
        digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
        return f"{slug}-{digest}" if slug else digest


@dataclass
class Finding:
    path: str
    category: str
    message: str
    severity: str = "medium"
    line: Optional[int] = None


@dataclass
class AppliedFix:
    path: str
    category: str
    description: str


class SelfImprovementEngine:
    """Parse operational learning material and prevent known failure classes."""

    def __init__(self, repo_root: Path = ROOT) -> None:
        self.repo_root = repo_root
        self.learnings_dir = repo_root / ".learnings"
        self.errors_md = self.learnings_dir / "ERRORS.md"
        self.learnings_md = self.learnings_dir / "LEARNINGS.md"
        self.patterns_json = self.learnings_dir / "PATTERNS.json"
        self.reports_dir = self.learnings_dir / "reports"

    def parse_errors(self) -> List[ErrorEntry]:
        if not self.errors_md.exists():
            return []
        entries: List[ErrorEntry] = []
        current: Optional[ErrorEntry] = None
        for line in self.errors_md.read_text(encoding="utf-8").splitlines():
            header = ERROR_HEADER_RE.match(line)
            if header:
                if current:
                    entries.append(current)
                current = ErrorEntry(
                    date=header.group("date").strip(),
                    kind=header.group("kind").strip(),
                    component=header.group("component").strip(),
                )
                continue
            field_match = FIELD_RE.match(line)
            if field_match and current:
                current.fields[field_match.group("key").strip()] = field_match.group("value").strip()
        if current:
            entries.append(current)
        return entries

    def derive_patterns(self, entries: Sequence[ErrorEntry]) -> List[Dict[str, object]]:
        patterns: Dict[str, Dict[str, object]] = {}
        for entry in entries:
            key = entry.pattern_key
            pattern = patterns.setdefault(key, {
                "pattern_key": key,
                "kind": entry.kind,
                "component": entry.component,
                "root_causes": [],
                "preventions": [],
                "commands": [],
                "occurrences": 0,
                "last_seen": entry.date,
            })
            pattern["occurrences"] = int(pattern["occurrences"]) + 1
            for src, dst in (("Root Cause", "root_causes"), ("Prevention", "preventions"), ("Command", "commands")):
                value = entry.fields.get(src)
                if value and value not in pattern[dst]:
                    pattern[dst].append(value)
            pattern["last_seen"] = max(str(pattern["last_seen"]), entry.date)
        return sorted(patterns.values(), key=lambda item: (-int(item["occurrences"]), str(item["pattern_key"])))

    def write_patterns(self, patterns: Sequence[Mapping[str, object]]) -> None:
        self.learnings_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source": str(self.errors_md.relative_to(self.repo_root)),
            "patterns": list(patterns),
        }
        self.patterns_json.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    def iter_repo_files(self, suffixes: Tuple[str, ...]) -> Iterable[Path]:
        ignored_parts = {".git", "__pycache__", ".pytest_cache", "node_modules", ".venv", "venv"}
        for path in self.repo_root.rglob("*"):
            if any(part in ignored_parts for part in path.parts):
                continue
            if path.is_file() and path.suffix in suffixes:
                yield path

    def scan(self) -> List[Finding]:
        findings: List[Finding] = []
        for path in self.iter_repo_files((".py",)):
            rel = str(path.relative_to(self.repo_root))
            text = path.read_text(encoding="utf-8", errors="replace")
            try:
                ast.parse(text, filename=rel)
            except SyntaxError as exc:
                findings.append(Finding(rel, "python_syntax", exc.msg, "high", exc.lineno))
            for index, line in enumerate(text.splitlines(), start=1):
                if line.startswith(" ") and not line.startswith("    ") and line.strip():
                    findings.append(Finding(rel, "python_indent_width", "Leading spaces are not a multiple of four", "medium", index))
                    break
                if LINE_CONTINUATION_RE.search(line):
                    findings.append(Finding(rel, "line_continuation_trailing_space", "Backslash continuation has trailing whitespace", "medium", index))
                    break
                if INVALID_BYTES_ESCAPE_RE.search(line):
                    findings.append(Finding(rel, "invalid_bytes_escape", "Bytes literal contains a non-hex \\x escape", "high", index))
                    break
        for path in self.iter_repo_files((".json",)):
            rel = str(path.relative_to(self.repo_root))
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                findings.append(Finding(rel, "json_syntax", exc.msg, "high", exc.lineno))
        return findings

    def apply_safe_fixes(self, dry_run: bool = False) -> List[AppliedFix]:
        fixes: List[AppliedFix] = []
        for path in self.iter_repo_files((".py", ".md", ".yaml", ".yml", ".json")):
            original = path.read_text(encoding="utf-8", errors="replace")
            updated = TRAILING_WS_RE.sub("", original)
            if path.suffix == ".py":
                updated = "\n".join(line.rstrip() for line in updated.splitlines()) + ("\n" if updated else "")
            if updated != original:
                fixes.append(AppliedFix(str(path.relative_to(self.repo_root)), "trailing_whitespace", "Removed trailing whitespace"))
                if not dry_run:
                    path.write_text(updated, encoding="utf-8")
        return fixes

    def update_learning_ledger(self, patterns: Sequence[Mapping[str, object]], findings: Sequence[Finding], fixes: Sequence[AppliedFix], dry_run: bool) -> None:
        if dry_run:
            return
        existing = self.learnings_md.read_text(encoding="utf-8") if self.learnings_md.exists() else "# OpenClaw Learnings\n"
        marker = "## Self-Improvement Engine"
        summary = [
            "",
            marker,
            f"### [{datetime.now(timezone.utc).date()}] Repository Hygiene Automation",
            "- **Pattern-Key**: self-improvement-repo-hygiene",
            f"- **Learning**: Parsed {len(patterns)} recurring error pattern(s), detected {len(findings)} current issue(s), and applied {len(fixes)} deterministic safe fix(es).",
            "- **Source**: pipeline/self_improvement.py",
            "- **Prevention**: Run `python3 pipeline/self_improvement.py --apply` before commits that modify pipeline, updater, skill, or bot files.",
        ]
        addition = "\n".join(summary) + "\n"
        if "self-improvement-repo-hygiene" not in existing:
            self.learnings_md.write_text(existing.rstrip() + addition, encoding="utf-8")

    def write_report(self, patterns: Sequence[Mapping[str, object]], findings: Sequence[Finding], fixes: Sequence[AppliedFix]) -> Path:
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = self.reports_dir / f"self_improvement_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "patterns": list(patterns),
            "findings": [finding.__dict__ for finding in findings],
            "applied_fixes": [fix.__dict__ for fix in fixes],
            "git_head": self.git_head(),
        }
        report_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return report_path

    def git_head(self) -> str:
        try:
            completed = subprocess.run(["git", "rev-parse", "HEAD"], cwd=self.repo_root, check=True, text=True, capture_output=True)
            return completed.stdout.strip()
        except Exception:
            return "unknown"

    def run(self, apply: bool = False) -> Dict[str, object]:
        entries = self.parse_errors()
        patterns = self.derive_patterns(entries)
        self.write_patterns(patterns)
        initial_findings = self.scan()
        fixes = self.apply_safe_fixes(dry_run=not apply)
        final_findings = self.scan() if apply else initial_findings
        self.update_learning_ledger(patterns, final_findings, fixes, dry_run=not apply)
        report = self.write_report(patterns, final_findings, fixes)
        return {
            "error_entries": len(entries),
            "patterns": len(patterns),
            "findings": len(final_findings),
            "safe_fixes": len(fixes),
            "report": str(report.relative_to(self.repo_root)),
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run OpenClaw self-improvement analysis and safe repairs")
    parser.add_argument("--apply", action="store_true", help="Apply deterministic safe fixes and update LEARNINGS.md")
    parser.add_argument("--repo-root", type=Path, default=ROOT)
    args = parser.parse_args()
    result = SelfImprovementEngine(args.repo_root.resolve()).run(apply=args.apply)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
