-- Migration: Add output_model_storage_uri and output_model_entry_id columns to training_jobs table
-- Revision: 0004_output_model_fields
-- Revises: 0003_runtime_image

-- Add output_model_storage_uri column
ALTER TABLE training_jobs
ADD COLUMN output_model_storage_uri TEXT;

-- Add output_model_entry_id column with foreign key constraint
ALTER TABLE training_jobs
ADD COLUMN output_model_entry_id UUID;

-- Add foreign key constraint
ALTER TABLE training_jobs
ADD CONSTRAINT fk_training_jobs_output_model_entry_id
FOREIGN KEY (output_model_entry_id)
REFERENCES model_catalog_entries(id)
ON DELETE SET NULL;

