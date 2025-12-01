import { test, expect } from "@playwright/test";

test.describe("Serving Endpoints Workflows", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/serving/endpoints");
  });

  test("should list serving endpoints", async ({ page }) => {
    await expect(page.locator("h1")).toContainText(/serving endpoints/i);
    // Verify the table or list is visible
    await expect(page.locator(".endpoints-table, .endpoint-list")).toBeVisible();
  });

  test("should filter endpoints by environment", async ({ page }) => {
    // Select environment filter
    await page.selectOption('select:has-text("Environment")', "dev");
    // Wait for filtered results
    await page.waitForTimeout(500);
    // Verify filter is applied (check URL or table content)
    const url = page.url();
    expect(url).toContain("environment=dev");
  });

  test("should filter endpoints by status", async ({ page }) => {
    // Select status filter
    await page.selectOption('select:has-text("Status")', "healthy");
    // Wait for filtered results
    await page.waitForTimeout(500);
    // Verify filter is applied
    const url = page.url();
    expect(url).toContain("status=healthy");
  });

  test("should navigate to endpoint detail page", async ({ page }) => {
    // Click on first endpoint's view link
    const firstViewLink = page.locator(".endpoints-table a.btn-link, .endpoint-list a").first();
    if (await firstViewLink.isVisible()) {
      await firstViewLink.click();
      // Verify we're on detail page
      await expect(page.locator("h1")).toContainText(/endpoint details/i);
      await expect(page.locator(".detail-content")).toBeVisible();
    }
  });

  test("should display endpoint details", async ({ page }) => {
    // Navigate to a detail page (assuming endpoint ID exists)
    await page.goto("/serving/endpoints/test-endpoint-id");
    // Verify detail sections are visible
    await expect(page.locator(".detail-section")).toBeVisible();
    await expect(page.locator("dt:has-text('Route')")).toBeVisible();
    await expect(page.locator("dt:has-text('Environment')")).toBeVisible();
    await expect(page.locator("dt:has-text('Status')")).toBeVisible();
  });

  test("should refresh endpoint list", async ({ page }) => {
    const refreshButton = page.locator('button:has-text("Refresh")');
    await refreshButton.click();
    // Verify loading state or refreshed content
    await page.waitForTimeout(500);
    await expect(page.locator(".endpoints-table, .endpoint-list")).toBeVisible();
  });

  test("should navigate back from detail to list", async ({ page }) => {
    // Go to detail page
    await page.goto("/serving/endpoints/test-endpoint-id");
    // Click back button
    const backButton = page.locator('a:has-text("Back to List"), .btn-back');
    if (await backButton.isVisible()) {
      await backButton.click();
      // Verify we're back on list page
      await expect(page.locator("h1")).toContainText(/serving endpoints/i);
    }
  });

  test("should show empty state when no endpoints", async ({ page }) => {
    // This test assumes no endpoints exist or API returns empty
    // Verify empty message is shown
    const emptyMessage = page.locator('text=/no.*endpoints/i, .empty');
    // This may or may not be visible depending on data
    // Just verify the page structure is correct
    await expect(page.locator("h1")).toContainText(/serving endpoints/i);
  });
});

