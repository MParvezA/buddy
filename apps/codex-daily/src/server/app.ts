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
import { registerReportRoutes } from "./reports/report-routes.js";
import { ReportRepository } from "./reports/report-repository.js";
import { ReportScheduler } from "./reports/report-scheduler.js";
import {
  ReportService,
  type ReportNarrativeProvider,
} from "./reports/report-service.js";
import { ReportingThreadNarrativeProvider } from "./reports/reporting-thread.js";
import { ObserverReportingGateway } from "./reports/observer-reporting-gateway.js";
import { openDatabase } from "./storage/database.js";
import { ObserverRepository } from "./storage/observer-repository.js";
import { PlanningRepository } from "./storage/planning-repository.js";
import { WriteCoordinator, LocalDataBusyError } from "./runtime/write-coordinator.js";
import { PrivacyService } from "./privacy/privacy-service.js";
import { registerPrivacyRoutes } from "./privacy/privacy-routes.js";
import { DiagnosticsService } from "./diagnostics/diagnostics-service.js";
import { SessionBriefRepository } from "./briefs/session-brief-repository.js";
import type { SessionBriefAnalyzer } from "./briefs/session-brief-analyzer.js";
import { SessionBriefGateway } from "./briefs/session-brief-gateway.js";
import { SessionBriefService } from "./briefs/session-brief-service.js";
import { registerSessionBriefRoutes } from "./briefs/session-brief-routes.js";

export interface BuildAppOptions {
  logger?: boolean;
  serveStatic?: boolean;
  staticRoot?: string;
  databasePath?: string;
  clock?: () => Date;
  timezone?: string;
  reportTime?: string;
  migrationsDirectory?: string;
  observer?: boolean;
  observerMode?: ObserverMode;
  codexExecutable?: string;
  processFactory?: ProcessFactory;
  observerInventoryIntervalMs?: number;
  observerRequestTimeoutMs?: number;
  reportingTurnTimeoutMs?: number;
  observerReconnectBaseMs?: number;
  observerReconnectMaxMs?: number;
  attentionSweepIntervalMs?: number;
  reportNarrativeProvider?: ReportNarrativeProvider;
  reportSetTimer?: typeof setTimeout;
  reportClearTimer?: typeof clearTimeout;
  version?: string;
  sessionBriefAnalyzer?: SessionBriefAnalyzer;
  sessionBriefRetentionIntervalMs?: number;
  sessionBriefDebounceMs?: number;
  sessionBriefRetryDelaysMs?: readonly [number, number];
  sessionBriefTurnTimeoutMs?: number;
}

function loopbackRequestAllowed(hostHeader: string | undefined, originHeader: string | undefined) {
  if (!hostHeader) return false;
  let host: URL;
  try {
    host = new URL(`http://${hostHeader}`);
  } catch {
    return false;
  }
  if (
    host.username ||
    host.password ||
    host.pathname !== "/" ||
    host.search ||
    host.hash ||
    !["127.0.0.1", "localhost", "[::1]"].includes(host.hostname.toLowerCase())
  ) {
    return false;
  }
  if (!originHeader) return true;
  try {
    const origin = new URL(originHeader);
    return (
      origin.protocol === "http:" &&
      origin.username === "" &&
      origin.password === "" &&
      origin.pathname === "/" &&
      origin.search === "" &&
      origin.hash === "" &&
      origin.host.toLowerCase() === host.host.toLowerCase()
    );
  } catch {
    return false;
  }
}

