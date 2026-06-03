#!/usr/bin/env python3
"""Execute a task JSON through the Playwright worker pipeline."""

import asyncio, json, argparse, sys
from playwright.async_api import async_playwright
from pathlib import Path

OUTPUT_DIR = Path("artifacts")
OUTPUT_DIR.mkdir(exist_ok=True)

ACTION_HANDLERS = {}

def register_action(name):
    def deco(fn):
        ACTION_HANDLERS[name] = fn
        return fn
    return deco

@register_action("navigate")
async def do_navigate(page, step):
    url = step["target"]
    wait_until = step.get("wait_until", "networkidle")
    timeout = step.get("timeout", 30000)
    await page.goto(url, wait_until=wait_until, timeout=timeout)
    return {"action": "navigate", "url": url, "ok": True}

@register_action("click")
async def do_click(page, step):
    selector = step["selector"]
    timeout = step.get("timeout", 5000)
    await page.click(selector, timeout=timeout)
    return {"action": "click", "selector": selector, "ok": True}

@register_action("fill")
async def do_fill(page, step):
    selector = step["selector"]
    value = step["value"]
    await page.fill(selector, value)
    return {"action": "fill", "selector": selector, "ok": True}

@register_action("select")
async def do_select(page, step):
    selector = step["selector"]
    value = step["value"]
    await page.select_option(selector, value)
    return {"action": "select", "selector": selector, "ok": True}

@register_action("submit")
async def do_submit(page, step):
    selector = step.get("selector", "button[type=submit]")
    await page.click(selector)
    if step.get("wait_for_navigation"):
        await page.wait_for_navigation()
    return {"action": "submit", "selector": selector, "ok": True}

@register_action("screenshot")
async def do_screenshot(page, step):
    filename = step.get("path", f"screenshots/{step.get('target', 'page').replace('/', '_')}.png")
    full_page = step.get("full_page", True)
    Path(filename).parent.mkdir(parents=True, exist_ok=True)
    await page.screenshot(path=filename, full_page=full_page)
    return {"action": "screenshot", "path": filename, "ok": True}

@register_action("extract")
async def do_extract(page, step):
    selector = step.get("selector", "body")
    extract_type = step.get("type", "text")
    if extract_type == "html":
        data = await page.inner_html(selector)
    elif extract_type == "table":
        rows = await page.query_selector_all(f"{selector} tr")
        data = [
            [await td.text_content() for td in await row.query_selector_all("td,th")]
            for row in rows
        ]
    else:
        data = await page.text_content(selector)
    return {"action": "extract", "selector": selector, "type": extract_type, "data": data, "ok": True}

@register_action("wait")
async def do_wait(page, step):
    duration_ms = step.get("duration_ms", 1000)
    await asyncio.sleep(duration_ms / 1000)
    return {"action": "wait", "duration_ms": duration_ms, "ok": True}

@register_action("hover")
async def do_hover(page, step):
    selector = step["selector"]
    await page.hover(selector)
    return {"action": "hover", "selector": selector, "ok": True}

@register_action("scroll")
async def do_scroll(page, step):
    if step.get("direction") == "up":
        await page.evaluate("window.scrollBy(0, -window.innerHeight)")
    else:
        await page.evaluate("window.scrollBy(0, window.innerHeight)")
    return {"action": "scroll", "ok": True}

@register_action("intercept")
async def do_intercept(page, step):
    # Interception is set up globally; this step is a no-op marker
    return {"action": "intercept", "ok": True}

async def run_task(task_json: dict, browser_name: str = "chromium", headless: bool = True, verbose: bool = False):
    async with async_playwright() as p:
        browser_cls = getattr(p, browser_name)
        browser = await browser_cls.launch(headless=headless)

        ctx_opts = task_json.get("context", {})
        context = await browser.new_context(**ctx_opts)
        page = await context.new_page()

        results = []
        for i, step in enumerate(task_json.get("steps", [])):
            action = step["action"]
            if verbose:
                print(f"[{i+1}/{len(task_json['steps'])}] {action}: {step}")

            if action not in ACTION_HANDLERS:
                print(f"WARNING: Unknown action '{action}', skipping")
                continue

            try:
                result = await ACTION_HANDLERS[action](page, step)
                results.append(result)
            except Exception as e:
                results.append({"action": action, "ok": False, "error": str(e)})
                if verbose:
                    print(f"ERROR in step {i+1}: {e}")

        # Capture artifacts
        capture = task_json.get("capture", {})
        artifacts = {}

        if capture.get("screenshot"):
            ss_path = f"artifacts/{task_json['task_id']}_screenshot.png"
            await page.screenshot(path=ss_path, full_page=True)
            artifacts["screenshot"] = ss_path

        if capture.get("html"):
            html_path = f"artifacts/{task_json['task_id']}_dom.html"
            Path(html_path).write_text(await page.content())
            artifacts["html"] = html_path

        if capture.get("console_logs"):
            artifacts["console_logs"] = []

        await browser.close()

        return {
            "task_id": task_json["task_id"],
            "status": "done",
            "steps_completed": results,
            "artifacts": artifacts,
        }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", help="Task UUID")
    parser.add_argument("--task", help="Task JSON string or @filepath")
    parser.add_argument("--browser", default="chromium", choices=["chromium", "firefox", "webkit"])
    parser.add_argument("--headless", type=bool, default=True)
    parser.add_argument("-o", "--output", help="Output file for result JSON")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    if args.task:
        task_str = args.task
        if task_str.startswith("@"):
            with open(task_str[1:]) as f:
                task_str = f.read()
        task_json = json.loads(task_str)
    elif args.task_id:
        # Load from queue result (placeholder)
        print(f"Loading task {args.task_id} from storage...")
        sys.exit(1)
    else:
        task_json = json.load(sys.stdin)

    result = asyncio.run(run_task(
        task_json,
        browser_name=args.browser,
        headless=args.headless,
        verbose=args.verbose,
    ))

    out = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(out)
        print(f"Result saved to {args.output}")
    else:
        print(out)

if __name__ == "__main__":
    main()
