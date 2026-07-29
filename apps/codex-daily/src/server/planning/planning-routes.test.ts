// @vitest-environment node
import type { FastifyInstance } from "fastify";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { PlanningView } from "../../shared/planning.js";
import { buildApp } from "../app.js";

let app: FastifyInstance;

beforeEach(async () => {
  app = await buildApp({
    serveStatic: false,
    databasePath: ":memory:",
    clock: () => new Date("2026-07-29T12:00:00.000Z"),
  });
});

afterEach(async () => {
  await app.close();
});

describe("planning routes", () => {
  it("persists the typed create, update, order, confirm, and reopen flow", async () => {
    const first = await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-29/tasks",
      payload: { title: "First" },
    });
    expect(first.statusCode).toBe(200);
    const firstTask = first.json<PlanningView>().tasks[0];
    const second = await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-29/tasks",
      payload: { title: "Second", clarification: "Details" },
    });
    const secondTask = second.json<PlanningView>().tasks[1];

    expect(
      (
        await app.inject({
          method: "PUT",
          url: "/api/planning/2026-07-29/tasks/order",
          payload: { taskIds: [secondTask.id, firstTask.id] },
        })
      )
        .json<PlanningView>()
        .tasks.map((task) => task.title),
    ).toEqual(["Second", "First"]);

    const updated = await app.inject({
      method: "PATCH",
      url: `/api/planning/2026-07-29/tasks/${firstTask.id}`,
      payload: { title: "First edited", clarification: "Done means tested" },
    });
    expect(updated.json<PlanningView>().tasks[1]).toMatchObject({
      title: "First edited",
      clarification: "Done means tested",
      lifecycle: "open",
    });

    const confirmed = await app.inject({
      method: "POST",
      url: `/api/planning/2026-07-29/tasks/${firstTask.id}/lifecycle`,
      payload: { action: "confirm" },
    });
    expect(
      confirmed.json<PlanningView>().tasks.find((task) => task.id === firstTask.id)?.lifecycle,
    ).toBe("confirmed_complete");
    const reopened = await app.inject({
      method: "POST",
      url: `/api/planning/2026-07-29/tasks/${firstTask.id}/lifecycle`,
      payload: { action: "reopen" },
    });
    expect(
      reopened.json<PlanningView>().tasks.find((task) => task.id === firstTask.id)?.lifecycle,
    ).toBe("open");
  });

  it("returns explainable validation, not-found, and conflict envelopes", async () => {
    const malformed = await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-29/tasks",
    });
    expect(malformed.statusCode).toBe(400);
    expect(malformed.json()).toMatchObject({ error: { code: "validation" } });

    const invalid = await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-29/tasks",
      payload: { title: " " },
    });
    expect(invalid.statusCode).toBe(400);
    expect(invalid.json()).toEqual({
      error: { code: "validation", message: "Outcome cannot be blank." },
    });

    const missing = await app.inject({
      method: "PATCH",
      url: "/api/planning/2026-07-29/tasks/missing",
      payload: { title: "Still missing" },
    });
    expect(missing.statusCode).toBe(404);
    expect(missing.json()).toMatchObject({ error: { code: "not_found" } });

    await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-28/tasks",
      payload: { title: "Prior work" },
    });
    const gated = await app.inject({
      method: "POST",
      url: "/api/planning/2026-07-29/tasks",
      payload: { title: "Bypass review" },
    });
    expect(gated.statusCode).toBe(409);
    expect(gated.json()).toMatchObject({ error: { code: "conflict" } });
  });
});