export async function buildApp(options: BuildAppOptions = {}): Promise<FastifyInstance> {
  const app = Fastify({ logger: options.logger ?? false });
  const database = openDatabase({
    path:
      options.databasePath ??
      path.resolve(process.cwd(), ".codex-daily-data/codex-daily.sqlite"),
    migrationsDirectory: options.migrationsDirectory,
  });
  const reportRepository = new ReportRepository(database.connection);
  const planning = new PlanningService({
    repository: new PlanningRepository(database.connection),
    clock: options.clock,
    timezone: () => reportRepository.getSchedule().timezone,
  });
  const observer = new ObserverService({
    repository: new ObserverRepository(database.connection),
    mode: options.observerMode,
    executable: options.codexExecutable,
    processFactory: options.processFactory,
    clock: options.clock,
    inventoryIntervalMs: options.observerInventoryIntervalMs,
    requestTimeoutMs: options.observerRequestTimeoutMs,
    reportingTurnTimeoutMs: options.reportingTurnTimeoutMs,
    reconnectBaseMs: options.observerReconnectBaseMs,
    reconnectMaxMs: options.observerReconnectMaxMs,
  });
  const sessionBriefs = new SessionBriefService({
    repository: new SessionBriefRepository(database.connection),
    observer,
    analyzer:
      options.sessionBriefAnalyzer ??
      new SessionBriefGateway(observer, options.sessionBriefTurnTimeoutMs),
    clock: options.clock,
    retentionIntervalMs: options.sessionBriefRetentionIntervalMs,
    debounceMs: options.sessionBriefDebounceMs,
    retryDelaysMs: options.sessionBriefRetryDelaysMs,
  });
  const attention = new AttentionService({
    repository: new AttentionRepository(database.connection),
    observer,
    clock: options.clock,
    sweepIntervalMs: options.attentionSweepIntervalMs,
  });
  const reports = new ReportService(
    reportRepository,
    options.clock,
    options.reportNarrativeProvider ??
      new ReportingThreadNarrativeProvider(new ObserverReportingGateway(observer)),
  );
  reports.recoverOrphanedNarratives();
  if (options.timezone || options.reportTime) {
    const configured = reports.schedule();
    reports.updateSchedule({
      ...configured,
      timezone: options.timezone ?? configured.timezone,
      time: options.reportTime ?? configured.time,
    });
  }
  const reportScheduler = new ReportScheduler({
    service: reports,
    repository: reportRepository,
    clock: options.clock,
    setTimer: options.reportSetTimer,
    clearTimer: options.reportClearTimer,
  });
  const observerEnabled = options.observer ?? process.env.NODE_ENV !== "test";
  const coordinator = new WriteCoordinator();
  const pauseWriters = async () => {
    await sessionBriefs.pauseAndDrain();
    await reportScheduler.stopAndDrain();
    attention.stop();
    await observer.stop();
  };
  const resumeWriters = async () => {
    attention.start();
    reportScheduler.resume();
    if (observerEnabled) void observer.start();
    sessionBriefs.resume();
  };
  const privacy = new PrivacyService({
    database: database.connection,
    reports: reportRepository,
    coordinator,
    clock: options.clock,
    pauseWriters,
    resumeWriters,
  });
  const diagnostics = new DiagnosticsService({
    dataLocation: database.path,
    privacy,
    observer,
    scheduler: reportScheduler,
    reports: reportRepository,
    version: options.version ?? "0.1.0",
  });
  const writeReleases = new WeakMap<object, () => void>();
  app.addHook("onRequest", async (request, reply) => {
    const origin =
      typeof request.headers.origin === "string"
        ? request.headers.origin
        : undefined;
    if (!loopbackRequestAllowed(request.headers.host, origin)) {
      return reply.code(403).send({
        error: {
          code: "forbidden",
          message: "Codex Daily accepts only same-origin loopback requests.",
        },
      });
    }
    if (
      ["GET", "HEAD", "OPTIONS"].includes(request.method) ||
      request.url.startsWith("/api/operations/")
    ) {
      return;
    }
    try {
      writeReleases.set(request, coordinator.beginWrite());
    } catch (error) {
      if (error instanceof LocalDataBusyError) {
        return reply.code(503).send({
          error: { code: "maintenance", message: error.message },
        });
      }
      throw error;
    }
  });
  const releaseWrite = (request: object) => {
    writeReleases.get(request)?.();
    writeReleases.delete(request);
  };
  app.addHook("onResponse", async (request) => releaseWrite(request));
  app.addHook("onError", async (request) => releaseWrite(request));
  app.addHook("onClose", async () => {
    await sessionBriefs.stop();
    await reportScheduler.stopAndDrain();
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

  await registerPlanningRoutes(app, planning);
  await registerObserverRoutes(app, observer);
  await registerSessionBriefRoutes(app, sessionBriefs);
  await registerAttentionRoutes(app, attention);
  await registerReportRoutes(app, reports, reportScheduler);
  await registerPrivacyRoutes(app, privacy, diagnostics);
  attention.start();
  sessionBriefs.start();
  await reportScheduler.start();
  if (observerEnabled) {
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
