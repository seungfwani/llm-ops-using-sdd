-- Phase 2 foundational schema for LLM Ops platform
-- Aligns with entities defined in specs/001-document-llm-ops/data-model.md

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS model_catalog_entries (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL CHECK (type IN ('base', 'fine-tuned', 'external')),
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'under_review', 'approved', 'deprecated')),
    owner_team TEXT NOT NULL,
    metadata JSONB NOT NULL,
    lineage_dataset_ids UUID[],
    evaluation_summary JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, type, version)
);

CREATE TABLE IF NOT EXISTS dataset_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    storage_uri TEXT NOT NULL,
    pii_scan_status TEXT NOT NULL DEFAULT 'pending'
        CHECK (pii_scan_status IN ('pending', 'clean', 'failed')),
    quality_score INTEGER CHECK (quality_score BETWEEN 0 AND 100),
    change_log TEXT,
    owner_team TEXT NOT NULL,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS catalog_entry_datasets (
    catalog_entry_id UUID NOT NULL REFERENCES model_catalog_entries(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES dataset_records(id) ON DELETE CASCADE,
    PRIMARY KEY (catalog_entry_id, dataset_id)
);

CREATE TABLE IF NOT EXISTS prompt_templates (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    language TEXT,
    content TEXT NOT NULL,
    context_tags TEXT[],
    status TEXT NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'live', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, version)
);

CREATE TABLE IF NOT EXISTS prompt_experiments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    template_a_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    template_b_id UUID NOT NULL REFERENCES prompt_templates(id) ON DELETE CASCADE,
    allocation INTEGER NOT NULL CHECK (allocation BETWEEN 0 AND 100),
    metric TEXT NOT NULL,
    start_at TIMESTAMPTZ NOT NULL,
    end_at TIMESTAMPTZ,
    winner_template_id UUID REFERENCES prompt_templates(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS training_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_entry_id UUID NOT NULL REFERENCES model_catalog_entries(id) ON DELETE CASCADE,
    dataset_id UUID NOT NULL REFERENCES dataset_records(id) ON DELETE RESTRICT,
    job_type TEXT NOT NULL CHECK (job_type IN ('finetune', 'distributed')),
    resource_profile JSONB NOT NULL,
    scheduler_id TEXT,
    status TEXT NOT NULL DEFAULT 'queued'
        CHECK (status IN ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
    retry_policy JSONB,
    submitted_by TEXT NOT NULL,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS experiment_metrics (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    training_job_id UUID NOT NULL REFERENCES training_jobs(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS serving_endpoints (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_entry_id UUID NOT NULL REFERENCES model_catalog_entries(id) ON DELETE RESTRICT,
    environment TEXT NOT NULL CHECK (environment IN ('dev', 'stg', 'prod')),
    route TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'deploying'
        CHECK (status IN ('deploying', 'healthy', 'degraded', 'failed')),
    min_replicas INTEGER NOT NULL DEFAULT 1,
    max_replicas INTEGER NOT NULL DEFAULT 1,
    autoscale_policy JSONB,
    prompt_policy_id UUID REFERENCES prompt_templates(id),
    last_health_check TIMESTAMPTZ,
    rollback_plan TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (environment, route)
);

CREATE TABLE IF NOT EXISTS observability_snapshots (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    serving_endpoint_id UUID NOT NULL REFERENCES serving_endpoints(id) ON DELETE CASCADE,
    time_bucket TIMESTAMPTZ NOT NULL,
    latency_p50 DOUBLE PRECISION,
    latency_p95 DOUBLE PRECISION,
    error_rate DOUBLE PRECISION,
    token_per_request DOUBLE PRECISION,
    notes TEXT,
    UNIQUE (serving_endpoint_id, time_bucket)
);

CREATE TABLE IF NOT EXISTS evaluation_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    model_entry_id UUID NOT NULL REFERENCES model_catalog_entries(id) ON DELETE CASCADE,
    dataset_id UUID REFERENCES dataset_records(id) ON DELETE SET NULL,
    prompt_template_id UUID REFERENCES prompt_templates(id) ON DELETE SET NULL,
    run_type TEXT NOT NULL CHECK (run_type IN ('automated', 'human', 'llm_judge')),
    metrics JSONB NOT NULL,
    status TEXT NOT NULL,
    notes TEXT,
    run_by TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS governance_policies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    scope TEXT NOT NULL CHECK (scope IN ('model', 'dataset', 'user', 'project')),
    rules JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'retired')),
    last_reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (name, scope)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    actor_id TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    resource_id TEXT,
    result TEXT NOT NULL CHECK (result IN ('allowed', 'denied')),
    metadata JSONB,
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cost_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    resource_type TEXT NOT NULL CHECK (resource_type IN ('training', 'serving')),
    resource_id UUID NOT NULL,
    time_window TEXT NOT NULL,
    gpu_hours DOUBLE PRECISION,
    token_count BIGINT,
    cost_currency TEXT DEFAULT 'USD',
    cost_amount NUMERIC(14, 2),
    budget_variance NUMERIC(14, 2),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (resource_type, resource_id, time_window)
);

-- indexes to speed up common queries
CREATE INDEX IF NOT EXISTS idx_catalog_status ON model_catalog_entries (status);
CREATE INDEX IF NOT EXISTS idx_dataset_owner ON dataset_records (owner_team);
CREATE INDEX IF NOT EXISTS idx_training_status ON training_jobs (status);
CREATE INDEX IF NOT EXISTS idx_serving_env ON serving_endpoints (environment);
CREATE INDEX IF NOT EXISTS idx_audit_resource ON audit_logs (resource_type, resource_id);

