import type { FastifyInstance, FastifyReply } from "fastify";
import type { DiagnosticsService } from "../diagnostics/diagnostics-service.js";
import {
  PrivacyConfirmationError,
  PrivacyService,
} from "./privacy-service.js";

function failure(reply: FastifyReply, status: number, code: string, message: string) {
  return reply.code(status).send({ error: { code, message } });
}

export async function registerPrivacyRoutes(
  app: FastifyInstance,
  privacy: PrivacyService,
  diagnostics: DiagnosticsService,
): Promise<void> {
  app.get("/api/operations/diagnostics", async () => diagnostics.snapshot());
  app.get("/api/operations/export", async (_request, reply) =>
    reply
      .header("content-disposition", "attachment; filename=\"codex-daily-export.json\"")
      .send(privacy.export()),
  );
  app.delete<{ Params: { localDate: string }; Body: { confirmation?: string } }>(
    "/api/operations/days/:localDate",
    async (request, reply) => {
      try {
        return await privacy.deleteDay(
          request.params.localDate,
          request.body?.confirmation ?? "",
        );
      } catch (error) {
        if (
          error instanceof PrivacyConfirmationError ||
          (error instanceof Error && error.message.includes("Date"))
        ) {
          return failure(reply, 400, "confirmation", error.message);
        }
        throw error;
      }
    },
  );
  app.delete<{ Body: { confirmation?: string } }>(
    "/api/operations/data",
    async (request, reply) => {
      try {
        return await privacy.deleteAll(request.body?.confirmation ?? "");
      } catch (error) {
        if (error instanceof PrivacyConfirmationError) {
          return failure(reply, 400, "confirmation", error.message);
        }
        throw error;
      }
    },
  );
}

