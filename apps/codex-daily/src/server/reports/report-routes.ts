import type { FastifyInstance, FastifyReply } from "fastify";
import type { UpdateReportScheduleRequest } from "../../shared/report.js";
import { assertLocalDate } from "../planning/local-date.js";
import { ReportScheduler } from "./report-scheduler.js";
import {
  ReportConflictError,
  ReportNotFoundError,
  ReportService,
} from "./report-service.js";

function error(reply: FastifyReply, status: number, code: string, message: string) {
  return reply.code(status).send({ error: { code, message } });
}

export async function registerReportRoutes(
  app: FastifyInstance,
  service: ReportService,
  scheduler: ReportScheduler,
): Promise<void> {
  app.get("/api/reports", async () => service.list());
  app.get("/api/reports/latest", async () => ({
    snapshot: service.latest(),
    scheduler: scheduler.state(),
  }));
  app.get<{ Params: { snapshotId: string } }>(
    "/api/reports/:snapshotId",
    async (request, reply) => {
      try {
        return service.find(request.params.snapshotId);
      } catch (reason) {
        if (reason instanceof ReportNotFoundError) {
          return error(reply, 404, "not_found", reason.message);
        }
        throw reason;
      }
    },
  );
  app.post<{ Body: { localDate?: string } }>(
    "/api/reports",
    async (request, reply) => {
      try {
        const localDate = request.body?.localDate
          ? assertLocalDate(request.body.localDate)
          : service.currentLocalDate();
        const snapshot = await service.generate(localDate, "manual");
        return reply.code(201).send(snapshot);
      } catch (reason) {
        if (reason instanceof Error && reason.message.includes("Date")) {
          return error(reply, 400, "validation", reason.message);
        }
        throw reason;
      }
    },
  );
  app.post<{ Params: { snapshotId: string } }>(
    "/api/reports/:snapshotId/narrative",
    async (request, reply) => {
      try {
        return await service.generateNarrative(request.params.snapshotId);
      } catch (reason) {
        if (reason instanceof ReportNotFoundError) {
          return error(reply, 404, "not_found", reason.message);
        }
        if (reason instanceof ReportConflictError) {
          return error(reply, 409, "conflict", reason.message);
        }
        throw reason;
      }
    },
  );
  app.get("/api/report-settings", async () => scheduler.state());
  app.put<{ Body: UpdateReportScheduleRequest }>(
    "/api/report-settings",
    async (request, reply) => {
      try {
        service.updateSchedule({
          time: request.body?.time,
          timezone: request.body?.timezone,
          narrativeEnabled: request.body?.narrativeEnabled,
        });
        await scheduler.preferencesChanged();
        return scheduler.state();
      } catch (reason) {
        return error(
          reply,
          400,
          "validation",
          reason instanceof Error ? reason.message : "Report settings are invalid.",
        );
      }
    },
  );
}
