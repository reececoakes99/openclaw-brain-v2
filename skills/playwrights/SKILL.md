---
name: playwrights
description: Full-stack browser automation using Python Playwright. Trigger when users ask to automate browser tasks — navigate, screenshot, fill forms, click elements, scrape content (DOM or network), capture API tokens, run authenticated flows, or execute test scenarios. Handles async multi-browser (Chromium/Firefox/WebKit), network interception, HAR capture, and result storage via Redis queue + PostgreSQL backend.
---

# Playwrights

Full-stack browser automation skill powered by Python Playwright, FastAPI control layer, Redis task queue, and PostgreSQL storage.

## When to Use

Trigger on prompts like:
- "Open [URL] and extract [data]"
- "Take a screenshot of [page]"
- "Fill out [form] with [dataset] and validate [response]"
- "Capture all network requests on [URL] and extract [tokens]"
- "Run the checkout flow authenticated as [user]"
- "Map the user journey on [site]"
- "Intercept and log API calls from [URL]"
- "Execute test [scenario] and report results with HAR"

## Core Architecture

```
User Prompt → Intent Parser → Task JSON → Redis Queue → Playwright Worker
                                                                    ↓
                                            DOM / Network Capture → PostgreSQL
                                                                    ↓
                                              Artifacts + HAR + Logs
```

## Workflow Decision Tree

```
User Prompt Received
│
├─ "navigate" or "open" or "visit" → NAVIGATE
│
├─ "screenshot" → NAVIGATE → SCREENSHOT
│
├─ "fill" or "form" or "submit" → NAVIGATE → INTERACT (DOM)
│
├─ "extract" or "scrape" or "get data" → NAVIGATE → SCRAPE
│
├─ "network" or "requests" or "intercept" or "capture tokens" → NAVIGATE → INTERCEPT
│
├─ "authenticated" or "login" or "session" → AUTHENTICATED FLOW
│
├─ "test" or "scenario" or "journey" or "flow" → NAVIGATE → SEQUENCE → ASSERT
│
└─ "HAR" or "export" or "log network" → NAVIGATE → INTERCEPT → HAR CAPTURE
```

## Step 1 — Intent Parsing

Parse user prompt into structured task JSON:

```json
{
  "task_id": "<uuid>",
  "steps": [
    { "action": "navigate", "target": "<url>", "wait_until": "networkidle" },
    { "action": "click", "selector": "<css/xpath>", "timeout": 5000 },
    { "action": "fill", "selector": "<input[name=email]>", "value": "<data>" },
    { "action": "submit", "selector": "<form>", "wait_for_navigation": true },
    { "action": "extract", "selector": "<.results>", "type": "html|text|table" },
    { "action": "intercept", "match_url": "<regex>", "store": true }
  ],
  "browser": "chromium|firefox|webkit",
  "context": {
    "viewport": { "width": 1280, "height": 720 },
    "user_agent": "<ua-string>",
    "proxy": "<proxy-url>",
    "storage_state": "<auth-state-path>"
  },
  "assertions": [
    { "type": "url", "contains": "<expected-url-fragment>" },
    { "type": "selector", "present": "<.success-message>" },
    { "type": "response", "status": 200 },
    { "type": "network", "contains_token": "<token-name>" }
  ],
  "capture": {
    "screenshot": true,
    "html": true,
    "har": true,
    "console_logs": true
  }
}
```

Use `scripts/parse_intent.py` to convert natural prompts to task JSON.

## Step 2 — Queue & Execute

Submit task JSON to Redis queue:

```bash
python scripts/queue_task.py --task <task-json-file>
python scripts/run_worker.py --task-id <uuid>
```

Worker picks up task, executes Playwright steps in order, captures artifacts, stores results in PostgreSQL.

## Step 3 — Actions Reference

### Navigate
```python
async with async_playwright() as p:
    browser = await p.chromium.launch(headless=True)
    context = await browser.new_context(
        viewport={"width": 1280, "height": 720},
        user_agent="...",
        proxy={"server": "http://proxy:port"}
    )
    page = await context.new_page()
    await page.goto(url, wait_until="networkidle", timeout=30000)
```

