import type {
  ConsiderTomorrowFact,
  FactualDigest,
  ReportAttentionFact,
  ReportTaskFact,
  ReportUnplannedFact,
} from "../../shared/report.js";

export interface DigestTaskInput extends ReportTaskFact {
  lifecycle: "open" | "confirmed_complete";
  suggestedComplete: boolean;
  blocked: boolean;
  position: number;
}

export interface DigestThreadInput {
  threadId: string;
  title: string | null;
  activityCount: number;
  lastActivityAt: string;
  linked: boolean;
}

export interface FactualDigestInput {
  localDate: string;
  cutoff: string;
  tasks: DigestTaskInput[];
  threads: DigestThreadInput[];
  attention: ReportAttentionFact[];
}

const byTask = (a: DigestTaskInput, b: DigestTaskInput) =>
  a.position - b.position || a.title.localeCompare(b.title) || a.taskId.localeCompare(b.taskId);

function taskFact(task: DigestTaskInput): ReportTaskFact {
  return {
    taskId: task.taskId,
    title: task.title,
    clarification: task.clarification,
    threadIds: [...task.threadIds].sort(),
  };
}

export function buildFactualDigest(input: FactualDigestInput): FactualDigest {
  const tasks = [...input.tasks].sort(byTask);
  const planned = tasks.map(taskFact);
  const confirmedComplete = tasks.filter((task) => task.lifecycle === "confirmed_complete").map(taskFact);
  const suggestedComplete = tasks
    .filter((task) => task.lifecycle === "open" && task.suggestedComplete)
    .map(taskFact);
  const blocked = tasks
    .filter((task) => task.lifecycle === "open" && task.blocked)
    .map(taskFact);
  const pending = tasks
    .filter((task) => task.lifecycle === "open" && !task.blocked)
    .map(taskFact);
  const unplannedWork: ReportUnplannedFact[] = input.threads
    .filter((thread) => !thread.linked && thread.activityCount > 0)
    .sort(
      (a, b) =>
        b.lastActivityAt.localeCompare(a.lastActivityAt) ||
        (a.title ?? "").localeCompare(b.title ?? "") ||
        a.threadId.localeCompare(b.threadId),
    )
    .map((thread) => ({
      threadId: thread.threadId,
      title: thread.title?.trim() || "Untitled Codex work",
      activityCount: thread.activityCount,
      lastActivityAt: thread.lastActivityAt,
    }));
  const outstandingAttention = [...input.attention].sort(
    (a, b) =>
      a.certainty.localeCompare(b.certainty) ||
      b.occurredAt.localeCompare(a.occurredAt) ||
      a.attentionId.localeCompare(b.attentionId),
  );
  const considerTomorrow: ConsiderTomorrowFact[] = [
    ...blocked.map((task) => ({
      kind: "task" as const,
      id: task.taskId,
      label: task.title,
      reason: "blocked" as const,
    })),
    ...pending.map((task) => ({
      kind: "task" as const,
      id: task.taskId,
      label: task.title,
      reason: "pending" as const,
    })),
    ...unplannedWork.map((thread) => ({
      kind: "unplanned_work" as const,
      id: thread.threadId,
      label: thread.title,
      reason: "unplanned" as const,
    })),
  ];

  return {
    localDate: input.localDate,
    cutoff: input.cutoff,
    planned,
    confirmedComplete,
    suggestedComplete,
    pending,
    blocked,
    unplannedWork,
    outstandingAttention,
    considerTomorrow,
  };
}
