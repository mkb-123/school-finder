import { test, expect } from "@playwright/test";

/**
 * School Detail page (/schools/:id) E2E tests.
 *
 * Shows comprehensive information about a single school including its name,
 * Ofsted rating, address, and tabbed sections for Overview, Clubs,
 * Performance, Term Dates, and Admissions.
 *
 * NOTE: These tests rely on a seeded database. We navigate to the school
 * list first and click through to a real school, or go directly to a
 * known school ID.
 */
test.describe("School Detail Page", () => {
  /**
   * Before all tests, find a valid school ID by visiting the list page.
   * This ensures we test against a school that actually exists in the DB.
   */
  let schoolUrl: string;

  test.beforeAll(async ({ browser }) => {
    const page = await browser.newPage();
    await page.goto("/schools?council=Milton+Keynes&postcode=MK9+1AB");

    // Wait for school cards to load
    await page.waitForSelector(
      '[data-testid="school-card"] a, .school-card a, article a, [class*="SchoolCard"] a, a[href*="/schools/"]',
      { timeout: 15_000 }
    );

    // Extract the first school detail link
    const link = page.locator('a[href*="/schools/"]').first();
    const href = await link.getAttribute("href");

    // Fall back to /schools/1 if we cannot extract a link
    schoolUrl = href ?? "/schools/1";

    await page.close();
  });

  test.beforeEach(async ({ page }) => {
    await page.goto(schoolUrl);
    // Wait for the page content to render
    await page.waitForSelector("h1, h2, [data-testid='school-name']", {
      timeout: 10_000,
    });
  });

  test.describe("Core Information", () => {
    test("should display the school name", async ({ page }) => {
      const schoolName = page.locator(
        "h1, [data-testid='school-name']"
      );
      await expect(schoolName.first()).toBeVisible();
      const text = await schoolName.first().textContent();
      expect(text!.trim().length).toBeGreaterThan(0);
    });

    test("should display the Ofsted rating", async ({ page }) => {
      // Ofsted rating could be text like "Outstanding", "Good", or a badge/icon
      const ofstedRating = page.locator(
        '[data-testid="ofsted-rating"], text=/Outstanding|Good|Requires Improvement|Inadequate/i, [class*="ofsted" i], [class*="rating" i]'
      );
      await expect(ofstedRating.first()).toBeVisible();
    });

    test("should display the school address", async ({ page }) => {
      // Address is typically displayed near the top of the detail page
      const address = page.locator(
        '[data-testid="school-address"], address, [class*="address" i]'
      );

      // If no explicit address element, look for postcode-like text (e.g. "MK" prefix)
      if ((await address.count()) > 0) {
        await expect(address.first()).toBeVisible();
      } else {
        // Fallback: the page body should contain something that looks like an address
        const bodyText = await page.locator("main, [class*='detail']").first().textContent();
        // Milton Keynes postcodes start with MK
        expect(bodyText).toMatch(/MK\d/i);
      }
    });
  });

  test.describe("Tabs", () => {
    /**
     * The detail page uses a tabbed interface with sections for:
     * Overview, Clubs, Performance, Term Dates, Admissions.
     */

    const expectedTabs = [
      "Overview",
      "Clubs",
      "Performance",
      "Term Dates",
      "Admissions",
    ];

    test("should display all expected tabs", async ({ page }) => {
      for (const tabName of expectedTabs) {
        const tab = page.locator(
          `[role="tab"]:has-text("${tabName}"), button:has-text("${tabName}"), a:has-text("${tabName}"), [data-testid="tab-${tabName.toLowerCase().replace(/\s+/g, "-")}"]`
        );
        await expect(tab.first()).toBeVisible();
      }
    });

    test("clicking the Clubs tab should show clubs content", async ({
      page,
    }) => {
      const clubsTab = page.locator(
        '[role="tab"]:has-text("Clubs"), button:has-text("Clubs"), a:has-text("Clubs")'
      );
      await clubsTab.first().click();

      // The clubs panel should now be visible
      const clubsContent = page.locator(
        '[role="tabpanel"], [data-testid="clubs-panel"], [class*="clubs" i], [class*="ClubList"]'
      );
      await expect(clubsContent.first()).toBeVisible();
    });

    test("clicking the Performance tab should show performance content", async ({
      page,
    }) => {
      const performanceTab = page.locator(
        '[role="tab"]:has-text("Performance"), button:has-text("Performance"), a:has-text("Performance")'
      );
      await performanceTab.first().click();

      const performanceContent = page.locator(
        '[role="tabpanel"], [data-testid="performance-panel"], [class*="performance" i], [class*="PerformanceChart"]'
      );
      await expect(performanceContent.first()).toBeVisible();
    });

    test("clicking the Term Dates tab should show term dates content", async ({
      page,
    }) => {
      const termDatesTab = page.locator(
        '[role="tab"]:has-text("Term Dates"), button:has-text("Term Dates"), a:has-text("Term Dates")'
      );
      await termDatesTab.first().click();

      const termDatesContent = page.locator(
        '[role="tabpanel"], [data-testid="term-dates-panel"], [class*="term" i], table, [class*="calendar" i]'
      );
      await expect(termDatesContent.first()).toBeVisible();
    });

    test("clicking the Admissions tab should show admissions content", async ({
      page,
    }) => {
      const admissionsTab = page.locator(
        '[role="tab"]:has-text("Admissions"), button:has-text("Admissions"), a:has-text("Admissions")'
      );
      await admissionsTab.first().click();

      const admissionsContent = page.locator(
        '[role="tabpanel"], [data-testid="admissions-panel"], [class*="admission" i], [class*="WaitingList"]'
      );
      await expect(admissionsContent.first()).toBeVisible();
    });

    test("switching tabs should change the visible content", async ({
      page,
    }) => {
      // Click Overview tab first (it may already be selected)
      const overviewTab = page.locator(
        '[role="tab"]:has-text("Overview"), button:has-text("Overview"), a:has-text("Overview")'
      );
      await overviewTab.first().click();
      const overviewContent = await page
        .locator('[role="tabpanel"], main section')
        .first()
        .textContent();

      // Switch to Clubs tab
      const clubsTab = page.locator(
        '[role="tab"]:has-text("Clubs"), button:has-text("Clubs"), a:has-text("Clubs")'
      );
      await clubsTab.first().click();

      // Wait briefly for the content to swap
      await page.waitForTimeout(500);

      const clubsContent = await page
        .locator('[role="tabpanel"], main section')
        .first()
        .textContent();

      // The visible content should have changed after switching tabs
      // (unless both sections happen to be empty, which is unlikely with seeded data)
      expect(clubsContent).not.toEqual(overviewContent);
    });
  });
});