### Screenshot
```python
await page.goto(url)
await page.screenshot(path="screenshots/result.png", full_page=True)
```

### DOM Interaction
```python
# Click
await page.click("#submit-btn", timeout=5000)

# Fill form
await page.fill("input[name=email]", "user@example.com")
await page.fill("input[name=password]", "secret")

# Select
await page.select_option("select[name=country]", "US")

# Submit
await page.click("button[type=submit]")
await page.wait_for_navigation()
```

### Scraping
```python
# Text
text = await page.text_content(".article-title")

# HTML
html = await page.inner_html(".results")

# Table
rows = await page.query_selector_all("table.data tr")
data = [[await td.text_content() for td in await row.query_selector_all("td")] for row in rows]

# Multiple elements
items = await page.query_selector_all(".product-card")
for item in items:
    title = await item.text_content(".title")
    price = await item.get_attribute("data-price")
```

### Network Interception
```python
api_calls = []

async def capture_request(route, request):
    api_calls.append({
        "url": request.url,
        "method": request.method,
        "headers": dict(request.headers),
        "post_data": request.post_data,
        "timestamp": datetime.utcnow().isoformat()
    })
    await route.continue_()

async def capture_response(response):
    for call in api_calls:
        if call["url"] == response.request.url:
            call["response_status"] = response.status
            call["response_body"] = await response.text()

page.on("request", capture_request)
page.on("response", capture_response)

# For specific API interception
await page.route("**/api/**", capture_request)
```

### HAR Capture
```python
context = await browser.new_context(record_har_path="har/capture.har")
# ... navigate ...
await context.close()
```

### Authenticated Flow
```python
# Save auth state after login
context = await browser.new_context()
page = await context.new_page()
await page.goto("https://example.com/login")
await page.fill("input[name=email]", "user@test.com")
await page.fill("input[name=password]", "pass123")
await page.click("button[type=submit]")
await page.wait_for_navigation()
await context.storage_state(path="auth_state.json")

# Reuse for subsequent requests
context = await browser.new_context(storage_state="auth_state.json")
page = await context.new_page()
await page.goto("https://example.com/dashboard")
```

### Assertions
```python
# URL assertion
assert "success" in page.url

# Selector presence
await page.wait_for_selector(".success-message", timeout=5000)

# Response status
response = await page.request.get("https://api.example.com/data")
assert response.status == 200

# Token extraction from network
for call in api_calls:
    if "token" in call.get("url", "") or "token" in str(call.get("post_data", "")):
        print(f"Found token: {call}")
```

## Step 4 — Artifact Storage

Results are stored in PostgreSQL:

```sql
CREATE TABLE task_runs (
    task_id UUID PRIMARY KEY,
    created_at TIMESTAMP DEFAULT NOW(),
    status TEXT,
    browser TEXT,
    steps_completed JSONB,
    screenshot_url TEXT,
    har_path TEXT,
    console_logs JSONB,
    network_calls JSONB,
    assertions_passed JSONB,
    error TEXT
);
```

## Step 5 — Output Artifacts

Worker returns:
- `screenshot.png` — page screenshot
- `dom.html` — full page HTML
- `capture.har` — network traffic log
- `console.log` — browser console output
- `network.json` — intercepted API calls with tokens
- `task_result.json` — full task result with pass/fail assertions

## Selector Strategy

See `references/selectors.md` for deterministic fallback patterns and anti-detection guidance.

## Network Tracing

See `references/network_tracing.md` for deep network inspection, token extraction, and HAR processing.

## Run Modes

See `references/run_modes.md` for local execution, CI integration, and versioned reproducible runs.

---

**Resources:**

| Directory | Contents |
|-----------|----------|
| `scripts/` | Intent parser, task queue, worker runner, action modules |
| `references/` | Detailed guides: selectors, network tracing, run modes, PostgreSQL schema |
| `assets/` | Starter playwright config, selector maps, assertion templates |
