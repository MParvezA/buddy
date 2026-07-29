import type {
  CreateTaskRequest,
  PlanningErrorResponse,
  PlanningView,
  ReorderTasksRequest,
  ReviewDecisionRequest,
  TaskLifecycleRequest,
  UpdateTaskRequest,
} from "../../shared/planning";

export class PlanningRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: { accept: "application/json", "content-type": "application/json", ...init?.headers },
  });
  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as PlanningErrorResponse | null;
    throw new PlanningRequestError(
      body?.error.message ?? `Planning request failed (${response.status}).`,
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

function datePath(localDate: string): string {
  return `/api/planning/${encodeURIComponent(localDate)}`;
}

export function getPlanning(): Promise<PlanningView> {
  return request("/api/planning");
}

export function createTask(localDate: string, body: CreateTaskRequest): Promise<PlanningView> {
  return request(`${datePath(localDate)}/tasks`, { method: "POST", body: JSON.stringify(body) });
}

export function updateTask(
  localDate: string,
  taskId: string,
  body: UpdateTaskRequest,
): Promise<PlanningView> {
  return request(`${datePath(localDate)}/tasks/${encodeURIComponent(taskId)}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function reorderTasks(
  localDate: string,
  body: ReorderTasksRequest,
): Promise<PlanningView> {
  return request(`${datePath(localDate)}/tasks/order`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export function transitionTask(
  localDate: string,
  taskId: string,
  body: TaskLifecycleRequest,
): Promise<PlanningView> {
  return request(`${datePath(localDate)}/tasks/${encodeURIComponent(taskId)}/lifecycle`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function decideReview(
  localDate: string,
  taskId: string,
  body: ReviewDecisionRequest,
): Promise<PlanningView> {
  return request(`${datePath(localDate)}/review/${encodeURIComponent(taskId)}`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
