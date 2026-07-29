import type {
  CreateTaskRequest,
  PlanningTask,
  PlanningView,
  ReorderTasksRequest,
  ReviewDecisionRequest,
  TaskLifecycleRequest,
  UpdateTaskRequest,
} from "../../shared/planning.js";
import { PlanningRepository } from "../storage/planning-repository.js";
import { assertLocalDate, localDateFor, priorLocalDate } from "./local-date.js";
import { PlanningError } from "./planning-errors.js";

const MAX_TITLE = 240;
const MAX_CLARIFICATION = 2_000;

export interface PlanningServiceOptions {
  repository: PlanningRepository;
  clock?: () => Date;
  timezone?: string;
}

function text(value: unknown, label: string, max: number, required: boolean): string | null {
  if (value == null && !required) return null;
  if (typeof value !== "string") {
    throw new PlanningError("validation", `${label} must be text.`);
  }
  const trimmed = value.trim();
  if (required && !trimmed) throw new PlanningError("validation", `${label} cannot be blank.`);
  if (trimmed.length > max) {
    throw new PlanningError("validation", `${label} must be ${max} characters or fewer.`);
  }
  return trimmed || null;
}

function sameIds(left: string[], right: string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

export class PlanningService {
  private readonly repository: PlanningRepository;
  private readonly clock: () => Date;
  readonly timezone: string;

  constructor(options: PlanningServiceOptions) {
    this.repository = options.repository;
    this.clock = options.clock ?? (() => new Date());
    this.timezone = options.timezone ?? "Europe/Berlin";
  }

  today(): string {
    return localDateFor(this.clock, this.timezone);
  }

  now(): string {
    return this.clock().toISOString();
  }

  view(requestedDate?: string): PlanningView {
    const localDate = assertLocalDate(requestedDate ?? this.today());
    const priorDate = priorLocalDate(localDate);
    this.repository.ensureDay(localDate, this.now());
    const unresolvedTasks = this.repository.listUnresolved(priorDate);
    return {
      localDate,
      timezone: this.timezone,
      reviewRequired: unresolvedTasks.length > 0,
      tasks: this.repository.listTasks(localDate),
      priorDay: { localDate: priorDate, unresolvedTasks },
    };
  }

  create(localDateValue: string, request: CreateTaskRequest): PlanningView {
    const localDate = assertLocalDate(localDateValue);
    const title = text(request.title, "Outcome", MAX_TITLE, true)!;
    const clarification = text(
      request.clarification,
      "Clarification",
      MAX_CLARIFICATION,
      false,
    );
    if (this.repository.listUnresolved(priorLocalDate(localDate)).length) {
      throw new PlanningError(
        "conflict",
        "Resolve every unfinished outcome from the previous day before planning this day.",
      );
    }
    this.repository.createTask({
      localDate,
      title,
      clarification,
      position: this.repository.nextPosition(localDate),
      now: this.now(),
    });
    return this.view(localDate);
  }

  update(localDateValue: string, taskId: string, request: UpdateTaskRequest): PlanningView {
    const localDate = assertLocalDate(localDateValue);
    const task = this.taskOnDate(taskId, localDate);
    if (task.lifecycle === "closed") {
      throw new PlanningError("conflict", "A closed outcome cannot be edited.");
    }
    this.repository.updateTask(
      task.id,
      text(request.title, "Outcome", MAX_TITLE, true)!,
      text(request.clarification, "Clarification", MAX_CLARIFICATION, false),
      this.now(),
    );
    return this.view(localDate);
  }

  reorder(localDateValue: string, request: ReorderTasksRequest): PlanningView {
    const localDate = assertLocalDate(localDateValue);
    if (!Array.isArray(request.taskIds) || request.taskIds.some((id) => typeof id !== "string")) {
      throw new PlanningError("validation", "Task order must be a list of task IDs.");
    }
    const current = this.repository.listTasks(localDate).map((task) => task.id);
    const requested = [...request.taskIds];
    if (
      new Set(requested).size !== requested.length ||
      !sameIds([...current].sort(), [...requested].sort())
    ) {
      throw new PlanningError("validation", "Task order must contain every current outcome once.");
    }
    this.repository.transaction(() => this.repository.reorder(requested, this.now()));
    return this.view(localDate);
  }

  transition(
    localDateValue: string,
    taskId: string,
    request: TaskLifecycleRequest,
  ): PlanningView {
    const localDate = assertLocalDate(localDateValue);
    const task = this.taskOnDate(taskId, localDate);
    if (request.action === "confirm") {
      if (task.lifecycle !== "open") {
        throw new PlanningError("conflict", "Only an open outcome can be confirmed.");
      }
      this.repository.updateLifecycle(task.id, "confirmed_complete", this.now());
    } else if (request.action === "reopen") {
      if (task.lifecycle !== "confirmed_complete") {
        throw new PlanningError("conflict", "Only a confirmed outcome can be reopened.");
      }
      this.repository.updateLifecycle(task.id, "open", this.now());
    } else {
      throw new PlanningError("validation", "Completion action must be confirm or reopen.");
    }
    return this.view(localDate);
  }

  decide(
    localDateValue: string,
    sourceTaskId: string,
    request: ReviewDecisionRequest,
  ): PlanningView {
    const localDate = assertLocalDate(localDateValue);
    if (!["carry_forward", "reschedule", "close"].includes(request.action)) {
      throw new PlanningError(
        "validation",
        "Review action must be carry_forward, reschedule, or close.",
      );
    }
    const target =
      request.action === "carry_forward"
        ? localDate
        : request.action === "reschedule"
          ? assertLocalDate(request.rescheduleDate ?? "")
          : null;
    if (request.action === "reschedule" && target! <= localDate) {
      throw new PlanningError("validation", "Reschedule date must be later than today.");
    }

    const source = this.repository.findTask(sourceTaskId);
    if (!source) throw new PlanningError("not_found", "The prior-day outcome was not found.");
    if (source.localDate !== priorLocalDate(localDate)) {
      throw new PlanningError(
        "validation",
        "Only outcomes from the immediately previous day can be reviewed.",
      );
    }

    const existing = this.repository.findDecision(sourceTaskId);
    if (existing) {
      if (existing.action === request.action && existing.target_local_date === target) {
        return this.view(localDate);
      }
      throw new PlanningError(
        "conflict",
        "This outcome already has a different review decision.",
      );
    }
    if (source.lifecycle !== "open") {
      throw new PlanningError("conflict", "Only an unresolved open outcome can be reviewed.");
    }

    this.repository.transaction(() => {
      let successor: PlanningTask | null = null;
      if (target) {
        successor = this.repository.createTask({
          localDate: target,
          title: source.title,
          clarification: source.clarification,
          position: this.repository.nextPosition(target),
          originTaskId: source.id,
          now: this.now(),
        });
      }
      if (request.action === "close") {
        this.repository.updateLifecycle(source.id, "closed", this.now());
      }
      this.repository.recordDecision({
        sourceTaskId: source.id,
        action: request.action,
        targetLocalDate: target,
        successorTaskId: successor?.id ?? null,
        now: this.now(),
      });
    });
    return this.view(localDate);
  }

  private taskOnDate(id: string, localDate: string): PlanningTask {
    const task = this.repository.findTask(id);
    if (!task || task.localDate !== localDate) {
      throw new PlanningError("not_found", "The outcome was not found for this day.");
    }
    return task;
  }
}
