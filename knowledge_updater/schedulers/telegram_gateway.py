#!/usr/bin/env python3
"""Telegram gateway for OpenClaw bot queues.

The gateway polls Telegram for operator commands, writes validated work items to
JSON queue files, and reports current queue health. It uses only the Telegram Bot
HTTP API and local JSON state, so it runs under Docker Compose or systemd without
extra services.
"""

from __future__ import annotations

import json
import logging
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(os.getenv("OPENCLAW_ROOT", Path(__file__).resolve().parents[2])).resolve()
QUEUE_DIR = ROOT / "knowledge" / "bot_queue"
LOG_DIR = ROOT / "knowledge" / "bot_activity_logs" / "gateway"
LOG_FILE = LOG_DIR / "telegram_gateway.log"
STATE_FILE = QUEUE_DIR / "telegram_gateway_state.json"
HEALTH_FILE = ROOT / "knowledge" / "bot_activity_logs" / "health_check.json"
DOMAIN_RE = re.compile(r"^(?=.{1,253}$)(?!-)[A-Za-z0-9-]{1,63}(?<!-)(?:\.(?!-)[A-Za-z0-9-]{1,63}(?<!-))+$")
STOP = False

LOG = logging.getLogger("openclaw.telegram_gateway")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def ensure_layout() -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    for path in [
        QUEUE_DIR / "recon_pending.json",
        QUEUE_DIR / "intel_pending.json",
        QUEUE_DIR / "intel_scored.json",
        QUEUE_DIR / "hunter_queue.json",
        QUEUE_DIR / "ops_ready.json",
        QUEUE_DIR / "operations_pending.json",
        QUEUE_DIR / "dead_letter.json",
        QUEUE_DIR / "telegram_commands.json",
    ]:
        if not path.exists():
            write_json(path, {"version": 1, "queue": [], "last_updated": None, "total_pending": 0})
    if not STATE_FILE.exists():
        write_json(STATE_FILE, {"version": 1, "last_update_id": None, "last_poll_at": None, "last_error": None})


def read_json(path: Path, default: Any) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, sort_keys=True)
        handle.write("\n")
    tmp.replace(path)


def queue_payload(path: Path) -> dict[str, Any]:
    data = read_json(path, {"version": 1, "queue": [], "last_updated": None, "total_pending": 0})
    if isinstance(data, list):
        data = {"version": 1, "queue": data, "last_updated": None, "total_pending": len(data)}
    data.setdefault("version", 1)
    data.setdefault("queue", [])
    data.setdefault("last_updated", None)
    data["total_pending"] = len(data["queue"])
    return data


def enqueue(queue_name: str, item: dict[str, Any]) -> dict[str, Any]:
    path = QUEUE_DIR / queue_name
    data = queue_payload(path)
    item = dict(item)
    item.setdefault("id", f"{queue_name}:{utc_now()}:{len(data['queue']) + 1}")
    item.setdefault("status", "pending")
    item.setdefault("queued_at", utc_now())
    data["queue"].append(item)
    data["last_updated"] = utc_now()
    data["total_pending"] = len(data["queue"])
    write_json(path, data)
    return item


def update_health(status: str, error: str | None = None) -> None:
    health = read_json(HEALTH_FILE, {"version": 1})
    health["timestamp"] = utc_now()
    health.setdefault("gateway", {})
    health["gateway"].update({"status": status, "last_run": utc_now(), "last_error": error})
    write_json(HEALTH_FILE, health)


def telegram_request(method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    url = f"https://api.telegram.org/bot{token}/{method}"
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        parsed = json.loads(response.read().decode("utf-8"))
    if not parsed.get("ok"):
        raise RuntimeError(f"Telegram API returned not ok for {method}: {parsed}")
    return parsed


def send_message(chat_id: str | int, text: str) -> None:
    telegram_request("sendMessage", {"chat_id": chat_id, "text": text})


def queue_summary() -> str:
    rows = []
    for path in sorted(QUEUE_DIR.glob("*.json")):
        if path.name.endswith("_state.json"):
            continue
        data = queue_payload(path)
        rows.append(f"{path.name}: {data['total_pending']} pending")
    return "\n".join(rows) if rows else "No queue files found."


def handle_command(chat_id: int, text: str, update_id: int) -> None:
    command = text.strip()
    enqueue("telegram_commands.json", {"update_id": update_id, "chat_id": chat_id, "command": command})

    if command in {"/start", "/help"}:
        send_message(chat_id, "OpenClaw gateway commands:\n/status\n/queues\n/enqueue recon <domain>")
        return
    if command == "/status":
        health = read_json(HEALTH_FILE, {})
        send_message(chat_id, json.dumps(health, indent=2, sort_keys=True)[:3500])
        return
    if command == "/queues":
        send_message(chat_id, queue_summary())
        return
    if command.startswith("/enqueue "):
        parts = command.split()
        if len(parts) != 3 or parts[1] != "recon" or not DOMAIN_RE.match(parts[2]):
            send_message(chat_id, "Usage: /enqueue recon example.com")
            return
        domain = parts[2].lower()
        item = enqueue("recon_pending.json", {"source": "telegram", "domain": domain, "requested_by_chat_id": chat_id, "update_id": update_id})
        send_message(chat_id, f"Queued recon target {domain}\nQueue item: {item['id']}")
        return
    send_message(chat_id, "Unknown command. Use /help for supported commands.")


def poll_once() -> None:
    state = read_json(STATE_FILE, {"version": 1, "last_update_id": None, "last_poll_at": None, "last_error": None})
    params: dict[str, Any] = {"timeout": 25}
    if state.get("last_update_id") is not None:
        params["offset"] = int(state["last_update_id"]) + 1
    result = telegram_request("getUpdates", params).get("result", [])
    for update in result:
        update_id = int(update["update_id"])
        state["last_update_id"] = update_id
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        text = message.get("text") or ""
        chat_id = chat.get("id")
        if chat_id is not None and text.startswith("/"):
            handle_command(chat_id, text, update_id)
    state["last_poll_at"] = utc_now()
    state["last_error"] = None
    write_json(STATE_FILE, state)
    update_health("active")


def _handle_stop(signum: int, frame: object) -> None:
    global STOP
    STOP = True
    LOG.info("received signal %s; stopping Telegram gateway", signum)


def main() -> int:
    ensure_layout()
    logging.basicConfig(
        level=os.getenv("OPENCLAW_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(LOG_FILE)],
    )
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    interval = max(1, int(os.getenv("BOT_GATEWAY_POLL_INTERVAL_SECONDS", "5")))
    LOG.info("starting Telegram gateway; interval=%ss", interval)
    while not STOP:
        try:
            if os.getenv("TELEGRAM_BOT_TOKEN"):
                poll_once()
            else:
                update_health("idle", "TELEGRAM_BOT_TOKEN is not configured")
                LOG.info("TELEGRAM_BOT_TOKEN is not configured; gateway idle")
                time.sleep(max(interval, 30))
        except (urllib.error.URLError, TimeoutError, RuntimeError, ValueError) as exc:
            update_health("error", str(exc))
            LOG.exception("gateway poll failed")
            time.sleep(max(interval, 10))
        else:
            time.sleep(interval)
    update_health("stopped")
    LOG.info("Telegram gateway stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
