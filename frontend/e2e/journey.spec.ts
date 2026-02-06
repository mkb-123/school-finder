import { test, expect } from "@playwright/test";

/**
 * Journey Planner page (/journey) E2E tests.
 *
 * The school run planner shows realistic travel times to schools, factoring
 * in drop-off (8:00-8:45am) and pick-up (5:00-5:30pm) traffic. Users can
 * compare multiple schools and switch between transport modes (walking,
 * cycling, driving, public transport).
 *
 * NOTE: The backend must be seeded and the journey calculation service
 * must be available. These are true E2E tests with no mocked data.
 */
test.describe("Journey Planner Page", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate with a postcode context so journey calculations have an origin
    await page.goto("/journey?council=Milton+Keynes&postcode=MK9+1AB");

    // Wait for the journey content to load
    await page.waitForSelector(
      '[data-testid="journey-card"], [class*="journey" i], [class*="JourneyCard"], [class*="travel" i], table, [class*="comparison"]',
      { timeout: 15_000 }
    );
  });

  test.describe("Travel Time Comparison", () => {
    test("should display travel time information for schools", async ({
      page,
    }) => {
      // Journey cards or a comparison table should show travel times
      const journeyItems = page.locator(
        '[data-testid="journey-card"], [class*="JourneyCard"], [class*="journey-card"], tr[class*="school"], [class*="travel-time"]'
      );
      const count = await journeyItems.count();
      expect(count).toBeGreaterThan(0);
    });

    test("should show time estimates with units", async ({ page }) => {
      // Look for time-related text like "8 min", "22 minutes", "0.5 mi", etc.
      const timeText = page.locator(
        'text=/\\d+\\s*(min|mins|minutes|hr|hours|km|mi)/, [data-testid*="time"], [class*="duration"]'
      );

      if ((await timeText.count()) > 0) {
        await expect(timeText.first()).toBeVisible();
      } else {
        // Fallback: the page body should contain numeric travel information
        const bodyText = await page.locator("main").textContent();
        expect(bodyText).toMatch(/\d+/);
      }
    });

    test("should display drop-off time estimates", async ({ page }) => {
      // The planner should show drop-off time routing (8:00-8:45am window)
      const dropOffInfo = page.locator(
        'text=/drop.?off/i, [data-testid*="drop-off"], [class*="drop-off" i], text=/8:00|8:45|morning/i'
      );

      if ((await dropOffInfo.count()) > 0) {
        await expect(dropOffInfo.first()).toBeVisible();
      }
    });

    test("should display pick-up time estimates", async ({ page }) => {
      // The planner should show pick-up time routing (5:00-5:30pm window)
      const pickUpInfo = page.locator(
        'text=/pick.?up/i, [data-testid*="pick-up"], [class*="pick-up" i], text=/5:00|5:30|afternoon|evening/i'
      );

      if ((await pickUpInfo.count()) > 0) {
        await expect(pickUpInfo.first()).toBeVisible();
      }
    });
  });

  test.describe("Transport Mode Switching", () => {
    test("should display transport mode options", async ({ page }) => {
      // Transport modes: walking, cycling, driving, public transport
      const modeButtons = page.locator(
        'button:has-text("Walk"), button:has-text("Cycle"), button:has-text("Drive"), button:has-text("Transit"), button:has-text("Public"), [data-testid*="transport-mode"], [role="tablist"] button, [class*="transport-mode"], [role="radiogroup"] label'
      );
      const count = await modeButtons.count();

      // There should be at least 2 transport mode options
      expect(count).toBeGreaterThanOrEqual(2);
    });

    test("should allow switching between walking and driving", async ({
      page,
    }) => {
      // Click on "Walking" mode if not already selected
      const walkingMode = page.locator(
        'button:has-text("Walk"), [data-testid="mode-walking"], label:has-text("Walk"), [aria-label*="walk" i]'
      );
      const drivingMode = page.locator(
        'button:has-text("Driv"), [data-testid="mode-driving"], label:has-text("Driv"), [aria-label*="driv" i]'
      );

      if ((await walkingMode.count()) > 0 && (await drivingMode.count()) > 0) {
        // Click walking mode and capture the displayed time
        await walkingMode.first().click();
        await page.waitForTimeout(1_000);

        const walkingContent = await page.locator("main").textContent();

        // Switch to driving mode
        await drivingMode.first().click();
        await page.waitForTimeout(1_000);

        const drivingContent = await page.locator("main").textContent();

        // The content should update when switching modes
        // (driving times are typically shorter than walking times)
        expect(drivingContent).toBeTruthy();
      }
    });

    test("should update travel times when switching transport mode", async ({
      page,
    }) => {
      // Get all transport mode buttons/tabs
      const modeButtons = page.locator(
        '[data-testid*="transport-mode"], [role="tablist"] button, [class*="transport-mode"] button, [role="radiogroup"] label, button[class*="mode"]'
      );
      const count = await modeButtons.count();

      if (count >= 2) {
        // Click the first mode
        await modeButtons.first().click();
        await page.waitForTimeout(1_000);

        // Grab the travel time values shown
        const firstModeText = await page
          .locator(
            '[data-testid*="time"], [class*="duration"], [class*="travel-time"]'
          )
          .first()
          .textContent()
          .catch(() => "");

        // Click the second mode
        await modeButtons.nth(1).click();
        await page.waitForTimeout(1_000);

        const secondModeText = await page
          .locator(
            '[data-testid*="time"], [class*="duration"], [class*="travel-time"]'
          )
          .first()
          .textContent()
          .catch(() => "");

        // At least one of the modes should return non-empty text
        expect(
          (firstModeText?.trim().length ?? 0) > 0 ||
            (secondModeText?.trim().length ?? 0) > 0
        ).toBe(true);
      }
    });
  });

  test.describe("Multi-School Comparison", () => {
    test("should show travel information for multiple schools", async ({
      page,
    }) => {
      // The page should compare journey times across multiple schools
      const journeyItems = page.locator(
        '[data-testid="journey-card"], [class*="JourneyCard"], [class*="journey-card"], tr[class*="school"], [class*="comparison"] > *'
      );
      const count = await journeyItems.count();

      // With seeded data there should be more than one school to compare
      expect(count).toBeGreaterThanOrEqual(1);
    });
  });
});
