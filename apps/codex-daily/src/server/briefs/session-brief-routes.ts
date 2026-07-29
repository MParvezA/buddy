import type { FastifyInstance, FastifyReply } from "fastify";
import type { SessionBriefSseEvent } from "../../shared/session-briefs.js";
import {
  SessionBriefNotFoundError,
  SessionBriefNotSelectedError,
  SessionBriefObserverUnavailableError,
  SessionBriefService,
} from "./session-brief-service.js";

function validId(value: string): boolean {
  return value.length > 0 && value.length <= 200 && /^[A-Za-z0-9._:-]+$/.test(value);
}

function error(
  reply: FastifyReply,
  status: number,
  code: string,
  message: string,
) {
  return reply.code(status).send({ error: { code, message } });
}

function refreshFailure(reply: FastifyReply, reason: unknown) {
  if (reason instanceof SessionBriefNotFoundError) {
    return error(reply, 404, "not_found", reason.message);
  }
  if (reason instanceof SessionBriefNotSelectedError) {
    return error(reply, 409, "not_selected", reason.message);
  }
  if (reason instanceof SessionBriefObserverUnavailableError) {
    return error(reply, 503, "observer_unavailable", reason.message);
  }
  throw reason;
}

export async function registerSessionBriefRoutes(
  app: FastifyInstance,
  briefs: SessionBriefService,
  keepaliveMs = 15_000,
): Promise<void> {
  app.get("/api/session-briefs", async (_request, reply) =>
    reply.header("cache-control", "no-store").send(briefs.snapshot()),
  );

  app.get("/api/session-briefs/events", async (request, reply) => {
    reply.hijack();
    reply.raw.writeHead(200, {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-store, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    });
    const send = (event: SessionBriefSseEvent) => {
      if (reply.raw.destroyed) return;
      reply.raw.write(
        `id: ${event.id}\nevent: session-briefs\ndata: ${JSON.stringify(event.snapshot)}\n\n`,
      );
    };
    send(briefs.nextEvent());
    const keepalive = setInterval(() => {
      if (!reply.raw.destroyed) reply.raw.write(": keepalive\n\n");
    }, keepaliveMs);
    briefs.on("snapshot", send);
    request.raw.once("close", () => {
      clearInterval(keepalive);
      briefs.off("snapshot", send);
    });
  });

  app.post("/api/session-briefs/refresh", async (_request, reply) => {
    reply.header("cache-control", "no-store");
    try {
      return reply.code(202).send(briefs.refreshAll());
    } catch (reason) {
      return refreshFailure(reply, reason);
    }
  });

  app.post<{ Params: { threadId: string } }>(
    "/api/session-briefs/:threadId/refresh",
    async (request, reply) => {
      reply.header("cache-control", "no-store");
      if (!validId(request.params.threadId)) {
        return error(reply, 400, "validation", "The thread ID is invalid.");
      }
      try {
        return reply.code(202).send(briefs.refresh(request.params.threadId));
      } catch (reason) {
        return refreshFailure(reply, reason);
      }
    },
  );
}
