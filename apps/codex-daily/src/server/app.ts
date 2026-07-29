import fastifyStatic from "@fastify/static";
import Fastify, { type FastifyInstance } from "fastify";
import { existsSync } from "node:fs";
import path from "node:path";
import type { HealthResponse } from "../shared/dashboard.js";
import { registerPlanningRoutes } from "./planning/planning-routes.js";
import { PlanningService } from "./planning/planning-service.js";
import { representativeDay } from "./representative-day.js";
import { openDatabase } from "./storage/database.js";
import { PlanningRepository } from "./storage/planning-repository.js";

export interface BuildAppOptions {
  logger?: boolean;
  serveStatic?: boolean;
  staticRoot?: string;
  databasePath?: string;
  clock?: () => Date;
  timezone?: string;
  migrationsDirectory?: string;
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
  app.addHook("onClose", () => database.close());

  app.get("/api/health", async (): Promise<HealthResponse> => ({
    service: "codex-daily",
    status: "ok",
    mode: "representative",
    connection: "not-connected",
  }));

  app.get("/api/day", async () => representativeDay);
  await registerPlanningRoutes(app, planning);

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
