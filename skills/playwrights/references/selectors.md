# Selectors & Anti-Detection

## Selector Priority (most to least reliable)

1. **Data-testid** — Most stable, not CSS-dependent
2. **ID** — `#element-id`, unique by definition
3. **CSS class** — `.class-name`, prefer semantic names
4. **Text content** — `text="Submit"`, `has-text`
5. **XPath** — Last resort, fragile on DOM changes

## Deterministic Fallback Chain

```python
SELECTOR_FALLBACKS = [
    '[data-testid="submit-btn"]',
    '#submit-button',
    '.btn-primary',
    'button[type="submit"]',
    'button:has-text("Submit")',
    'xpath=//button[contains(@class,"submit")]'
]

async def click_with_fallback(page, fallbacks, timeout=5000):
    for selector in fallbacks:
        try:
            await page.click(selector, timeout=timeout)
            return selector
        except:
            continue
    raise Exception(f"None of the selectors matched: {fallbacks}")
```

## Selector Maps (YAML)

Store reusable selectors in `assets/selector_maps/`:

```yaml
# google_search.yaml
search_box:
  primary: '[name="q"]'
  fallback: '[data-testid="search-input"]'
  xpath: '//input[@placeholder*="search"i]'

submit_btn:
  primary: '[data-testid="search-submit"]'
  fallback: 'button[type="submit"]'
  xpath: '//button[contains(translate(text(),"SEARCH","search"),"search")]'

results:
  primary: '#search'
  fallback: '.g'
  xpath: '//div[contains(@class,"result")]'
```

## Anti-Detection Settings

```python
# Avoid headless:false — it signals automation
browser = await p.chromium.launch(
    headless=True,
    args=[
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--disable-gpu",
    ]
)

context = await browser.new_context(
    viewport={"width": 1920, "height": 1080},  # Common desktop size
    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    locale="en-US",
    timezone_id="America/New_York",
    permissions=["geolocation"],
    extra_http_headers={
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    }
)

# Stealth: hide webdriver flag
await page.add_init_script("""
    Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
    navigator.permissions.query = ({ name: 'notifications' }) =>
        Promise.resolve({ state: Notification.permission });
    Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
    Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
""")
```

## Human-like Delays

```python
import random
import asyncio

async def human_delay(min_ms=100, max_ms=500):
    await asyncio.sleep(random.uniform(min_ms / 1000, max_ms / 1000))

async def human_typing(page, selector, text):
    await page.click(selector)
    await page.fill(selector, "")
    for char in text:
        await page.type(selector, char, delay=random.uniform(0.05, 0.2))
        await asyncio.sleep(random.uniform(0.01, 0.05))

# Usage: random delays between steps
await human_delay(300, 800)
await human_typing(page, "input[name=email]", "user@example.com")
```
