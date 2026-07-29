export type TaskLifecycle = "open" | "confirmed_complete" | "closed";
export type ReviewAction = "carry_forward" | "reschedule" | "close";

export interface PlanningTask {
  id: string;
  localDate: string;
  title: string;
  clarification: string | null;
  position: number;
  lifecycle: TaskLifecycle;
  originTaskId: string | null;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
  closedAt: string | null;
}

export interface PlanningView {
  localDate: string;
  timezone: string;
  reviewRequired: boolean;
  tasks: PlanningTask[];
  priorDay: {
    localDate: string;
    unresolvedTasks: PlanningTask[];
  };
}

export interface CreateTaskRequest {
  title: string;
  clarification?: string | null;
}

export interface UpdateTaskRequest {
  title: string;
  clarification?: string | null;
}

export interface ReorderTasksRequest {
  taskIds: string[];
}

export interface TaskLifecycleRequest {
  action: "confirm" | "reopen";
}

export interface ReviewDecisionRequest {
  action: ReviewAction;
  rescheduleDate?: string;
}

export type PlanningErrorCode = "validation" | "conflict" | "not_found" | "persistence";

export interface PlanningErrorResponse {
  error: {
    code: PlanningErrorCode;
    message: string;
  };
}
