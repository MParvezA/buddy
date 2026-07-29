import { buildApp } from "./app.js";

const host = "127.0.0.1";
const port = Number.parseInt(process.env.CODEX_DAILY_PORT ?? "4317", 10);
const configuredDate = process.env.CODEX_DAILY_LOCAL_DATE;
const clock = configuredDate
  ? () => new Date(`${configuredDate}T12:00:00.000Z`)
  : undefined;

const app = await buildApp({
  logger: true,
  serveStatic: process.env.NODE_ENV !== "development",
  databasePath: process.env.CODEX_DAILY_DB_PATH,
  timezone: process.env.CODEX_DAILY_TIMEZONE,
  clock,
  observer: true,
  observerMode:
    process.env.CODEX_DAILY_OBSERVER_MODE === "shared_live"
      ? "shared_live"
      : "standalone_history",
  codexExecutable: process.env.CODEX_DAILY_CODEX_PATH,
  reportingTurnTimeoutMs: process.env.CODEX_DAILY_REPORTING_TURN_TIMEOUT_MS
    ? Number.parseInt(process.env.CODEX_DAILY_REPORTING_TURN_TIMEOUT_MS, 10)
    : undefined,
});

try {
  await app.listen({ host, port });
} catch (error) {
  app.log.error(error);
  process.exitCode = 1;
}
