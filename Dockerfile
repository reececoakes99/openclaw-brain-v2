FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    OPENCLAW_ROOT=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
        tini \
    && rm -rf /var/lib/apt/lists/*

COPY pipeline/requirements.txt /tmp/openclaw-pipeline-requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && if [ -s /tmp/openclaw-pipeline-requirements.txt ]; then \
        python -m pip install --no-cache-dir -r /tmp/openclaw-pipeline-requirements.txt; \
       fi

COPY . /app

RUN mkdir -p \
      /app/.openclaw/logs \
      /app/reports/sqlite \
      /app/knowledge/bot_activity_logs/recon \
      /app/knowledge/bot_activity_logs/intel \
      /app/knowledge/bot_activity_logs/hunter \
      /app/knowledge/bot_activity_logs/operations \
      /app/knowledge/bot_queue

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["python", "knowledge_updater/schedulers/heartbeat_loop.py"]
