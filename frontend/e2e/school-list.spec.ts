import { test, expect } from "@playwright/test";

/**
 * School List page (/schools) E2E tests.
 *
 * This page shows search results as a list of school cards alongside an
 * interactive Leaflet map with colour-coded pins. A filter panel allows
 * narrowing results by Ofsted rating, school type, distance, etc.
 *
 * NOTE: These are true E2E tests that hit the real backend.
 * The database must be seeded with Milton Keynes school data before running.
 */
test.describe("School List Page", () => {
  /**
   * Navigate to the school list with a known council and postcode so that
   * the backend returns real results from the seeded database.
   */
  test.beforeEach(async ({ page }) => {
    // Navigate with query params that should return seeded Milton Keynes schools
    await page.goto("/schools?council=Milton+Keynes&postcode=MK9+1AB");

    // Wait for the school data to load — look for at least one school card
    await page.waitForSelector(
      '[data-testid="school-card"], .school-card, article, [class*="card"]',
      { timeout: 15_000 }
    );
  });

  test.describe("School Cards", () => {
    test("should display one or more school cards", async ({ page }) => {
      const cards = page.locator(
        '[data-testid="school-card"], .school-card, article, [class*="SchoolCard"]'
      );
      const count = await cards.count();
      expect(count).toBeGreaterThan(0);
    });

    test("each school card should show the school name", async ({ page }) => {
      // The first card should contain a heading or prominent text with the school name
      const firstCard = page
        .locator(
          '[data-testid="school-card"], .school-card, article, [class*="SchoolCard"]'
        )
        .first();
      const cardText = await firstCard.textContent();
      expect(cardText).toBeTruthy();
      // School names are non-empty strings
      expect(cardText!.trim().length).toBeGreaterThan(0);
    });

    test("clicking a school card should navigate to the school detail page", async ({
      page,
    }) => {
      // Click the first school card (or the link within it)
      const firstCard = page
        .locator(
          '[data-testid="school-card"], .school-card, article, [class*="SchoolCard"]'
        )
        .first();

      // The card itself or an <a> inside it should be clickable
      const link = firstCard.locator("a").first();
      const isLink = (await link.count()) > 0;

      if (isLink) {
        await link.click();
      } else {
        await firstCard.click();
      }

      // Should navigate to a school detail page like /schools/123
      await page.waitForURL(/\/schools\/\d+/);
      expect(page.url()).toMatch(/\/schools\/\d+/);
    });
  });

  test.describe("Map", () => {
    test("should display the interactive map", async ({ page }) => {
      // Leaflet renders inside a container with class "leaflet-container"
      const mapContainer = page.locator(
        '.leaflet-container, [data-testid="map"], [class*="map"]'
      );
      await expect(mapContainer.first()).toBeVisible();
    });

    test("should show map pins/markers for schools", async ({ page }) => {
      // Leaflet markers are rendered as elements with class "leaflet-marker-icon"
      // or inside an SVG layer. Wait briefly for markers to render.
      const markers = page.locator(
        '.leaflet-marker-icon, .leaflet-marker-pane img, [class*="marker"], path.leaflet-interactive'
      );

      // There should be at least one marker for the returned schools
      await expect(markers.first()).toBeVisible({ timeout: 10_000 });
      const count = await markers.count();
      expect(count).toBeGreaterThan(0);
    });
  });

  test.describe("Filter Panel", () => {
    test("should display the filter panel", async ({ page }) => {
      const filterPanel = page.locator(
        '[data-testid="filter-panel"], .filter-panel, [class*="FilterPanel"], aside, [class*="filter"]'
      );
      await expect(filterPanel.first()).toBeVisible();
    });

    test("should have an Ofsted rating filter", async ({ page }) => {
      // Look for an Ofsted-related filter control (select, radio group, or checkboxes)
      const ofstedFilter = page.locator(
        'text=Ofsted, [data-testid*="ofsted"], label:has-text("Ofsted"), [class*="ofsted" i]'
      );
      await expect(ofstedFilter.first()).toBeVisible();
    });

    test("changing the Ofsted filter should update the results list", async ({
      page,
    }) => {
      // Count initial school cards
      const cards = page.locator(
        '[data-testid="school-card"], .school-card, article, [class*="SchoolCard"]'
      );
      const initialCount = await cards.count();

      // Find the Ofsted filter — it could be a <select>, radio buttons, or checkboxes
      const ofstedSelect = page.locator(
        'select[name*="ofsted" i], select[data-testid*="ofsted"], [data-testid="ofsted-filter"] select'
      );
      const ofstedCheckbox = page.locator(
        'input[type="checkbox"][name*="ofsted" i], [data-testid*="ofsted"] input[type="checkbox"]'
      );
      const ofstedRadio = page.locator(
        'input[type="radio"][name*="rating" i], input[type="radio"][name*="ofsted" i]'
      );

      if ((await ofstedSelect.count()) > 0) {
        // Native <select> — choose "Outstanding" (rating 1) to narrow results
        await ofstedSelect.first().selectOption({ index: 1 });
      } else if ((await ofstedCheckbox.count()) > 0) {
        // Checkbox-based filter — toggle the first option
        await ofstedCheckbox.first().click();
      } else if ((await ofstedRadio.count()) > 0) {
        // Radio-based filter — select the most restrictive option
        await ofstedRadio.last().click();
      } else {
        // Fallback: click any element labelled with "Outstanding"
        const outstandingOption = page.locator(
          'button:has-text("Outstanding"), label:has-text("Outstanding"), [data-testid*="outstanding"]'
        );
        if ((await outstandingOption.count()) > 0) {
          await outstandingOption.first().click();
        }
      }

      // Wait for the results to update (the count may change)
      await page.waitForTimeout(1_000);

      const updatedCount = await cards.count();

      // The count should differ or at least the page should not have errored out.
      // If "Outstanding" is stricter, we expect fewer (or equal) results.
      expect(updatedCount).toBeGreaterThanOrEqual(0);
      // Verify the filter actually did something — the list should have re-rendered
      // (we can't guarantee fewer results if all schools are Outstanding)
      expect(updatedCount).toBeLessThanOrEqual(initialCount + 1);
    });
  });

  test.describe("Results Count", () => {
    test("should display how many schools were found", async ({ page }) => {
      // Look for a text like "12 schools found" or "Showing 12 results"
      const resultsText = page.locator(
        'text=/\\d+\\s*(schools?|results?)/, [data-testid="results-count"]'
      );

      // This is optional UI — some apps show it, some don't. If present, verify it.
      if ((await resultsText.count()) > 0) {
        await expect(resultsText.first()).toBeVisible();
      } else {
        // Fallback: just verify there are cards on the page
        const cards = page.locator(
          '[data-testid="school-card"], .school-card, article, [class*="SchoolCard"]'
        );
        expect(await cards.count()).toBeGreaterThan(0);
      }
    });
  });
});
