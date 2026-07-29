import fastifyStatic from "@fastify/static";
import Fastify, { type FastifyInstance } from "fastify";
import { existsSync } from "node:fs";
import path from "node:path";
import type { HealthResponse } from "../shared/dashboard.js";
import type { ObserverMode } from "../shared/observer-types.js";
import { registerAttentionRoutes } from "./attention/attention-routes.js";
import { AttentionService } from "./attention/attention-service.js";
import { AttentionRepository } from "./attention/attention-repository.js";
import { registerObserverRoutes } from "./codex/observer-routes.js";
import { ObserverService } from "./codex/observer-service.js";
import type { ProcessFactory } from "./codex/app-server-client.js";
import { registerPlanningRoutes } from "./planning/planning-routes.js";
import { PlanningService } from "./planning/planning-service.js";
import { representativeDay } from "./representative-day.js";
import { openDatabase } from "./storage/database.js";
import { ObserverRepository } from "./storage/observer-repository.js";
import { PlanningRepository } from "./storage/planning-repository.js";

export interface BuildAppOptions {
  logger?: boolean;
  serveStatic?: boolean;
  staticRoot?: string;
  databasePath?: string;
  clock?: () => Date;
  timezone?: string;
  migrationsDirectory?: string;
  observer?: boolean;
  observerMode?: ObserverMode;
  codexExecutable?: string;
  processFactory?: ProcessFactory;
  observerInventoryIntervalMs?: number;
  observerRequestTimeoutMs?: number;
  observerReconnectBaseMs?: number;
  observerReconnectMaxMs?: number;
  attentionSweepIntervalMs?: number;
}

export async function buildApp(options: BuildAppOptions = {}): Promise<FastifyInstance> {
  const app = Fastify({ logger: options.logger ?? false });
  const database = openDatabase({
    path:
      options.databasePath ??
      path.resolve(process.cwd(), ".codex-daily-data/codex-daily.sqlite"),
    migrationsDirectory: options.migrationsDirectory,
  });
  const planning = new PlanningService({
    repository: new PlanningRepository(database.connection),
    clock: options.clock,
    timezone: options.timezone,
  });
  const observer = new ObserverService({
    repository: new ObserverRepository(database.connection),
    mode: options.observerMode,
    executable: options.codexExecutable,
    processFactory: options.processFactory,
    clock: options.clock,
    inventoryIntervalMs: options.observerInventoryIntervalMs,
    requestTimeoutMs: options.observerRequestTimeoutMs,
    reconnectBaseMs: options.observerReconnectBaseMs,
    reconnectMaxMs: options.observerReconnectMaxMs,
  });
  const attention = new AttentionService({
    repository: new AttentionRepository(database.connection),
    observer,
    clock: options.clock,
    sweepIntervalMs: options.attentionSweepIntervalMs,
  });
  app.addHook("onClose", async () => {
    attention.stop();
    await observer.stop();
    database.close();
  });

  app.get("/api/health", async (): Promise<HealthResponse> => ({
    service: "codex-daily",
    status: "ok",
    mode: "observer",
    connection: {
      state: observer.snapshot().health.state,
      capability: observer.snapshot().health.capability,
      diagnostic: observer.snapshot().health.diagnostic,
    },
  }));

  app.get("/api/day", async () => representativeDay);
  await registerPlanningRoutes(app, planning);
  await registerObserverRoutes(app, observer);
  await registerAttentionRoutes(app, attention);
  attention.start();
  if (options.observer ?? process.env.NODE_ENV !== "test") {
    void observer.start();
  }

  if (options.serveStatic ?? true) {
    const staticRoot = options.staticRoot ?? path.resolve(process.cwd(), "dist/client");
    if (!existsSync(staticRoot)) {
      throw new Error(`Built client not found at ${staticRoot}. Run npm run build first.`);
    }

    await app.register(fastifyStatic, {
      root: staticRoot,
      wildcard: false,
    });

    app.setNotFoundHandler((request, reply) => {
      if (request.url.startsWith("/api/")) {
        return reply.code(404).send({ error: "Not found" });
      }
      return reply.sendFile("index.html");
    });
  }

  return app;
}
