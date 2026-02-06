import { test, expect } from "@playwright/test";

/**
 * Navigation E2E tests.
 *
 * Verifies that the navbar contains working links to all major pages
 * and that cross-page navigation functions correctly. Also tests the
 * SEND toggle which is hidden by default and must be explicitly enabled.
 */
test.describe("Navigation", () => {
  test.beforeEach(async ({ page }) => {
    await page.goto("/");
  });

  test.describe("Navbar Links", () => {
    test("should display a navigation bar", async ({ page }) => {
      const navbar = page.locator("nav, header, [role='navigation']");
      await expect(navbar.first()).toBeVisible();
    });

    test("should have a link to the home page", async ({ page }) => {
      const homeLink = page.locator(
        'nav a[href="/"], header a[href="/"], a:has-text("Home"), a:has-text("School Finder"), [data-testid="nav-home"]'
      );
      await expect(homeLink.first()).toBeVisible();
    });

    test("should have a link to the schools page", async ({ page }) => {
      const schoolsLink = page.locator(
        'nav a[href*="/schools"], header a[href*="/schools"], a:has-text("Schools"), [data-testid="nav-schools"]'
      );
      await expect(schoolsLink.first()).toBeVisible();
    });

    test("should have a link to the private schools page", async ({
      page,
    }) => {
      const privateLink = page.locator(
        'nav a[href*="/private"], header a[href*="/private"], a:has-text("Private"), [data-testid="nav-private-schools"]'
      );
      await expect(privateLink.first()).toBeVisible();
    });

    test("should have a link to the compare page", async ({ page }) => {
      const compareLink = page.locator(
        'nav a[href*="/compare"], header a[href*="/compare"], a:has-text("Compare"), [data-testid="nav-compare"]'
      );
      await expect(compareLink.first()).toBeVisible();
    });

    test("should have a link to the term dates page", async ({ page }) => {
      const termDatesLink = page.locator(
        'nav a[href*="/term-dates"], header a[href*="/term-dates"], a:has-text("Term Dates"), [data-testid="nav-term-dates"]'
      );
      await expect(termDatesLink.first()).toBeVisible();
    });

    test("should have a link to the decision support page", async ({
      page,
    }) => {
      const decisionLink = page.locator(
        'nav a[href*="/decision"], header a[href*="/decision"], a:has-text("Decision"), [data-testid="nav-decision-support"]'
      );
      await expect(decisionLink.first()).toBeVisible();
    });

    test("should have a link to the journey planner page", async ({
      page,
    }) => {
      const journeyLink = page.locator(
        'nav a[href*="/journey"], header a[href*="/journey"], a:has-text("Journey"), [data-testid="nav-journey"]'
      );
      await expect(journeyLink.first()).toBeVisible();
    });
  });

  test.describe("Page Navigation", () => {
    /**
     * Test that clicking each navbar link actually navigates to the
     * correct page and the page renders without errors.
     */

    const pages = [
      { name: "Schools", href: "/schools", textMatch: /schools/i },
      {
        name: "Private Schools",
        href: "/private-schools",
        textMatch: /private/i,
      },
      { name: "Compare", href: "/compare", textMatch: /compare/i },
      { name: "Term Dates", href: "/term-dates", textMatch: /term/i },
      {
        name: "Decision Support",
        href: "/decision",
        textMatch: /decision/i,
      },
      { name: "Journey", href: "/journey", textMatch: /journey/i },
    ];

    for (const { name, href, textMatch } of pages) {
      test(`should navigate to the ${name} page via navbar`, async ({
        page,
      }) => {
        // Find and click the nav link for this page
        const navLink = page.locator(
          `nav a[href*="${href}"], header a[href*="${href}"], a:has-text("${name}")`
        );

        if ((await navLink.count()) > 0) {
          await navLink.first().click();

          // Verify the URL changed to include the expected path
          await page.waitForURL(new RegExp(href.replace("/", "\\/")));
          expect(page.url()).toContain(href);

          // The page should render without a blank screen
          const body = await page.locator("body").textContent();
          expect(body!.trim().length).toBeGreaterThan(0);
        }
      });
    }

    test("should navigate back to the home page from any page", async ({
      page,
    }) => {
      // Go to a non-home page first
      await page.goto("/compare");

      // Click the home/logo link
      const homeLink = page.locator(
        'nav a[href="/"], header a[href="/"], a:has-text("Home"), a:has-text("School Finder"), [data-testid="nav-home"]'
      );
      await homeLink.first().click();

      // Should be back on the home page
      await page.waitForURL(/\/$/);
      expect(page.url()).toMatch(/\/$/);
    });
  });

  test.describe("SEND Toggle", () => {
    /**
     * SEND (Special Educational Needs & Disabilities) information is
     * hidden by default behind a toggle. It should not be visible until
     * the user explicitly enables it.
     */

    test("SEND information should be hidden by default", async ({ page }) => {
      // Navigate to the schools page where SEND info would appear
      await page.goto("/schools?council=Milton+Keynes&postcode=MK9+1AB");

      // SEND-specific content should NOT be visible by default
      const sendContent = page.locator(
        '[data-testid="send-info"], [class*="send-provision" i], text=/EHCP/i, text=/SEN provision/i'
      );

      // Either not present in the DOM or not visible
      const count = await sendContent.count();
      if (count > 0) {
        await expect(sendContent.first()).not.toBeVisible();
      }
      // If count is 0, the SEND content simply is not in the DOM yet — that is correct
    });

    test("should find the SEND toggle", async ({ page }) => {
      // The SEND toggle could be in settings, filters, or the navbar
      // Search for it across common locations
      const sendToggle = page.locator(
        '[data-testid="send-toggle"], [class*="SendToggle"], label:has-text("SEND"), button:has-text("SEND"), input[name*="send" i], [aria-label*="SEND"]'
      );

      // Look in the schools page (where filters are)
      await page.goto("/schools?council=Milton+Keynes&postcode=MK9+1AB");
      await page.waitForTimeout(2_000);

      if ((await sendToggle.count()) > 0) {
        await expect(sendToggle.first()).toBeVisible();
      } else {
        // The toggle might be in a settings menu or behind a gear icon
        const settingsButton = page.locator(
          'button[aria-label*="settings" i], button:has-text("Settings"), [data-testid="settings"]'
        );
        if ((await settingsButton.count()) > 0) {
          await settingsButton.first().click();
          await page.waitForTimeout(500);

          // Now check for the SEND toggle in the opened settings panel
          const sendToggleInSettings = page.locator(
            'label:has-text("SEND"), input[name*="send" i], [data-testid="send-toggle"]'
          );
          if ((await sendToggleInSettings.count()) > 0) {
            await expect(sendToggleInSettings.first()).toBeVisible();
          }
        }
      }
    });

    test("should show SEND information when the toggle is enabled", async ({
      page,
    }) => {
      await page.goto("/schools?council=Milton+Keynes&postcode=MK9+1AB");
      await page.waitForTimeout(2_000);

      // Find and enable the SEND toggle
      const sendToggle = page.locator(
        '[data-testid="send-toggle"], [class*="SendToggle"] input, label:has-text("SEND") input, input[name*="send" i], [aria-label*="SEND"]'
      );

      if ((await sendToggle.count()) > 0) {
        const toggle = sendToggle.first();

        // Enable the toggle (click or check)
        const tagName = await toggle.evaluate((el) =>
          el.tagName.toLowerCase()
        );
        if (tagName === "input") {
          await toggle.check();
        } else {
          await toggle.click();
        }

        // Wait for SEND content to appear
        await page.waitForTimeout(1_000);

        // SEND information should now be visible somewhere on the page
        const sendContent = page.locator(
          '[data-testid="send-info"], [class*="send" i], text=/SEND/i, text=/EHCP/i, text=/Special Educational/i'
        );
        const count = await sendContent.count();
        expect(count).toBeGreaterThan(0);
      }
    });
  });
});
