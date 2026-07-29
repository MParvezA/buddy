import fastifyStatic from "@fastify/static";
import Fastify, { type FastifyInstance } from "fastify";
import { existsSync } from "node:fs";
import path from "node:path";
import type { HealthResponse } from "../shared/dashboard.js";
import { representativeDay } from "./representative-day.js";

interface BuildAppOptions {
  logger?: boolean;
  serveStatic?: boolean;
  staticRoot?: string;
}

export async function buildApp(options: BuildAppOptions = {}): Promise<FastifyInstance> {
  const app = Fastify({ logger: options.logger ?? false });

  app.get("/api/health", async (): Promise<HealthResponse> => ({
    service: "codex-daily",
    status: "ok",
    mode: "representative",
    connection: "not-connected",
  }));

  app.get("/api/day", async () => representativeDay);

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
