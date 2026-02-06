import { test, expect } from "@playwright/test";

/**
 * Home page (/) E2E tests.
 *
 * The landing page lets parents select a council and enter a postcode
 * before searching for schools in their catchment area.
 */
test.describe("Home Page", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test.describe("Page Layout", () => {
    test("should display the council selector dropdown", async ({ page }) => {
      // The council selector is the primary entry point for the app
      const councilSelector = page.locator(
        'select, [role="combobox"], [data-testid="council-selector"]'
      );
      await expect(councilSelector.first()).toBeVisible();
    });

    test("should display the postcode input field", async ({ page }) => {
      // Postcode input is used to geocode the user's location
      const postcodeInput = page.locator(
        'input[placeholder*="postcode" i], input[name="postcode"], [data-testid="postcode-input"]'
      );
      await expect(postcodeInput.first()).toBeVisible();
    });

    test("should display a search button", async ({ page }) => {
      const searchButton = page.locator(
        'button:has-text("Search"), button:has-text("Find Schools"), button[type="submit"], [data-testid="search-button"]'
      );
      await expect(searchButton.first()).toBeVisible();
    });

    test("should display a page heading or title", async ({ page }) => {
      // Verify some form of heading is visible on the landing page
      const heading = page.locator("h1, h2").first();
      await expect(heading).toBeVisible();
    });
  });

  test.describe("Council Selection", () => {
    test('should allow selecting "Milton Keynes" from the council dropdown', async ({
      page,
    }) => {
      // Locate the council selector (could be a <select> or custom combobox)
      const councilSelector = page.locator(
        'select, [role="combobox"], [data-testid="council-selector"]'
      );
      const selector = councilSelector.first();
      await expect(selector).toBeVisible();

      // Try native <select> first — selectOption works on <select> elements
      const tagName = await selector.evaluate((el) =>
        el.tagName.toLowerCase()
      );

      if (tagName === "select") {
        await selector.selectOption({ label: "Milton Keynes" });
        await expect(selector).toHaveValue(/milton/i);
      } else {
        // For custom combobox components: click to open, then pick the option
        await selector.click();
        const option = page.locator(
          'li:has-text("Milton Keynes"), [role="option"]:has-text("Milton Keynes")'
        );
        await option.first().click();
        await expect(selector).toContainText("Milton Keynes");
      }
    });

    test("should list available councils in the dropdown", async ({
      page,
    }) => {
      const councilSelector = page.locator(
        'select, [role="combobox"], [data-testid="council-selector"]'
      );
      const selector = councilSelector.first();
      await expect(selector).toBeVisible();

      const tagName = await selector.evaluate((el) =>
        el.tagName.toLowerCase()
      );

      if (tagName === "select") {
        // Native <select> — check that there is at least one <option>
        const optionCount = await selector.locator("option").count();
        expect(optionCount).toBeGreaterThan(0);
      } else {
        // Custom dropdown — click to reveal options, then check count
        await selector.click();
        const options = page.locator(
          '[role="option"], [role="listbox"] li'
        );
        const count = await options.count();
        expect(count).toBeGreaterThan(0);
      }
    });
  });

  test.describe("Postcode Entry", () => {
    test("should accept a valid postcode input", async ({ page }) => {
      const postcodeInput = page.locator(
        'input[placeholder*="postcode" i], input[name="postcode"], [data-testid="postcode-input"]'
      );
      const input = postcodeInput.first();
      await expect(input).toBeVisible();

      // Enter a Milton Keynes postcode
      await input.fill("MK9 1AB");
      await expect(input).toHaveValue("MK9 1AB");
    });

    test("should clear and re-enter postcode", async ({ page }) => {
      const postcodeInput = page.locator(
        'input[placeholder*="postcode" i], input[name="postcode"], [data-testid="postcode-input"]'
      );
      const input = postcodeInput.first();

      await input.fill("MK9 1AB");
      await expect(input).toHaveValue("MK9 1AB");

      await input.clear();
      await expect(input).toHaveValue("");

      await input.fill("MK7 6BJ");
      await expect(input).toHaveValue("MK7 6BJ");
    });
  });

  test.describe("Search Navigation", () => {
    test("should navigate to /schools with query params when search is submitted", async ({
      page,
    }) => {
      // Select a council
      const councilSelector = page.locator(
        'select, [role="combobox"], [data-testid="council-selector"]'
      );
      const selector = councilSelector.first();
      await expect(selector).toBeVisible();

      const tagName = await selector.evaluate((el) =>
        el.tagName.toLowerCase()
      );
      if (tagName === "select") {
        await selector.selectOption({ label: "Milton Keynes" });
      } else {
        await selector.click();
        const option = page.locator(
          '[role="option"]:has-text("Milton Keynes"), li:has-text("Milton Keynes")'
        );
        await option.first().click();
      }

      // Enter a postcode
      const postcodeInput = page.locator(
        'input[placeholder*="postcode" i], input[name="postcode"], [data-testid="postcode-input"]'
      );
      await postcodeInput.first().fill("MK9 1AB");

      // Click the search button
      const searchButton = page.locator(
        'button:has-text("Search"), button:has-text("Find Schools"), button[type="submit"], [data-testid="search-button"]'
      );
      await searchButton.first().click();

      // The app should navigate to /schools with council and postcode in the URL
      await page.waitForURL(/\/schools/);
      const url = page.url();
      expect(url).toContain("/schools");

      // Verify query parameters are present (council and/or postcode)
      const searchParams = new URL(url).searchParams;
      const hasCouncil = searchParams.has("council");
      const hasPostcode = searchParams.has("postcode");
      const hasLat = searchParams.has("lat");

      // At minimum, the URL should carry search context via query params
      expect(hasCouncil || hasPostcode || hasLat).toBe(true);
    });

    test("should not navigate if required fields are empty", async ({
      page,
    }) => {
      // Click search without filling anything in
      const searchButton = page.locator(
        'button:has-text("Search"), button:has-text("Find Schools"), button[type="submit"], [data-testid="search-button"]'
      );
      await searchButton.first().click();

      // Should remain on the home page
      await expect(page).toHaveURL(/\/$/);
    });
  });
});
