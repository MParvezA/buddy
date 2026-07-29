import type { FastifyInstance, FastifyReply } from "fastify";
import type { AttentionSnapshot } from "../../shared/attention.js";
import { AttentionService } from "./attention-service.js";

interface AttentionParams {
  attentionId: string;
}

function validId(value: string): boolean {
  return (
    value.length > 0 &&
    value.length <= 600 &&
    ![...value].some((character) => character.charCodeAt(0) <= 31)
  );
}

function invalid(reply: FastifyReply) {
  return reply.code(400).send({
    error: { code: "validation", message: "The attention item ID is invalid." },
  });
}

function mutate(
  reply: FastifyReply,
  service: AttentionService,
  id: string,
  action: "acknowledge" | "dismiss",
) {
  if (!validId(id)) return invalid(reply);
  const result =
    action === "acknowledge"
      ? service.acknowledge(id)
      : service.dismiss(id);
  if (result === "not_found") {
    return reply.code(404).send({
      error: { code: "not_found", message: "The attention item was not found." },
    });
  }
  if (result === "not_actionable") {
    return reply.code(409).send({
      error: {
        code: "not_actionable",
        message: "The attention item is no longer open.",
      },
    });
  }
  return service.snapshot();
}

export async function registerAttentionRoutes(
  app: FastifyInstance,
  service: AttentionService,
  keepaliveMs = 15_000,
): Promise<void> {
  app.get("/api/attention", async () => service.snapshot());

  app.get<{ Params: { threadId: string } }>(
    "/api/attention/threads/:threadId",
    async (request, reply) => {
      if (!validId(request.params.threadId)) return invalid(reply);
      return service.threadHistory(request.params.threadId);
    },
  );

  app.get("/api/attention/events", async (request, reply) => {
    reply.hijack();
    reply.raw.writeHead(200, {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    });
    const send = (event: { id: string; snapshot: AttentionSnapshot }) => {
      if (reply.raw.destroyed) return;
      reply.raw.write(
        `id: ${event.id}\nevent: attention\ndata: ${JSON.stringify(event.snapshot)}\n\n`,
      );
    };
    send(service.nextEvent());
    const keepalive = setInterval(() => {
      if (!reply.raw.destroyed) reply.raw.write(": keepalive\n\n");
    }, keepaliveMs);
    service.on("snapshot", send);
    request.raw.once("close", () => {
      clearInterval(keepalive);
      service.off("snapshot", send);
    });
  });

  app.post<{ Params: AttentionParams }>(
    "/api/attention/:attentionId/acknowledge",
    async (request, reply) =>
      mutate(reply, service, request.params.attentionId, "acknowledge"),
  );

  app.post<{ Params: AttentionParams }>(
    "/api/attention/:attentionId/dismiss",
    async (request, reply) =>
      mutate(reply, service, request.params.attentionId, "dismiss"),
  );
}
