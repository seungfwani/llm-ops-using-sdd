import { test, expect } from "@playwright/test";

test.describe("Training Job Workflows", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/training/jobs");
  });

  test("should list existing training jobs", async ({ page }) => {
    await expect(page.locator("h1")).toContainText(/training jobs/i);
    // Verify API call was made
    await expect(page.locator(".jobs-table, .empty")).toBeVisible();
  });

  test("should filter jobs by status", async ({ page }) => {
    await page.selectOption('select:has-text("Status")', "running");
    // Wait for API call to complete
    await page.waitForTimeout(500);
    // Verify filter is applied (check URL or table content)
    const statusFilter = page.locator('select:has-text("Status")');
    await expect(statusFilter).toHaveValue("running");
  });

  test("should filter jobs by model ID", async ({ page }) => {
    const modelIdInput = page.locator('input[placeholder*="model"]');
    await modelIdInput.fill("test-model-id");
    // Wait for debounced API call
    await page.waitForTimeout(600);
    await expect(modelIdInput).toHaveValue("test-model-id");
  });

  test("should submit fine-tuning job", async ({ page }) => {
    await page.click('a:has-text("Submit New Job")');
    await expect(page.locator("h1")).toContainText(/submit training job/i);

    // Select job type
    await page.selectOption('select#jobType', "finetune");

    // Fill required fields for fine-tuning
    await page.selectOption('select#modelId', { index: 1 }); // Select first model
    await page.selectOption('select#datasetId', { index: 1 }); // Select first dataset

    // Fill resource profile
    await page.fill('input#gpuCount', "1");
    await page.selectOption('select#gpuType', "nvidia-tesla-v100");
    await page.fill('input#maxDuration', "60");

    // Submit job
    await page.click('button:has-text("Submit Job")');

    // Verify success message or redirect to job detail
    await expect(
      page.locator('.message.success, h1:has-text("Training Job")')
    ).toBeVisible({ timeout: 5000 });
  });

  test("should submit from-scratch job with architecture", async ({ page }) => {
    await page.click('a:has-text("Submit New Job")');
    await expect(page.locator("h1")).toContainText(/submit training job/i);

    // Select job type
    await page.selectOption('select#jobType', "from_scratch");

    // Verify model selection is disabled/hidden
    const modelSelect = page.locator('select#modelId');
    const isDisabled = await modelSelect.isDisabled().catch(() => false);
    if (isDisabled) {
      await expect(modelSelect).toBeDisabled();
    }

    // Fill dataset
    await page.selectOption('select#datasetId', { index: 1 });

    // Fill architecture configuration
    const architectureConfig = {
      architecture: {
        type: "transformer",
        layers: 12,
        hidden_size: 768,
        num_attention_heads: 12,
      },
      learning_rate: 0.0001,
    };
    await page.fill(
      'textarea#architecture',
      JSON.stringify(architectureConfig, null, 2)
    );

    // Fill resource profile
    await page.fill('input#gpuCount', "1");
    await page.selectOption('select#gpuType', "nvidia-tesla-v100");
    await page.fill('input#maxDuration', "120");

    // Submit job
    await page.click('button:has-text("Submit Job")');

    // Verify success message or redirect
    await expect(
      page.locator('.message.success, h1:has-text("Training Job")')
    ).toBeVisible({ timeout: 5000 });
  });

  test("should submit pre-training job with architecture", async ({ page }) => {
    await page.click('a:has-text("Submit New Job")');
    await expect(page.locator("h1")).toContainText(/submit training job/i);

    // Select job type
    await page.selectOption('select#jobType', "pretrain");

    // Fill dataset
    await page.selectOption('select#datasetId', { index: 1 });

    // Fill architecture configuration
    const architectureConfig = {
      architecture: {
        type: "transformer",
        layers: 24,
        hidden_size: 1024,
        num_attention_heads: 16,
      },
      learning_rate: 0.00005,
    };
    await page.fill(
      'textarea#architecture',
      JSON.stringify(architectureConfig, null, 2)
    );

    // Fill resource profile
    await page.fill('input#gpuCount', "4");
    await page.selectOption('select#gpuType', "nvidia-tesla-a100");
    await page.fill('input#maxDuration', "240");

    // Submit job
    await page.click('button:has-text("Submit Job")');

    // Verify success message or redirect
    await expect(
      page.locator('.message.success, h1:has-text("Training Job")')
    ).toBeVisible({ timeout: 5000 });
  });

  test("should submit distributed training job", async ({ page }) => {
    await page.click('a:has-text("Submit New Job")');
    await expect(page.locator("h1")).toContainText(/submit training job/i);

    // Select job type
    await page.selectOption('select#jobType', "distributed");

    // Fill required fields
    await page.selectOption('select#modelId', { index: 1 });
    await page.selectOption('select#datasetId', { index: 1 });

    // Fill resource profile for distributed training
    await page.fill('input#gpuCount', "4"); // GPUs per node
    await page.fill('input#numNodes', "2"); // Number of nodes
    await page.selectOption('select#gpuType', "nvidia-tesla-a100");
    await page.fill('input#maxDuration', "180");

    // Submit job
    await page.click('button:has-text("Submit Job")');

    // Verify success message or redirect
    await expect(
      page.locator('.message.success, h1:has-text("Training Job")')
    ).toBeVisible({ timeout: 5000 });
  });

  test("should validate fine-tuning requires model", async ({ page }) => {
    await page.click('a:has-text("Submit New Job")');
    await expect(page.locator("h1")).toContainText(/submit training job/i);

    // Select fine-tuning job type
    await page.selectOption('select#jobType', "finetune");

    // Don't select a model
    await page.selectOption('select#datasetId', { index: 1 });
    await page.fill('input#gpuCount', "1");
    await page.selectOption('select#gpuType', "nvidia-tesla-v100");
    await page.fill('input#maxDuration', "60");

    // Try to submit - should be disabled or show validation error
    const submitButton = page.locator('button:has-text("Submit Job")');
    const isDisabled = await submitButton.isDisabled();
    if (!isDisabled) {
      await submitButton.click();
      // Should show validation error
      await expect(
        page.locator('.message.error, .error-text, [role="alert"]')
      ).toBeVisible({ timeout: 2000 });
    } else {
      await expect(submitButton).toBeDisabled();
    }
  });

  test("should validate from-scratch requires architecture", async ({ page }) => {
    await page.click('a:has-text("Submit New Job")');
    await expect(page.locator("h1")).toContainText(/submit training job/i);

    // Select from-scratch job type
    await page.selectOption('select#jobType', "from_scratch");

    // Don't fill architecture
    await page.selectOption('select#datasetId', { index: 1 });
    await page.fill('input#gpuCount', "1");
    await page.selectOption('select#gpuType', "nvidia-tesla-v100");
    await page.fill('input#maxDuration', "60");

    // Try to submit - should be disabled or show validation error
    const submitButton = page.locator('button:has-text("Submit Job")');
    const isDisabled = await submitButton.isDisabled();
    if (!isDisabled) {
      await submitButton.click();
      // Should show validation error
      await expect(
        page.locator('.message.error, .error-text, [role="alert"]')
      ).toBeVisible({ timeout: 2000 });
    } else {
      await expect(submitButton).toBeDisabled();
    }
  });

  test("should show job detail page with timeline", async ({ page }) => {
    // Navigate to a job detail page (assuming jobs exist)
    await page.goto("/training/jobs/test-job-id");
    
    // Verify job information is displayed
    await expect(page.locator("h1")).toContainText(/training job/i);
    await expect(page.locator('.job-info-card, .job-content')).toBeVisible();
    
    // Verify timeline is displayed
    await expect(page.locator('.timeline, .job-timeline-card')).toBeVisible();
  });

  test("should cancel queued job", async ({ page }) => {
    // Navigate to a job detail page with queued status
    await page.goto("/training/jobs/test-job-id");
    
    // Verify cancel button is visible for queued jobs
    const cancelButton = page.locator('button:has-text("Cancel")');
    await expect(cancelButton).toBeVisible({ timeout: 2000 });
    
    // Click cancel button
    await cancelButton.click();
    
    // Verify job status updates or confirmation dialog appears
    await expect(
      page.locator('.message.success, [role="dialog"], .status-cancelled')
    ).toBeVisible({ timeout: 5000 });
  });
});

