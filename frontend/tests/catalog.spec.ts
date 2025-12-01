import { test, expect } from "@playwright/test";

test.describe("Catalog Workflows", () => {
  test.beforeEach(async ({ page }) => {
    // Assume base URL is set via VITE_API_BASE_URL
    await page.goto("/catalog/models");
  });

  test("should list existing model entries", async ({ page }) => {
    await expect(page.locator("h1")).toContainText(/models/i);
    // Verify API call was made (check network or mock)
    await expect(page.locator('[data-testid="model-list"]')).toBeVisible();
  });

  test("should create a new model entry", async ({ page }) => {
    await page.click('button:has-text("Create Model")');
    await page.fill('input[name="name"]', "test-model-v1");
    await page.fill('input[name="version"]', "1.0.0");
    await page.selectOption('select[name="type"]', "base");
    await page.fill('textarea[name="metadata"]', '{"purpose": "test"}');
    await page.click('button:has-text("Submit")');
    // Verify success message or redirect
    await expect(page.locator('[data-testid="success-message"]')).toBeVisible({
      timeout: 5000,
    });
  });

  test("should show model detail page", async ({ page }) => {
    // Click first model in list
    await page.click('[data-testid="model-list"] >> first');
    await expect(page.locator("h1")).toContainText(/model detail/i);
    await expect(page.locator('[data-testid="model-metadata"]')).toBeVisible();
  });

  test("should trigger approval workflow", async ({ page }) => {
    await page.click('[data-testid="model-list"] >> first');
    await page.click('button:has-text("Request Approval")');
    await expect(page.locator('[data-testid="status"]')).toContainText(
      /under_review/i
    );
  });

  test("should upload model files", async ({ page }) => {
    // Navigate to model detail page
    await page.click('[data-testid="model-list"] >> first');
    await expect(page.locator("h1")).toContainText(/model detail/i);
    
    // Create a test file
    const testFile = new File(["test content"], "config.json", { type: "application/json" });
    
    // Upload file via drag and drop or file input
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "config.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"test": "data"}'),
    });
    
    // Verify file appears in file list
    await expect(page.locator('.file-list')).toBeVisible();
    await expect(page.locator('.file-item')).toContainText("config.json");
    
    // Click upload button
    await page.click('button:has-text("Upload Files")');
    
    // Wait for upload to complete (with timeout)
    await expect(page.locator('.upload-progress, .message.success')).toBeVisible({
      timeout: 10000,
    });
    
    // Verify storage URI is displayed
    await expect(page.locator('dt:has-text("Storage URI")')).toBeVisible();
  });

  test("should create model with file upload", async ({ page }) => {
    await page.click('button:has-text("Create New Model")');
    await page.fill('input[placeholder*="name"]', "test-model-with-files");
    await page.fill('input[placeholder*="version"]', "1.0.0");
    await page.selectOption('select', "base");
    await page.fill('input[placeholder*="team"]', "test-team");
    await page.fill('textarea', '{"description": "Test model"}');
    
    // Upload file before submitting
    const fileInput = page.locator('input[type="file"]');
    await fileInput.setInputFiles({
      name: "config.json",
      mimeType: "application/json",
      buffer: Buffer.from('{"test": "data"}'),
    });
    
    // Submit form
    await page.click('button:has-text("Create Model")');
    
    // Wait for redirect to detail page
    await expect(page).toHaveURL(/\/catalog\/models\/[^/]+$/, { timeout: 5000 });
    
    // Verify model was created and file upload status
    await expect(page.locator("h1")).toContainText(/model detail/i);
  });
});

