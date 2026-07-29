// @vitest-environment node
import { afterEach, describe, expect, it } from "vitest";
import { openDatabase, type PlanningDatabase } from "../storage/database.js";
import { PlanningRepository } from "../storage/planning-repository.js";
import { localDateFor } from "./local-date.js";
import { PlanningError } from "./planning-errors.js";
import { PlanningService } from "./planning-service.js";

let database: PlanningDatabase | undefined;

afterEach(() => {
  database?.close();
  database = undefined;
});

function service(date = "2026-07-29") {
  database?.close();
  database = openDatabase({ path: ":memory:" });
  return new PlanningService({
    repository: new PlanningRepository(database.connection),
    clock: () => new Date(`${date}T12:00:00.000Z`),
  });
}

describe("morning planning service", () => {
  it("creates, edits, reorders, confirms, and reopens without implicit completion", () => {
    const planning = service();
    expect(planning.view()).toMatchObject({ tasks: [], reviewRequired: false });

    let view = planning.create("2026-07-29", {
      title: "First result",
      clarification: "Original note",
    });
    const first = view.tasks[0];
    view = planning.create("2026-07-29", { title: "Second result" });
    const second = view.tasks[1];
    expect(view.tasks.map((task) => task.lifecycle)).toEqual(["open", "open"]);

    view = planning.update("2026-07-29", first.id, {
      title: "First durable result",
      clarification: "Clear success criteria",
    });
    view = planning.reorder("2026-07-29", { taskIds: [second.id, first.id] });
    expect(view.tasks.map((task) => [task.title, task.clarification])).toEqual([
      ["Second result", null],
      ["First durable result", "Clear success criteria"],
    ]);

    view = planning.transition("2026-07-29", first.id, { action: "confirm" });
    expect(view.tasks.find((task) => task.id === first.id)?.lifecycle).toBe(
      "confirmed_complete",
    );
    view = planning.transition("2026-07-29", first.id, { action: "reopen" });
    expect(view.tasks.find((task) => task.id === first.id)?.lifecycle).toBe("open");
  });

  it("gates today until every previous-day task has an explicit decision", () => {
    const planning = service();
    const prior = planning.create("2026-07-28", { title: "Unfinished history" }).tasks[0];
    expect(planning.view("2026-07-29")).toMatchObject({
      reviewRequired: true,
      priorDay: { localDate: "2026-07-28" },
    });
    expect(() => planning.create("2026-07-29", { title: "Bypass" })).toThrowError(
      /Resolve every unfinished/,
    );

    const view = planning.decide("2026-07-29", prior.id, { action: "carry_forward" });
    expect(view.reviewRequired).toBe(false);
    expect(view.tasks).toHaveLength(1);
    expect(view.tasks[0]).toMatchObject({
      title: "Unfinished history",
      lifecycle: "open",
      originTaskId: prior.id,
    });
    expect(planning.view("2026-07-28").tasks[0]).toMatchObject({
      id: prior.id,
      localDate: "2026-07-28",
      title: "Unfinished history",
    });
  });

  it("reschedules only into the future and closes without claiming completion", () => {
    const planning = service();
    const rescheduled = planning.create("2026-07-28", { title: "Later" }).tasks[0];
    expect(() =>
      planning.decide("2026-07-29", rescheduled.id, {
        action: "reschedule",
        rescheduleDate: "2026-07-29",
      }),
    ).toThrowError(/later than today/);
    let view = planning.decide("2026-07-29", rescheduled.id, {
      action: "reschedule",
      rescheduleDate: "2026-08-04",
    });
    expect(view.tasks).toEqual([]);
    expect(planning.view("2026-08-04").tasks[0]).toMatchObject({
      title: "Later",
      originTaskId: rescheduled.id,
      lifecycle: "open",
    });

    const nextPlanning = service("2026-08-06");
    const closed = nextPlanning.create("2026-08-05", { title: "Intentionally stop" }).tasks[0];
    view = nextPlanning.decide("2026-08-06", closed.id, { action: "close" });
    expect(view.tasks).toEqual([]);
    expect(database!.connection.prepare("SELECT lifecycle FROM tasks WHERE id = ?").get(closed.id))
      .toEqual({ lifecycle: "closed" });
    expect(
      database!.connection
        .prepare("SELECT successor_task_id FROM task_review_decisions WHERE source_task_id = ?")
        .get(closed.id),
    ).toEqual({ successor_task_id: null });
  });

  it("makes matching decision retries idempotent and conflicting retries explicit", () => {
    const planning = service();
    const prior = planning.create("2026-07-28", { title: "Retry safely" }).tasks[0];
    const first = planning.decide("2026-07-29", prior.id, { action: "carry_forward" });
    const retry = planning.decide("2026-07-29", prior.id, { action: "carry_forward" });
    expect(retry.tasks.map((task) => task.id)).toEqual(first.tasks.map((task) => task.id));
    expect(() => planning.decide("2026-07-29", prior.id, { action: "close" })).toThrow(
      PlanningError,
    );
    expect(
      database!.connection
        .prepare("SELECT count(*) AS count FROM tasks WHERE origin_task_id = ?")
        .get(prior.id),
    ).toEqual({ count: 1 });
  });

  it("uses the configured timezone across a UTC date boundary", () => {
    expect(
      localDateFor(() => new Date("2026-01-01T23:30:00.000Z"), "Europe/Berlin"),
    ).toBe("2026-01-02");
    expect(
      localDateFor(() => new Date("2026-01-01T23:30:00.000Z"), "America/New_York"),
    ).toBe("2026-01-01");
  });

  it("validates text, task identity, order, and lifecycle transitions", () => {
    const planning = service();
    expect(() => planning.create("2026-07-29", { title: "   " })).toThrowError(
      /cannot be blank/,
    );
    const task = planning.create("2026-07-29", { title: "Valid" }).tasks[0];
    expect(() => planning.reorder("2026-07-29", { taskIds: [] })).toThrowError(
      /every current outcome/,
    );
    expect(() => planning.transition("2026-07-29", task.id, { action: "reopen" })).toThrowError(
      /confirmed outcome/,
    );
    expect(() =>
      planning.update("2026-07-30", task.id, { title: "Wrong day" }),
    ).toThrowError(/not found/);
  });
});
