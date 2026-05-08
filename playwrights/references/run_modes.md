# Run Modes

## Local Execution

### Interactive (Dev Mode)

```python
import asyncio
from playwright.async_api import async_playwright

async def dev_run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto("https://example.com")

        # Debug: print DOM state
        content = await page.content()
        print(content[:1000])

        await asyncio.get_event_loop().create_task(asyncio.Event().wait())  # Keep open

asyncio.run(dev_run())
```

### Scripted (CLI)

```bash
python -m playwrights.scripts.run_worker --task-id <uuid> --verbose
```

## Redis Queue Mode

### Enqueue Task

```python
# scripts/queue_task.py
import redis, json, sys, argparse
from uuid import uuid4

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", required=True, help="Task JSON string or @filepath")
    parser.add_argument("--queue", default="playwright_tasks")
    args = parser.parse_args()

    task_str = args.task
    if task_str.startswith("@"):
        with open(task_str[1:]) as f:
            task_str = f.read()

    task = json.loads(task_str)
    if "task_id" not in task:
        task["task_id"] = str(uuid4())

    r = redis.Redis(host="localhost", port=6379)
    r.rpush(args.queue, json.dumps(task))
    print(f"Queued task {task['task_id']}")

if __name__ == "__main__":
    main()
```

### Worker

```python
# scripts/run_worker.py
import redis, json, asyncio
from playwright.async_api import async_playwright

async def run_task(task_json: dict):
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()
        for step in task_json.get("steps", []):
            action = step["action"]
            if action == "navigate":
                await page.goto(step["target"], wait_until=step.get("wait_until", "load"))
            elif action == "click":
                await page.click(step["selector"], timeout=step.get("timeout", 5000))
            elif action == "fill":
                await page.fill(step["selector"], step["value"])
            elif action == "screenshot":
                await page.screenshot(path=step["path"])

async def main():
    r = redis.Redis(host="localhost", port=6379)
    while True:
        raw = r.blpop("playwright_tasks", timeout=30)
        if raw:
            task_json = json.loads(raw[1])
            task_id = task_json["task_id"]
            print(f"Running task {task_id}")
            try:
                await run_task(task_json)
                r.set(f"result:{task_id}", json.dumps({"status": "done"}))
            except Exception as e:
                r.set(f"result:{task_id}", json.dumps({"status": "error", "error": str(e)}))

if __name__ == "__main__":
    asyncio.run(main())
```

## CI / Headless Mode

```bash
# CI runner script
#!/bin/bash
set -e

PLAYWRIGHT_BROWSERS_PATH=/tmp/pw-browsers \
  python scripts/run_worker.py \
    --task-id "$TASK_ID" \
    --browser chromium \
    --sandbox=false \
    --output /tmp/artifacts/
```

## Docker

```dockerfile
FROM python:3.12-slim

RUN pip install playwright \
  && playwright install --with-deps chromium

WORKDIR /app
COPY . .

CMD ["python", "scripts/run_worker.py"]
```

## Versioned / Reproducible Runs

Store task snapshots in PostgreSQL:

```sql
CREATE TABLE task_versions (
    id SERIAL PRIMARY KEY,
    task_id UUID REFERENCES task_runs(task_id),
    version INT,
    steps_snapshot JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(task_id, version)
);

CREATE TABLE task_snapshots (
    snapshot_id UUID PRIMARY KEY,
    task_definition JSONB,
    git_commit TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

Before running, snapshot task:
```python
def snapshot_task(task_json: dict, git_commit: str) -> str:
    snapshot_id = str(uuid4())
    db.execute("""
        INSERT INTO task_snapshots (snapshot_id, task_definition, git_commit)
        VALUES (%s, %s, %s)
    """, snapshot_id, json.dumps(task_json), git_commit)
    return snapshot_id
```

Re-run from snapshot:
```python
def replay_task(snapshot_id: str):
    row = db.fetchone("SELECT task_definition FROM task_snapshots WHERE snapshot_id = %s", snapshot_id)
    task = row["task_definition"]
    # Inject into queue
    r.rpush("playwright_tasks", json.dumps(task))
```
