-- control_plane.sql
-- Phase 10: Pipeline Control Plane
-- PostgreSQL schema additions for pipeline control and monitoring.

BEGIN;

-- Optional enums. If the project prefers TEXT + CHECK constraints,
-- Codex may replace these enums with TEXT columns and equivalent checks.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pipeline_run_status') THEN
        CREATE TYPE pipeline_run_status AS ENUM (
            'pending',
            'running',
            'cancelling',
            'cancelled',
            'failed',
            'success'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pipeline_stage_status') THEN
        CREATE TYPE pipeline_stage_status AS ENUM (
            'pending',
            'running',
            'success',
            'failed',
            'skipped'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pipeline_command_status') THEN
        CREATE TYPE pipeline_command_status AS ENUM (
            'pending',
            'accepted',
            'applied',
            'rejected',
            'failed'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pipeline_command_type') THEN
        CREATE TYPE pipeline_command_type AS ENUM (
            'start_run',
            'cancel_run',
            'retry_run',
            'retry_stage'
        );
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'pipeline_type_enum') THEN
        CREATE TYPE pipeline_type_enum AS ENUM (
            'full_pipeline',
            'crawl_only',
            'extract_only',
            'geocode_only',
            'analytics_only',
            'export_only'
        );
    END IF;
END
$$;

-- -------------------------------------------------------------------
-- pipeline_runs
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id BIGSERIAL PRIMARY KEY,
    pipeline_type pipeline_type_enum NOT NULL,
    status pipeline_run_status NOT NULL DEFAULT 'pending',
    current_stage_name TEXT NULL,
    target_scope TEXT NOT NULL DEFAULT 'all',
    parameters_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    requested_by TEXT NULL,
    created_by_command_id BIGINT NULL,
    replacement_for_run_id BIGINT NULL REFERENCES pipeline_runs(id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pipeline_runs_finished_terminal_chk CHECK (
        (status IN ('cancelled', 'failed', 'success') AND finished_at IS NOT NULL)
        OR
        (status IN ('pending', 'running', 'cancelling'))
    )
);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status_created_at
    ON pipeline_runs(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_created_at
    ON pipeline_runs(created_at DESC);

-- -------------------------------------------------------------------
-- pipeline_stage_runs
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pipeline_stage_runs (
    id BIGSERIAL PRIMARY KEY,
    pipeline_run_id BIGINT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    status pipeline_stage_status NOT NULL DEFAULT 'pending',
    stage_order INTEGER NOT NULL,
    items_total INTEGER NULL,
    items_completed INTEGER NOT NULL DEFAULT 0,
    items_failed INTEGER NOT NULL DEFAULT 0,
    started_at TIMESTAMPTZ NULL,
    finished_at TIMESTAMPTZ NULL,
    error_message TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT pipeline_stage_runs_unique UNIQUE (pipeline_run_id, stage_name),
    CONSTRAINT pipeline_stage_runs_nonnegative_chk CHECK (
        items_completed >= 0 AND items_failed >= 0
    ),
    CONSTRAINT pipeline_stage_runs_finished_terminal_chk CHECK (
        (status IN ('success', 'failed', 'skipped') AND finished_at IS NOT NULL)
        OR
        (status IN ('pending', 'running'))
    )
);

CREATE INDEX IF NOT EXISTS idx_pipeline_stage_runs_run_stage
    ON pipeline_stage_runs(pipeline_run_id, stage_order);

CREATE INDEX IF NOT EXISTS idx_pipeline_stage_runs_run_status
    ON pipeline_stage_runs(pipeline_run_id, status);

-- -------------------------------------------------------------------
-- pipeline_progress
-- Current-state table, one row per run + stage.
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pipeline_progress (
    pipeline_run_id BIGINT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    stage_name TEXT NOT NULL,
    current_index INTEGER NOT NULL DEFAULT 0,
    total_items INTEGER NULL,
    items_completed INTEGER NOT NULL DEFAULT 0,
    items_failed INTEGER NOT NULL DEFAULT 0,
    current_document_id BIGINT NULL,
    current_document_url TEXT NULL,
    current_item_label TEXT NULL,
    message TEXT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (pipeline_run_id, stage_name),
    CONSTRAINT pipeline_progress_nonnegative_chk CHECK (
        current_index >= 0
        AND items_completed >= 0
        AND items_failed >= 0
        AND (total_items IS NULL OR total_items >= 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_pipeline_progress_run_updated
    ON pipeline_progress(pipeline_run_id, updated_at DESC);

-- -------------------------------------------------------------------
-- pipeline_logs
-- Primary persisted operator log source for UI.
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pipeline_logs (
    id BIGSERIAL PRIMARY KEY,
    pipeline_run_id BIGINT NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    stage_name TEXT NULL,
    service_name TEXT NOT NULL,
    level TEXT NOT NULL,
    event_type TEXT NULL,
    message TEXT NOT NULL,
    document_id BIGINT NULL,
    document_url TEXT NULL,
    current_index INTEGER NULL,
    payload_json JSONB NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pipeline_logs_run_id_id
    ON pipeline_logs(pipeline_run_id, id ASC);

CREATE INDEX IF NOT EXISTS idx_pipeline_logs_run_created
    ON pipeline_logs(pipeline_run_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_logs_run_stage_level
    ON pipeline_logs(pipeline_run_id, stage_name, level);

-- -------------------------------------------------------------------
-- pipeline_commands
-- Single control queue.
-- -------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS pipeline_commands (
    id BIGSERIAL PRIMARY KEY,
    command_type pipeline_command_type NOT NULL,
    pipeline_run_id BIGINT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    stage_name TEXT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status pipeline_command_status NOT NULL DEFAULT 'pending',
    requested_by TEXT NULL,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at TIMESTAMPTZ NULL,
    error_message TEXT NULL,
    dedupe_key TEXT NULL,
    CONSTRAINT pipeline_commands_stage_retry_requires_stage_chk CHECK (
        command_type <> 'retry_stage' OR stage_name IS NOT NULL
    )
);

CREATE INDEX IF NOT EXISTS idx_pipeline_commands_status_id
    ON pipeline_commands(status, id ASC);

CREATE INDEX IF NOT EXISTS idx_pipeline_commands_run_status_id
    ON pipeline_commands(pipeline_run_id, status, id ASC);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pipeline_commands_pending_dedupe
    ON pipeline_commands(dedupe_key)
    WHERE status = 'pending' AND dedupe_key IS NOT NULL;

-- -------------------------------------------------------------------
-- Helpful view: active run
-- -------------------------------------------------------------------

CREATE OR REPLACE VIEW v_active_pipeline_runs AS
SELECT *
FROM pipeline_runs
WHERE status IN ('pending', 'running', 'cancelling');

-- -------------------------------------------------------------------
-- Retention helper for logs: keep only logs for the most recent 10 runs.
-- This is an example SQL procedure. Backend may call equivalent SQL.
-- -------------------------------------------------------------------

CREATE OR REPLACE FUNCTION prune_pipeline_logs_keep_last_10_runs()
RETURNS INTEGER
LANGUAGE plpgsql
AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    WITH ranked_runs AS (
        SELECT id
        FROM pipeline_runs
        ORDER BY COALESCE(started_at, created_at) DESC, id DESC
        OFFSET 10
    ),
    deleted AS (
        DELETE FROM pipeline_logs
        WHERE pipeline_run_id IN (SELECT id FROM ranked_runs)
        RETURNING 1
    )
    SELECT COUNT(*) INTO deleted_count FROM deleted;

    RETURN COALESCE(deleted_count, 0);
END;
$$;

COMMIT;