-- Migration: Add resource configuration fields to serving_endpoints table
-- This allows storing initial deployment settings for redeployment

ALTER TABLE serving_endpoints
ADD COLUMN IF NOT EXISTS use_gpu BOOLEAN,
ADD COLUMN IF NOT EXISTS cpu_request TEXT,
ADD COLUMN IF NOT EXISTS cpu_limit TEXT,
ADD COLUMN IF NOT EXISTS memory_request TEXT,
ADD COLUMN IF NOT EXISTS memory_limit TEXT;

-- Add comment for documentation
COMMENT ON COLUMN serving_endpoints.use_gpu IS 'Whether GPU resources are requested. NULL means use default from settings';
COMMENT ON COLUMN serving_endpoints.cpu_request IS 'CPU request (e.g., "2", "1000m"). NULL means use default from settings';
COMMENT ON COLUMN serving_endpoints.cpu_limit IS 'CPU limit (e.g., "4", "2000m"). NULL means use default from settings';
COMMENT ON COLUMN serving_endpoints.memory_request IS 'Memory request (e.g., "4Gi", "2G"). NULL means use default from settings';
COMMENT ON COLUMN serving_endpoints.memory_limit IS 'Memory limit (e.g., "8Gi", "4G"). NULL means use default from settings';

