# Performance Tuning — Playwrights

## Browser Launch Optimization

### Reuse Strategy
```python
# Reuse browser instances across requests (not per-request launch)
pool = BrowserPool(browser_type='chromium', pool_size=8)

@app.post("/tasks")
async def create_task(req: TaskRequest):
    browser = await pool.acquire(timeout=30)
    result = await browser.execute(req.intent)
    await pool.release(browser)  # return to pool, don't close
    return {"task_id": task_id, "result": result}
```

### Lazy Initialization
```python
# Don't launch browsers on startup — start workers on demand
class LazyBrowserPool:
    def __init__(self, max_size=4):
        self.browsers = []
        self.max_size = max_size
        self._semaphore = asyncio.Semaphore(max_size)

    async def acquire(self):
        await self._semaphore.acquire()
        if self.browsers:
            return self.browsers.pop()
        return await self._launch()

    async def release(self, browser):
        self.browsers.append(browser)
        self._semaphore.release()
```

### Pool Sizing
| Worker Count | Pool Size | Concurrent Browsers | Memory |
|---|---|---|---|
| 2 workers | 4 per worker | 8 | ~8 GB |
| 4 workers | 4 per worker | 16 | ~16 GB |
| 8 workers | 4 per worker | 32 | ~32 GB |

## HTTP Optimization

### Keep-Alive
```python
# Reuse HTTP client connections
import httpx

client = httpx.AsyncClient(
    limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
    timeout=httpx.Timeout(30.0, connect=5.0),
    keepalive_expiry=60.0,
)
```

### Connection Pooling
```python
# Thread pool for synchronous operations
from concurrent.futures import ThreadPoolExecutor
executor = ThreadPoolExecutor(max_workers=10)
```

## Database Optimization

### Indexes
```sql
CREATE INDEX idx_tasks_status_created ON tasks(status, created_at DESC);
CREATE INDEX idx_tasks_worker_status ON tasks(worker_id, status);
CREATE INDEX idx_results_task_id ON results(task_id);
-- Partial index for active tasks only
CREATE INDEX idx_tasks_active ON tasks(created_at DESC)
  WHERE status IN ('queued', 'running');
```

### Connection Pool
```python
# asyncpg connection pool
pool = await asyncpg.create_pool(
    host='postgres',
    port=5432,
    database='playwrights',
    user='playwrights',
    password=os.environ['DB_PASSWORD'],
    min_size=5,
    max_size=20,
)
```

### Query Optimization
```python
# BAD: N+1 queries
results = await fetch_results(task_ids)
for result in results:
    task = await fetch_task(result.task_id)  # N queries

# GOOD: Batch fetch
task_ids = [r.task_id for r in results]
tasks = await pool.fetch(
    'SELECT * FROM tasks WHERE id = ANY($1)',
    task_ids
)
```

## Redis Optimization

### Pipelines
```python
# Batch get (1 round trip instead of N)
pipe = r.pipeline()
for tid in task_ids:
    pipe.get(f'task:{tid}:status')
    pipe.get(f'task:{tid}:result')
results = pipe.execute()
```

### Lua Scripting
```lua
-- Atomic multi-key get + delete
local keys = {'task:'..KEYS[1]..':status', 'task:'..KEYS[1]..':result', 'task:'..KEYS[1]..':data'}
local vals = {}
for i, k in ipairs(keys) do
    vals[i] = redis.call('GET', k)
    redis.call('DEL', k)
end
return vals
```

### Persistence
```
# redis.conf
appendonly yes
appendfsync everysec    # <-- fast writes, acceptable durability
maxmemory 512mb
maxmemory-policy allkeys-lru
```

## FastAPI Optimization

### Async Handlers
```python
# All I/O operations must be async
@app.post("/tasks")
async def create_task(req: TaskRequest):  # async def, not def
    task_id = await db.insert(req)       # await DB
    await redis.lpush(f"queue:{worker_id}", task_id)  # await Redis
    return {"task_id": task_id}

# Sync I/O in executor
def blocking_op():
    result = sync_browser_driver.execute(req.intent)
    return result

loop = asyncio.get_event_loop()
result = await loop.run_in_executor(executor, blocking_op)
```

### Gunicorn Workers
```bash
# 4 workers per CPU core (CPU-bound), async worker class
gunicorn app:app \
  --workers $((4 * $(nproc))) \
  --worker-class uvicorn.workers.UvicornWorker \
  --bind 0.0.0.0:8080 \
  --timeout 60 \
  --keep-alive 5 \
  --max-requests 10000 \
  --max-requests-jitter 1000
```

### Response Compression
```python
# middleware in app
from starlette.middleware.compression import CompressionMiddleware
app.add_middleware(CompressionMiddleware, minimum_size=1000)
```

## Caching

### In-Memory Cache (LRU)
```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def get_selector_map(selector_version: str) -> dict:
    # Cached for repeated lookups
    return load_selector_map_from_db(selector_version)
```

### Redis Cache
```python
async def get_cached_intent(intent: str, ttl=3600):
    key = f"cached_intent:{hash(intent)}"
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    # Compute + cache
    result = compute_result(intent)
    await redis.setex(key, ttl, json.dumps(result))
    return result
```