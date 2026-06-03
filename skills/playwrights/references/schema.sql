-- Playwrights PostgreSQL Schema

-- Task runs: one row per execution
CREATE TABLE task_runs (
    task_id          UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_id      UUID        REFERENCES task_snapshots(snapshot_id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    started_at       TIMESTAMPTZ,
    finished_at      TIMESTAMPTZ,
    status           TEXT        CHECK (status IN ('queued', 'running', 'done', 'error', 'cancelled')),
    browser          TEXT        CHECK (browser IN ('chromium', 'firefox', 'webkit')),
    headless         BOOLEAN     DEFAULT TRUE,
    steps_completed  JSONB,
    assertions_passed JSONB,
    error            TEXT,
    duration_ms      INTEGER
);

CREATE INDEX idx_task_runs_status     ON task_runs(status);
CREATE INDEX idx_task_runs_created_at ON task_runs(created_at DESC);
CREATE INDEX idx_task_runs_snapshot   ON task_runs(snapshot_id);

-- Artifacts: files produced by a task run
CREATE TABLE task_artifacts (
    artifact_id   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id       UUID        REFERENCES task_runs(task_id) ON DELETE CASCADE,
    artifact_type TEXT        CHECK (artifact_type IN ('screenshot', 'html', 'har', 'console_log', 'network_json')),
    file_path     TEXT,
    file_size     BIGINT,
    mime_type     TEXT,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_artifacts_task_id ON task_artifacts(task_id);

-- Network calls captured during a task run
CREATE TABLE network_calls (
    call_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id      UUID        REFERENCES task_runs(task_id) ON DELETE CASCADE,
    url          TEXT,
    method       TEXT,
    request_hdrs JSONB,
    post_data    TEXT,
    response_hdrs JSONB,
    response_body TEXT,
    response_status INTEGER,
    resource_type TEXT,
    tokens_found  JSONB,
    timestamp    TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_network_task_id ON network_calls(task_id);
CREATE INDEX idx_network_url    ON network_calls(url text_pattern_ops);

-- Task snapshots: versioned, reproducible task definitions
CREATE TABLE task_snapshots (
    snapshot_id      UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    task_definition  JSONB       NOT NULL,
    git_commit        TEXT,
    prompt_text       TEXT,
    created_at        TIMESTAMPTZ DEFAULT NOW(),
    creator           TEXT
);

CREATE INDEX idx_snapshots_created ON task_snapshots(created_at DESC);

COMMENT ON TABLE task_runs        IS 'Execution log for each Playwright task run';
COMMENT ON TABLE task_artifacts   IS 'Files produced during task execution (screenshots, HAR, etc.)';
COMMENT ON TABLE network_calls    IS 'Network traffic captured during task execution';
COMMENT ON TABLE task_snapshots   IS 'Frozen task definitions for reproducible/replayable runs';
