import type {
  AttentionCertainty,
  AttentionKind,
} from "../../shared/attention.js";
import type {
  ObservedActivity,
  ObserverSnapshot,
} from "../../shared/observer-types.js";
import {
  AttentionRepository,
  type AttentionCandidate,
} from "./attention-repository.js";

export const STALE_AFTER_MS = 30 * 60 * 1_000;

interface Mapping {
  kind: AttentionKind;
  certainty: AttentionCertainty;
  label: string;
}

function mappingFor(activity: ObservedActivity): Mapping | null {
  if (activity.category === "approval" && activity.lifecycle === "pending") {
    return {
      kind: "approval",
      certainty: "explicit",
      label: activity.label,
    };
  }
  if (activity.category === "input_request" && activity.lifecycle === "pending") {
    return {
      kind: "direct_question",
      certainty: "explicit",
      label: activity.label,
    };
  }
  if (activity.category === "turn" && activity.lifecycle === "failed") {
    return {
      kind: "failed_turn",
      certainty: "explicit",
      label: "Turn failed",
    };
  }
  if (activity.category === "turn" && activity.lifecycle === "interrupted") {
    return {
      kind: "interrupted_turn",
      certainty: "explicit",
      label: "Turn interrupted",
    };
  }
  if (activity.category === "goal" && activity.lifecycle === "blocked") {
    return {
      kind: "explicit_blocker",
      certainty: "explicit",
      label: "Explicit blocker",
    };
  }
  return null;
}

function candidate(
  activity: ObservedActivity,
  mapping: Mapping,
): AttentionCandidate {
  return {
    sourceKey: activity.sourceKey,
    threadId: activity.threadId,
    turnId: activity.turnId,
    itemId: activity.itemId,
    kind: mapping.kind,
    certainty: mapping.certainty,
    sourceOccurredAt: activity.occurredAt,
    sourceLabel: mapping.label,
  };
}

function pendingRequestKey(activity: ObservedActivity): string | null {
  const suffix = ":resolved";
  if (!activity.sourceKey.startsWith("request:") || !activity.sourceKey.endsWith(suffix)) {
    return null;
  }
  return `${activity.sourceKey.slice(0, -suffix.length)}:pending`;
}

export class AttentionEngine {
  constructor(
    private readonly repository: AttentionRepository,
    private readonly clock: () => Date = () => new Date(),
  ) {}

  reconcile(snapshot: ObserverSnapshot): void {
    // Disconnected/reconnecting observations are explicitly last-known. Reuse
    // the persisted queue until a connected snapshot can authoritatively derive
    // or resolve attention.
    if (snapshot.health.state !== "connected") return;

    const now = this.clock();
    const nowIso = now.toISOString();
    const activities = [...snapshot.activities].sort(
      (left, right) =>
        left.occurredAt.localeCompare(right.occurredAt) ||
        left.sourceKey.localeCompare(right.sourceKey),
    );

    for (const activity of activities) {
      if (
        activity.category === "input_request" &&
        activity.lifecycle === "resolved"
      ) {
        const sourceKey = pendingRequestKey(activity);
        if (sourceKey) this.repository.sourceResolve(sourceKey, nowIso);
        continue;
      }

      if (
        activity.category === "goal" &&
        activity.lifecycle !== "blocked"
      ) {
        this.repository.sourceResolveKindForThread(
          activity.threadId,
          "explicit_blocker",
          activity.occurredAt,
        );
        continue;
      }

      const mapping = mappingFor(activity);
      if (!mapping) continue;
      if (
        (mapping.kind === "approval" || mapping.kind === "direct_question") &&
        snapshot.health.capability !== "shared_live"
      ) {
        continue;
      }
      this.repository.upsert(candidate(activity, mapping), nowIso);
    }

    this.reconcileStaleness(snapshot, now);
  }

  private reconcileStaleness(snapshot: ObserverSnapshot, now: Date): void {
    const nowIso = now.toISOString();
    for (const thread of snapshot.threads) {
      if (
        thread.archived ||
        thread.runtime !== "active" ||
        !thread.lastActivityAt
      ) {
        this.repository.sourceResolveKindForThread(
          thread.id,
          "possibly_stale",
          nowIso,
        );
        continue;
      }

      const sourceKey = `stale:${thread.id}:${thread.lastActivityAt}`;
      this.repository.sourceResolveKindForThread(
        thread.id,
        "possibly_stale",
        nowIso,
        sourceKey,
      );
      const quietForMs = now.getTime() - new Date(thread.lastActivityAt).getTime();
      if (quietForMs < STALE_AFTER_MS) continue;
      this.repository.upsert(
        {
          sourceKey,
          threadId: thread.id,
          turnId: null,
          itemId: null,
          kind: "possibly_stale",
          certainty: "possible",
          sourceOccurredAt: thread.lastActivityAt,
          sourceLabel: "Possibly stale · lower certainty",
        },
        nowIso,
      );
    }
  }
}
