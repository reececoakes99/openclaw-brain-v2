from playwright.async_api import async_playwright, Browser, BrowserContext, Page
import asyncio, json, re
from datetime import datetime
from uuid import uuid4

# ─── Config ───────────────────────────────────────────────────────────────────
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
STEALTH_SCRIPT = """
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
navigator.permissions.query = ({ name: 'notifications' }) =>
    Promise.resolve({ state: Notification.permission });
Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
"""


# ─── Browser Factory ──────────────────────────────────────────────────────────
async def launch_browser(
    pw,
    browser: str = "chromium",
    headless: bool = True,
    proxy: dict = None,
    args: list = None,
) -> Browser:
    defaults = [
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",
    ]
    launch_kwargs = {
        "headless": headless,
        "args": args or [],
    }
    for arg in defaults:
        if arg not in launch_kwargs["args"]:
            launch_kwargs["args"].append(arg)
    if proxy:
        launch_kwargs["proxy"] = proxy
    browser_cls = getattr(pw, browser)
    return await browser_cls.launch(**launch_kwargs)


async def new_context(
    browser: Browser,
    viewport: dict = None,
    user_agent: str = None,
    storage_state: str = None,
    proxy: dict = None,
    locale: str = "en-US",
    timezone: str = "America/New_York",
    extra_headers: dict = None,
    record_har: str = None,
) -> BrowserContext:
    ctx_opts = {
        "viewport": viewport or DEFAULT_VIEWPORT,
        "user_agent": user_agent or DEFAULT_UA,
        "locale": locale,
        "timezone_id": timezone,
        "permissions": ["geolocation"],
        "extra_http_headers": extra_headers or {
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    }
    if storage_state:
        ctx_opts["storage_state"] = storage_state
    if proxy:
        ctx_opts["proxy"] = proxy
    if record_har:
        ctx_opts["record_har_path"] = record_har
    return await browser.new_context(**ctx_opts)


async def stealth_page(page: Page) -> Page:
    await page.add_init_script(STEALTH_SCRIPT)
    return page


# ─── Selectors ────────────────────────────────────────────────────────────────
SELECTOR_PRIORITY = [
    lambda s: f'[data-testid="{s}"]',
    lambda s: f'#{s}',
    lambda s: f'.{s}',
    lambda s: s,
]


async def click_fallback(page: Page, selectors: list[str], timeout: int = 5000) -> str:
    for sel in selectors:
        try:
            await page.click(sel, timeout=timeout)
            return sel
        except Exception:
            continue
    raise Exception(f"None matched: {selectors}")


# ─── Network Tracer ─────────────────────────────────────────────────────────────
class NetworkTracer:
    def __init__(self):
        self.requests = []
        self.responses = []
        self.tokens = []

    async def start(self, page: Page, match_pattern: str = "**"):
        self.match_pattern = match_pattern

        async def on_request(request):
            self.requests.append({
                "url": request.url,
                "method": request.method,
                "headers": dict(request.headers),
                "post_data": request.post_data,
                "resource_type": request.resource_type,
                "timestamp": datetime.utcnow().isoformat(),
            })

        async def on_response(response):
            try:
                body = await response.text()
            except:
                body = None
            self.responses.append({
                "url": response.request.url,
                "status": response.status,
                "headers": dict(response.headers),
                "body": body,
                "timestamp": datetime.utcnow().isoformat(),
            })

        page.on("request", on_request)
        page.on("response", on_response)
        if match_pattern != "**":
            await page.route(match_pattern, on_request)

    def extract_tokens(self) -> list[dict]:
        patterns = [
            (r"Bearer\s+[\w\-]+\.[\w\-]+\.[\w\-]+", "Bearer JWT"),
            (r'(?:access_token|refresh_token|auth_token)["\']?\s*[:=]\s*["\']?([\w\-]{20,})', "Token Field"),
            (r"session_id["\']?\s*[:=]\s*[\"']?([\w\-]{10,})", "Session ID"),
            (r"api[_\-]?key["\']?\s*[:=]\s*[\"']?([\w\-]{16,})", "API Key"),
        ]
        for req in self.requests:
            content = req["url"] + str(req.get("post_data") or "")
            for pat, label in patterns:
                for match in re.finditer(pat, content, re.IGNORECASE):
                    self.tokens.append({
                        "type": label,
                        "value": match.group(0),
                        "url": req["url"],
                        "method": req["method"],
                    })
        return self.tokens

    def to_dict(self) -> dict:
        return {
            "requests": self.requests,
            "responses": self.responses,
            "tokens": self.tokens,
            "request_count": len(self.requests),
        }


# ─── Task Runner ───────────────────────────────────────────────────────────────
ACTION_MAP = {
    "navigate":  lambda p, s: p.goto(s["target"], wait_until=s.get("wait_until","load"), timeout=s.get("timeout",30000)),
    "click":     lambda p, s: p.click(s["selector"], timeout=s.get("timeout",5000)),
    "fill":      lambda p, s: p.fill(s["selector"], s["value"]),
    "select":    lambda p, s: p.select_option(s["selector"], s["value"]),
    "submit":    lambda p, s: p.click(s.get("selector","button[type=submit]")),
    "wait":      lambda _, s: asyncio.sleep(s.get("duration_ms", 1000) / 1000),
    "hover":     lambda p, s: p.hover(s["selector"]),
    "screenshot": lambda p, s: p.screenshot(path=s.get("path","screenshot.png"), full_page=s.get("full_page",True)),
    "extract":   lambda p, s: (
        p.inner_html(s["selector"]) if s.get("type")=="html"
        else p.text_content(s["selector"])
    ),
}


async def run_steps(page: Page, steps: list[dict], verbose: bool = False) -> list[dict]:
    results = []
    for i, step in enumerate(steps):
        action = step.get("action")
        if verbose:
            print(f"[{i+1}] {action}: {step}")
        try:
            if action == "intercept":
                results.append({"action": action, "ok": True})
                continue
            if action not in ACTION_MAP:
                results.append({"action": action, "ok": False, "error": f"Unknown action: {action}"})
                continue
            await ACTION_MAP[action](page, step)
            results.append({"action": action, "ok": True})
        except Exception as e:
            results.append({"action": action, "ok": False, "error": str(e)})
    return results


async def run_task(
    task_json: dict,
    browser: str = "chromium",
    headless: bool = True,
    verbose: bool = False,
) -> dict:
    async with async_playwright() as pw:
        br = await launch_browser(pw, browser=browser, headless=headless)
        ctx = await new_context(br, **task_json.get("context", {}))
        page = await ctx.new_page()
        await stealth_page(page)

        # Start network tracer if intercept is in steps
        tracer = None
        if any(s.get("action") == "intercept" for s in task_json.get("steps", [])):
            tracer = NetworkTracer()
            await tracer.start(page)

        steps = await run_steps(page, task_json.get("steps", []), verbose=verbose)

        if tracer:
            tracer.extract_tokens()

        capture = task_json.get("capture", {})
        artifacts = {}
        task_id = task_json.get("task_id", str(uuid4()))

        if capture.get("screenshot"):
            path = f"artifacts/{task_id}_screenshot.png"
            await page.screenshot(path=path, full_page=True)
            artifacts["screenshot"] = path

        if capture.get("html"):
            path = f"artifacts/{task_id}_dom.html"
            open(path, "w").write(await page.content())
            artifacts["html"] = path

        if capture.get("har") and tracer:
            artifacts["network"] = tracer.to_dict()

        await ctx.close()
        await br.close()

        return {
            "task_id": task_id,
            "status": "done",
            "steps_completed": steps,
            "artifacts": artifacts,
            "tracer": tracer.to_dict() if tracer else None,
        }
