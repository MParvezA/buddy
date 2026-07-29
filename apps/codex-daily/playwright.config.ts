import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: "http://127.0.0.1:4317",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
    {
      name: "mobile",
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } },
    },
  ],
  webServer: {
    command:
      "CODEX_DAILY_DB_PATH=:memory: CODEX_DAILY_TEST_LOCAL_DATE=2026-07-29 CODEX_DAILY_OBSERVER_MODE=shared_live CODEX_DAILY_CODEX_PATH=./test/fixtures/fake-codex-app-server.py npm run start:e2e",
    url: "http://127.0.0.1:4317/api/health",
    reuseExistingServer: false,
    timeout: 30_000,
  },
});
