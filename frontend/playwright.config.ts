import { defineConfig, devices } from "@playwright/test";

/**
 * Playwright configuration for School Finder E2E tests.
 *
 * Assumes the FastAPI backend (port 8000) and Vite dev server (port 5173)
 * are already running. If you want Playwright to start them automatically,
 * uncomment the webServer array below.
 *
 * Run tests:
 *   npx playwright test            # all tests
 *   npx playwright test e2e/home   # single spec
 *   npx playwright test --headed   # watch in browser
 */
export default defineConfig({
  /* Directory containing E2E spec files */
  testDir: "./e2e",

  /* Maximum time a single test can run before being marked as failed */
  timeout: 30_000,

  /* Maximum time expect() assertions can wait for a condition */
  expect: {
    timeout: 10_000,
  },

  /* Run tests sequentially in CI to avoid resource contention */
  fullyParallel: true,

  /* Fail the build on CI if you accidentally left test.only in the source code */
  forbidOnly: !!process.env.CI,

  /* Retry failed tests once in CI, never locally */
  retries: process.env.CI ? 1 : 0,

  /* Limit parallel workers in CI to avoid flakiness */
  workers: process.env.CI ? 1 : undefined,

  /* Reporter configuration */
  reporter: [
    ["html", { open: "never" }],
    ["list"],
  ],

  /* Shared settings for all projects */
  use: {
    /* Base URL for page.goto() calls — matches the Vite dev server */
    baseURL: "http://localhost:5173",

    /* Capture a screenshot when a test fails */
    screenshot: "only-on-failure",

    /* Record a trace on first retry so failures are easier to debug */
    trace: "on-first-retry",

    /* Reasonable viewport for desktop testing */
    viewport: { width: 1280, height: 720 },
  },

  /* Only run in Chromium for speed — add firefox/webkit here if broader coverage is needed */
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  /**
   * Web server configuration.
   *
   * Playwright can start the backend and frontend before tests run and
   * shut them down afterwards. Each entry waits for its URL to respond
   * before proceeding.
   *
   * If you prefer to start the servers yourself (e.g. in a separate
   * terminal or via docker-compose), leave this commented out.
   */
  webServer: [
    {
      /* FastAPI backend — started from the project root */
      command: "cd .. && uv run python -m src.main",
      url: "http://localhost:8000/docs",
      reuseExistingServer: !process.env.CI,
      timeout: 30_000,
    },
    {
      /* Vite dev server — started from the frontend directory */
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 15_000,
    },
  ],
});
