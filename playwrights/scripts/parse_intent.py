#!/usr/bin/env python3
"""Parse natural language prompts into structured task JSON."""

import json, sys, re, argparse
from uuid import uuid4

ACTION_KEYWORDS = {
    "navigate": ["navigate", "open", "visit", "go to", "load", "browse"],
    "click": ["click", "press", "tap", "select button", "hit"],
    "fill": ["fill", "type", "enter", "input", "write"],
    "select": ["select", "pick", "choose"],
    "submit": ["submit", "send", "post"],
    "screenshot": ["screenshot", "capture", "snapshot", "screen grab"],
    "extract": ["extract", "scrape", "get data", "pull", "read", "fetch"],
    "intercept": ["intercept", "capture requests", "log network", "monitor", "track"],
    "wait": ["wait", "pause", "delay", "sleep"],
    "hover": ["hover", "mouse over"],
    "scroll": ["scroll", "scroll down", "scroll up"],
}

BROWSER_KEYWORDS = {
    "chromium": ["chrome", "chromium", "google"],
    "firefox": ["firefox", "ff", "mozilla"],
    "webkit": ["safari", "webkit", "apple"],
}

def detect_action(phrase: str) -> str:
    phrase = phrase.lower()
    for action, keywords in ACTION_KEYWORDS.items():
        for kw in keywords:
            if kw in phrase:
                return action
    return "navigate"

def detect_browser(phrase: str) -> str:
    phrase = phrase.lower()
    for browser, keywords in BROWSER_KEYWORDS.items():
        for kw in keywords:
            if kw in phrase:
                return browser
    return "chromium"

def extract_url(phrase: str) -> str | None:
    patterns = [
        r'https?://[^\s<>"\']+',
        r'www\.[^\s<>"\']+',
    ]
    for p in patterns:
        m = re.search(p, phrase, re.IGNORECASE)
        if m:
            return m.group(0)
    return None

def extract_selectors(phrase: str) -> list[str]:
    selectors = []
    css_pattern = r'[\[#\.\]?[\w\-]+\s]*[\[#\.\]?[\w\-\s=\'"]+'
    for m in re.finditer(css_pattern, phrase):
        s = m.group(0).strip()
        if s and any(c in s for c in "#.[") and len(s) < 100:
            selectors.append(s)
    return selectors

def extract_wait_for(phrase: str) -> str:
    if "networkidle" in phrase.lower():
        return "networkidle"
    if "domcontentloaded" in phrase.lower():
        return "domcontentloaded"
    if "load" in phrase.lower():
        return "load"
    return "networkidle"

def parse_prompt(prompt: str, browser: str = "chromium") -> dict:
    steps = []
    sentences = re.split(r'(?<=[.,;])\s+', prompt)

    for sent in sentences:
        if not sent.strip():
            continue
        action = detect_action(sent)
        step = {"action": action}

        if action in ("navigate", "screenshot"):
            url = extract_url(sent)
            if url:
                step["target"] = url
                step["wait_until"] = extract_wait_for(sent)
        elif action == "fill":
            selectors = extract_selectors(sent)
            if selectors:
                step["selector"] = selectors[0]
            value_m = re.search(r'["\']([^"\']+)["\']', sent)
            if value_m:
                step["value"] = value_m.group(1)
        elif action in ("click", "submit", "hover"):
            selectors = extract_selectors(sent)
            if selectors:
                step["selector"] = selectors[0]
            elif "button" in sent.lower():
                step["selector"] = "button"
        elif action == "intercept":
            match_url_m = re.search(r'["\']([^"\']+)["\']', sent)
            step["match_url"] = match_url_m.group(1) if match_url_m else "**/api/**"
            step["store"] = True
        elif action == "extract":
            selectors = extract_selectors(sent)
            if selectors:
                step["selector"] = selectors[0]
            step["type"] = "text"
            if "html" in sent.lower():
                step["type"] = "html"
            elif "table" in sent.lower():
                step["type"] = "table"
        elif action == "wait":
            ms_m = re.search(r'(\d+)\s*(ms|milliseconds?|s|seconds?)', sent)
            if ms_m:
                val = int(ms_m.group(1))
                if ms_m.group(2)[0] == "s":
                    val *= 1000
                step["duration_ms"] = val
            else:
                step["duration_ms"] = 1000

        if step.get("target") or step.get("selector") or step.get("type"):
            steps.append(step)

    return {
        "task_id": str(uuid4()),
        "steps": steps,
        "browser": detect_browser(prompt),
        "context": {"viewport": {"width": 1280, "height": 720}},
        "capture": {
            "screenshot": "screenshot" in prompt.lower() or "capture" in prompt.lower(),
            "html": True,
            "har": "network" in prompt.lower() or "intercept" in prompt.lower(),
            "console_logs": True,
        }
    }

def main():
    parser = argparse.ArgumentParser(description="Parse prompt to task JSON")
    parser.add_argument("prompt", nargs="*", help="Prompt string")
    parser.add_argument("-f", "--file", help="Read prompt from file")
    parser.add_argument("-o", "--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            prompt = f.read()
    elif args.prompt:
        prompt = " ".join(args.prompt)
    else:
        prompt = sys.stdin.read()

    task = parse_prompt(prompt)
    out = json.dumps(task, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(out)
        print(f"Task written to {args.output} (ID: {task['task_id']})")
    else:
        print(out)

if __name__ == "__main__":
    main()
