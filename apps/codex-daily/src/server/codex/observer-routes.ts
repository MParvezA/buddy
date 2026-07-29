import type { FastifyInstance, FastifyReply } from "fastify";
import type { ObserverSseEvent } from "../../shared/observer-types.js";
import {
  ObserverNotFoundError,
  ObserverService,
  ObserverUnavailableError,
} from "./observer-service.js";

interface ThreadParams {
  threadId: string;
}

interface LinkParams extends ThreadParams {
  taskId: string;
}

function validId(value: string): boolean {
  return value.length > 0 && value.length <= 200 && /^[A-Za-z0-9._:-]+$/.test(value);
}

function invalid(reply: FastifyReply) {
  return reply.code(400).send({
    error: { code: "validation", message: "The task or thread ID is invalid." },
  });
}

function missing(reply: FastifyReply, message: string) {
  return reply.code(404).send({ error: { code: "not_found", message } });
}

export async function registerObserverRoutes(
  app: FastifyInstance,
  observer: ObserverService,
  keepaliveMs = 15_000,
): Promise<void> {
  app.get("/api/observer", async () => observer.snapshot());

  app.get("/api/observer/events", async (request, reply) => {
    reply.hijack();
    reply.raw.writeHead(200, {
      "content-type": "text/event-stream; charset=utf-8",
      "cache-control": "no-cache, no-transform",
      connection: "keep-alive",
      "x-accel-buffering": "no",
    });

    const send = (event: ObserverSseEvent) => {
      if (reply.raw.destroyed) return;
      reply.raw.write(`id: ${event.id}\nevent: observer\ndata: ${JSON.stringify(event.snapshot)}\n\n`);
    };
    send(observer.nextEvent());
    const keepalive = setInterval(() => {
      if (!reply.raw.destroyed) reply.raw.write(": keepalive\n\n");
    }, keepaliveMs);
    observer.on("snapshot", send);
    request.raw.once("close", () => {
      clearInterval(keepalive);
      observer.off("snapshot", send);
    });
  });

  app.get<{ Params: ThreadParams }>(
    "/api/observer/threads/:threadId",
    async (request, reply) => {
      reply.header("cache-control", "no-store");
      if (!validId(request.params.threadId)) return invalid(reply);
      try {
        return await observer.detail(request.params.threadId);
      } catch (error) {
        if (error instanceof ObserverNotFoundError) return missing(reply, error.message);
        if (error instanceof ObserverUnavailableError) {
          return reply.code(503).send({
            error: { code: "unavailable", message: error.message },
          });
        }
        request.log.error(error);
        return reply.code(503).send({
          error: {
            code: "unavailable",
            message: "Transient Codex thread detail could not be read.",
          },
        });
      }
    },
  );

  app.put<{ Params: LinkParams }>(
    "/api/tasks/:taskId/threads/:threadId",
    async (request, reply) => {
      const { taskId, threadId } = request.params;
      if (!validId(taskId) || !validId(threadId)) return invalid(reply);
      const result = observer.link(taskId, threadId);
      if (result === "missing_task") return missing(reply, "The outcome was not found.");
      if (result === "missing_thread") return missing(reply, "The observed thread was not found.");
      return observer.snapshot();
    },
  );

  app.delete<{ Params: LinkParams }>(
    "/api/tasks/:taskId/threads/:threadId",
    async (request, reply) => {
      const { taskId, threadId } = request.params;
      if (!validId(taskId) || !validId(threadId)) return invalid(reply);
      const result = observer.unlink(taskId, threadId);
      if (result === "missing_task") return missing(reply, "The outcome was not found.");
      if (result === "missing_thread") return missing(reply, "The observed thread was not found.");
      return observer.snapshot();
    },
  );
}
