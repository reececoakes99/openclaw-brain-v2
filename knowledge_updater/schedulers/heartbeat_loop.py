#!/usr/bin/env python3
"""Long-running OpenClaw heartbeat scheduler.

This wrapper runs the existing heartbeat health check on a fixed interval so it
can be managed by Docker Compose or systemd without relying on cron.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from knowledge_updater.schedulers import heartbeat

LOG = logging.getLogger("openclaw.heartbeat_loop")
STOP = False


def _handle_stop(signum: int, frame: object) -> None:
    global STOP
    STOP = True
    LOG.info("received signal %s; stopping heartbeat loop", signum)


def _interval_seconds() -> int:
    raw = os.getenv("BOT_HEARTBEAT_INTERVAL_SECONDS", "300")
    try:
        value = int(raw)
    except ValueError:
        value = 300
    return max(30, value)


def main() -> int:
    logging.basicConfig(
        level=os.getenv("OPENCLAW_LOG_LEVEL", "INFO"),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)

    interval = _interval_seconds()
    LOG.info("starting heartbeat loop with interval=%ss", interval)

    while not STOP:
        started = time.monotonic()
        try:
            heartbeat.main()
        except Exception:
            LOG.exception("heartbeat run failed")
        elapsed = time.monotonic() - started
        sleep_for = max(1, interval - int(elapsed))
        for _ in range(sleep_for):
            if STOP:
                break
            time.sleep(1)

    LOG.info("heartbeat loop stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
