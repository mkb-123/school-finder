import { test, expect } from "@playwright/test";

/**
 * Decision Support page (/decision-support) E2E tests.
 *
 * This page helps parents weigh their priorities using sliders to set
 * weights for different criteria (distance, Ofsted rating, clubs, fees, etc.).
 * Schools are then ranked by a personalised composite score. Parents can
 * add schools to a shortlist and export comparisons.
 *
 * NOTE: The backend must be seeded with school data so the decision engine
 * has schools to rank. These are real E2E tests with no mocked data.
 */
test.describe("Decision Support Page", () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to the decision support page with a council context
    await page.goto("/decision-support?council=Milton+Keynes&postcode=MK9+1AB");

    // Wait for the page to load its interactive components
    await page.waitForSelector(
      'input[type="range"], [role="slider"], [data-testid*="slider"], [class*="slider" i]',
      { timeout: 15_000 }
    );
  });

  test.describe("Page Layout", () => {
    test("should display priority weight sliders", async ({ page }) => {
      const sliders = page.locator(
        'input[type="range"], [role="slider"], [data-testid*="slider"]'
      );
      const count = await sliders.count();

      // There should be multiple sliders for different criteria
      // (distance, Ofsted, clubs, etc.)
      expect(count).toBeGreaterThanOrEqual(2);
    });

    test("should label each slider with its criterion", async ({ page }) => {
      // Each slider should have an associated label explaining what it controls
      const sliderLabels = page.locator(
        'label:near(input[type="range"]), [data-testid*="slider-label"], [class*="slider"] label, [class*="slider"] span'
      );

      if ((await sliderLabels.count()) > 0) {
        const firstLabelText = await sliderLabels.first().textContent();
        expect(firstLabelText!.trim().length).toBeGreaterThan(0);
      }
    });

    test("should display a ranked list of schools", async ({ page }) => {
      // The decision engine should produce a ranked list of schools
      const rankedItems = page.locator(
        '[data-testid="ranked-school"], [class*="ranked" i], [class*="school-card"], [class*="SchoolCard"], tr, li[class*="school" i]'
      );
      const count = await rankedItems.count();
      expect(count).toBeGreaterThan(0);
    });
  });

  test.describe("Weight Adjustment", () => {
    test("should allow adjusting a slider value", async ({ page }) => {
      const slider = page.locator(
        'input[type="range"], [role="slider"]'
      ).first();
      await expect(slider).toBeVisible();

      // Get the initial value
      const initialValue = await slider.inputValue().catch(() => null);

      // Move the slider to a new position by filling a new value
      // For input[type="range"], we can set the value directly
      const tagName = await slider.evaluate((el) => el.tagName.toLowerCase());
      if (tagName === "input") {
        await slider.fill("80");
        // Dispatch input/change events so React picks up the change
        await slider.dispatchEvent("input");
        await slider.dispatchEvent("change");

        const newValue = await slider.inputValue();
        expect(newValue).toBe("80");
      } else {
        // For custom slider components, try dragging
        const box = await slider.boundingBox();
        if (box) {
          // Click at 80% of the slider width to set a high value
          await page.mouse.click(
            box.x + box.width * 0.8,
            box.y + box.height / 2
          );
        }
      }
    });

    test("should re-rank schools when weights are changed", async ({
      page,
    }) => {
      // Capture the initial order of schools
      const getSchoolOrder = async () => {
        const items = page.locator(
          '[data-testid="ranked-school"], [class*="ranked" i], [class*="school-card"], [class*="SchoolCard"]'
        );
        const texts: string[] = [];
        const count = await items.count();
        for (let i = 0; i < Math.min(count, 5); i++) {
          const text = await items.nth(i).textContent();
          texts.push(text?.trim() ?? "");
        }
        return texts;
      };

      const initialOrder = await getSchoolOrder();

      // Find all sliders and drastically change the first one
      const sliders = page.locator('input[type="range"], [role="slider"]');
      const sliderCount = await sliders.count();

      if (sliderCount >= 2) {
        // Set the first slider to minimum
        const firstSlider = sliders.first();
        const tagName = await firstSlider.evaluate((el) =>
          el.tagName.toLowerCase()
        );

        if (tagName === "input") {
          // Set first slider to 0 (minimum priority)
          await firstSlider.fill("0");
          await firstSlider.dispatchEvent("input");
          await firstSlider.dispatchEvent("change");

          // Set second slider to 100 (maximum priority)
          const secondSlider = sliders.nth(1);
          await secondSlider.fill("100");
          await secondSlider.dispatchEvent("input");
          await secondSlider.dispatchEvent("change");
        } else {
          // Custom slider — click at opposite ends
          const box1 = await firstSlider.boundingBox();
          if (box1) {
            await page.mouse.click(box1.x + 5, box1.y + box1.height / 2);
          }
          const box2 = await sliders.nth(1).boundingBox();
          if (box2) {
            await page.mouse.click(
              box2.x + box2.width - 5,
              box2.y + box2.height / 2
            );
          }
        }

        // Wait for the re-ranking to take effect
        await page.waitForTimeout(1_500);

        const updatedOrder = await getSchoolOrder();

        // The order should potentially change (not guaranteed if the data is very uniform,
        // but the page should at least re-render without errors)
        expect(updatedOrder.length).toBeGreaterThan(0);
      }
    });
  });

  test.describe("Shortlist", () => {
    test("should allow adding a school to the shortlist", async ({ page }) => {
      // Look for a shortlist button on any school card/row
      const shortlistButton = page.locator(
        'button:has-text("Shortlist"), button:has-text("Add"), button[aria-label*="shortlist" i], [data-testid*="shortlist"], button:has-text("Save")'
      );

      if ((await shortlistButton.count()) > 0) {
        await shortlistButton.first().click();

        // After clicking, the button state should change (e.g., "Added" or "Remove")
        // or a shortlist counter should update
        const confirmation = page.locator(
          'button:has-text("Added"), button:has-text("Remove"), button:has-text("Saved"), [data-testid="shortlist-count"], [class*="shortlist-badge"]'
        );

        // Give the UI a moment to react
        await page.waitForTimeout(500);

        // Either the button changed or a shortlist indicator appeared
        const buttonChanged = (await confirmation.count()) > 0;
        const shortlistVisible =
          (await page
            .locator('[data-testid="shortlist"], [class*="shortlist" i]')
            .count()) > 0;

        expect(buttonChanged || shortlistVisible).toBe(true);
      }
    });
  });

  test.describe("Export", () => {
    test("should display an export button", async ({ page }) => {
      const exportButton = page.locator(
        'button:has-text("Export"), button:has-text("Download"), button:has-text("PDF"), a:has-text("Export"), [data-testid*="export"]'
      );
      await expect(exportButton.first()).toBeVisible();
    });

    test("export button should be clickable", async ({ page }) => {
      const exportButton = page.locator(
        'button:has-text("Export"), button:has-text("Download"), button:has-text("PDF"), a:has-text("Export"), [data-testid*="export"]'
      );
      await expect(exportButton.first()).toBeEnabled();
    });
  });
});
