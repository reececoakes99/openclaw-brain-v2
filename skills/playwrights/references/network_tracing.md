# Network Tracing & Token Extraction

## Setup: Intercept All Requests

```python
from playwright.async_api import Page
import json, re
from datetime import datetime

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
                "post_data_json": self._parse_post_data(request),
                "resource_type": request.resource_type,
                "timestamp": datetime.utcnow().isoformat()
            })

        async def on_response(response):
            try:
                body = await response.text()
            except:
                body = None
            entry = {
                "url": response.request.url,
                "status": response.status,
                "headers": dict(response.headers),
                "body": body,
                "body_size": len(body or ""),
                "timestamp": datetime.utcnow().isoformat()
            }
            self.responses.append(entry)

        page.on("request", on_request)
        page.on("response", on_response)

        if match_pattern != "**":
            await page.route(match_pattern, on_request)

    def _parse_post_data(self, request):
        try:
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type and request.post_data:
                return json.loads(request.post_data)
        except:
            pass
        return None

    def extract_tokens(self):
        patterns = [
            (r'(Bearer\s+)[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+', 'Bearer JWT'),
            (r'(token["\']?\s*[:=]\s*["\']?)([A-Za-z0-9\-_]{20,})', 'Token Field'),
            (r'(access_token["\']?\s*[:=]\s*["\']?)([A-Za-z0-9\-_]{20,})', 'Access Token'),
            (r'(refresh_token["\']?\s*[:=]\s*["\']?)([A-Za-z0-9\-_]{20,})', 'Refresh Token'),
            (r'(auth["\']?\s*[:=]\s*["\']?)([A-Za-z0-9\-_]{20,})', 'Auth Token'),
            (r'(session_id["\']?\s*[:=]\s*["\']?)([A-Za-z0-9]{16,})', 'Session ID'),
        ]
        for req in self.requests:
            url = req["url"]
            pd = str(req.get("post_data") or "")
            for pattern, label in patterns:
                for match in re.finditer(pattern, url + pd, re.IGNORECASE):
                    self.tokens.append({
                        "type": label,
                        "value": match.group(0),
                        "url": url,
                        "method": req["method"],
                        "source": "url" if match.group(0) in url else "body"
                    })
        return self.tokens

    def get_api_calls(self, domain: str = None):
        return [r for r in self.requests if domain is None or domain in r["url"]]

    def to_dict(self):
        return {
            "requests": self.requests,
            "responses": self.responses,
            "tokens": self.tokens,
            "request_count": len(self.requests),
            "response_count": len(self.responses)
        }
```

## Usage

```python
tracer = NetworkTracer()
await tracer.start(page)

await page.goto("https://target-app.com")
# ... do stuff ...

tokens = tracer.extract_tokens()
api_calls = tracer.get_api_calls(domain="api.target-app.com")
result = tracer.to_dict()

print(f"API calls: {len(api_calls)}")
print(f"Tokens found: {len(tokens)}")
for t in tokens:
    print(f"  {t['type']} from {t['method']} {t['url']}")
```

## HAR Export

```python
# Record HAR on context level
context = await browser.new_context(record_har_path="output.har")

# Or filter what gets recorded
context = await browser.new_context(
    record_har_path="output.har",
    record_har_url_filter="**/*",
    record_har_omit_favicon=True
)

# Navigate and capture
page = await context.new_page()
await page.goto("https://target-app.com")
# ... actions ...

# Close context to flush HAR
await context.close()
```

## Process HAR Files

```python
import json, har_reader

def analyze_har(har_path: str):
    har = har_reader.read_har(har_path)

    # Summarize
    summary = {
        "total_requests": len(har["entries"]),
        "domains": set(e["request"]["url"].split("/")[2] for e in har["entries"]),
        "by_type": {},
        "slow_requests": [],
        "failed_requests": []
    }

    for entry in har["entries"]:
        t = entry["request"]["url"]
        rt = entry["request"]["resourceType"]
        summary["by_type"][rt] = summary["by_type"].get(rt, 0) + 1
        if entry["time"] > 2000:
            summary["slow_requests"].append({"url": t, "time": entry["time"]})
        if entry["response"]["status"] >= 400:
            summary["failed_requests"].append({"url": t, "status": entry["response"]["status"]})

    return summary
```

## Common Token Patterns

| Token Type | Regex Pattern | Where |
|------------|--------------|-------|
| Bearer JWT | `Bearer [A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+` | Auth header |
| Access Token | `access_token["\']?\s*[:=]` | URL / body |
| Refresh Token | `refresh_token["\']?\s*[:=]` | Body |
| CSRF Token | `(csrf|xsrf)["\']?\s*[:=]` | Cookie / body |
| Session ID | `session_id["\']?\s*[:=]` | Cookie |
| API Key | `api[_-]?key["\']?\s*[:=]` | Header / URL |
