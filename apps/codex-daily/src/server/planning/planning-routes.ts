import type { FastifyInstance, FastifyReply } from "fastify";
import type {
  CreateTaskRequest,
  ReorderTasksRequest,
  ReviewDecisionRequest,
  TaskLifecycleRequest,
  UpdateTaskRequest,
} from "../../shared/planning.js";
import { PlanningError } from "./planning-errors.js";
import type { PlanningService } from "./planning-service.js";

interface DateParams {
  date: string;
}

interface TaskParams extends DateParams {
  taskId: string;
}

function failure(reply: FastifyReply, error: unknown) {
  if (error instanceof PlanningError) {
    const status = error.code === "not_found" ? 404 : error.code === "conflict" ? 409 : 400;
    return reply.code(status).send({ error: { code: error.code, message: error.message } });
  }
  reply.log.error(error);
  return reply
    .code(500)
    .send({ error: { code: "persistence", message: "Local planning data could not be saved." } });
}

export async function registerPlanningRoutes(
  app: FastifyInstance,
  service: PlanningService,
): Promise<void> {
  app.get<{ Querystring: { date?: string } }>("/api/planning", async (request, reply) => {
    try {
      return service.view(request.query.date);
    } catch (error) {
      return failure(reply, error);
    }
  });

  app.post<{ Params: DateParams; Body: CreateTaskRequest }>(
    "/api/planning/:date/tasks",
    async (request, reply) => {
      try {
        return service.create(request.params.date, request.body ?? ({} as CreateTaskRequest));
      } catch (error) {
        return failure(reply, error);
      }
    },
  );

  app.patch<{ Params: TaskParams; Body: UpdateTaskRequest }>(
    "/api/planning/:date/tasks/:taskId",
    async (request, reply) => {
      try {
        return service.update(
          request.params.date,
          request.params.taskId,
          request.body ?? ({} as UpdateTaskRequest),
        );
      } catch (error) {
        return failure(reply, error);
      }
    },
  );

  app.put<{ Params: DateParams; Body: ReorderTasksRequest }>(
    "/api/planning/:date/tasks/order",
    async (request, reply) => {
      try {
        return service.reorder(
          request.params.date,
          request.body ?? ({} as ReorderTasksRequest),
        );
      } catch (error) {
        return failure(reply, error);
      }
    },
  );

  app.post<{ Params: TaskParams; Body: TaskLifecycleRequest }>(
    "/api/planning/:date/tasks/:taskId/lifecycle",
    async (request, reply) => {
      try {
        return service.transition(
          request.params.date,
          request.params.taskId,
          request.body ?? ({} as TaskLifecycleRequest),
        );
      } catch (error) {
        return failure(reply, error);
      }
    },
  );

  app.post<{ Params: TaskParams; Body: ReviewDecisionRequest }>(
    "/api/planning/:date/review/:taskId",
    async (request, reply) => {
      try {
        return service.decide(
          request.params.date,
          request.params.taskId,
          request.body ?? ({} as ReviewDecisionRequest),
        );
      } catch (error) {
        return failure(reply, error);
      }
    },
  );
}
