import { startCodexDaily } from "../../src/server/startup.js";

const configuredDate = process.env.CODEX_DAILY_TEST_LOCAL_DATE;
if (!configuredDate || !/^\d{4}-\d{2}-\d{2}$/.test(configuredDate)) {
  throw new Error("CODEX_DAILY_TEST_LOCAL_DATE must be an ISO local date.");
}

await startCodexDaily(
  () => new Date(`${configuredDate}T12:00:00.000Z`),
);
