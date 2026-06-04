#!/usr/bin/env python3
"""Durable JSONL queue utilities for OpenClaw bot coordination."""

from __future__ import annotations

import argparse
import fcntl
import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[2]
QUEUE_DIR = ROOT / "knowledge" / "bot_queue"


@dataclass
class QueueMessage:
    id: str
    created_at: str
    sender: str
    recipient: str
    priority: str
    message_type: str
    payload: Dict[str, Any]
    status: str = "queued"


def queue_path(name: str) -> Path:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    return QUEUE_DIR / f"{name}.jsonl"


def enqueue(name: str, sender: str, recipient: str, message_type: str, payload: Dict[str, Any], priority: str = "normal") -> QueueMessage:
    msg = QueueMessage(str(uuid.uuid4()), datetime.now(timezone.utc).isoformat(), sender, recipient, priority, message_type, payload)
    path = queue_path(name)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(asdict(msg), sort_keys=True) + "\n")
        fcntl.flock(handle, fcntl.LOCK_UN)
    return msg


def read_queue(name: str) -> List[QueueMessage]:
    path = queue_path(name)
    if not path.exists():
        return []
    messages: List[QueueMessage] = []
    with path.open("r", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_SH)
        for line in handle:
            if line.strip():
                messages.append(QueueMessage(**json.loads(line)))
        fcntl.flock(handle, fcntl.LOCK_UN)
    return messages


def acknowledge(name: str, message_id: str) -> bool:
    path = queue_path(name)
    messages = read_queue(name)
    changed = False
    with path.open("w", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        for msg in messages:
            if msg.id == message_id:
                msg.status = "acknowledged"
                changed = True
            handle.write(json.dumps(asdict(msg), sort_keys=True) + "\n")
        fcntl.flock(handle, fcntl.LOCK_UN)
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description="OpenClaw bot queue utility")
    sub = parser.add_subparsers(dest="command", required=True)
    push = sub.add_parser("enqueue")
    push.add_argument("queue")
    push.add_argument("--sender", required=True)
    push.add_argument("--recipient", required=True)
    push.add_argument("--type", required=True)
    push.add_argument("--payload", required=True, help="JSON object")
    push.add_argument("--priority", default="normal")
    pull = sub.add_parser("read")
    pull.add_argument("queue")
    ack = sub.add_parser("ack")
    ack.add_argument("queue")
    ack.add_argument("message_id")
    args = parser.parse_args()
    if args.command == "enqueue":
        msg = enqueue(args.queue, args.sender, args.recipient, args.type, json.loads(args.payload), args.priority)
        print(json.dumps(asdict(msg), indent=2, sort_keys=True))
    elif args.command == "read":
        print(json.dumps([asdict(msg) for msg in read_queue(args.queue)], indent=2, sort_keys=True))
    elif args.command == "ack":
        print(json.dumps({"acknowledged": acknowledge(args.queue, args.message_id)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
