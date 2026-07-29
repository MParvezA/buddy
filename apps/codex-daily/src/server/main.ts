import { buildApp } from "./app.js";

const host = "127.0.0.1";
const port = Number.parseInt(process.env.CODEX_DAILY_PORT ?? "4317", 10);

const app = await buildApp({ logger: true, serveStatic: process.env.NODE_ENV !== "development" });

try {
  await app.listen({ host, port });
} catch (error) {
  app.log.error(error);
  process.exitCode = 1;
}
