import { expect, test } from "@playwright/test";

test("observer discovers paginated chats, links a task, and reads detail transiently", async ({
  page,
}, testInfo) => {
  test.skip(testInfo.project.name !== "desktop", "Exercise the mutable local link once.");
  await page.goto("/");

  await expect(page.getByText("Codex connected", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Observed chat" }).first()).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Second observed chat", exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText("Turn completed")).toBeVisible();
  await expect(page.getByText("Unplanned work").first()).toBeVisible();

  await page.locator("#new-outcome").fill("Connect daily work");
  await page.getByRole("button", { name: "Add outcome" }).click();
  const card = page.locator(".work-card").filter({
    has: page.getByRole("heading", { name: "Observed chat", exact: true }),
  });
  await card.getByRole("combobox").selectOption({ label: "Connect daily work" });
  await card.getByRole("button", { name: "Link" }).click();
  await expect(card.getByText("Connect daily work")).toBeVisible();
  await expect(card.getByText("Unplanned work")).toHaveCount(0);

  await card.getByRole("link", { name: "Observed chat" }).click();
  await expect(page.getByText("1 turns fetched in request memory")).toBeVisible();
  const observerResponse = await page.request.get("/api/observer");
  expect(await observerResponse.text()).not.toMatch(/SECRET RESPONSE|SECRET PREVIEW|turns/);

  const briefsResponse = await page.request.get("/api/session-briefs");
  expect(briefsResponse.ok()).toBe(true);
  expect(briefsResponse.headers()["cache-control"]).toBe("no-store");
  const briefsBody = await briefsResponse.text();
  expect(JSON.parse(briefsBody)).toMatchObject({
    total: 2,
    queued: 2,
    items: [
      expect.objectContaining({ analysisStatus: "queued", lastGood: null }),
      expect.objectContaining({ analysisStatus: "queued", lastGood: null }),
    ],
  });
  expect(briefsBody).not.toContain("deterministic_placeholder");
  expect(briefsBody).not.toMatch(
    /SECRET RESPONSE|SECRET PREVIEW|rawProtocol|prompt|reasoning|turns/,
  );

  const liveBrief = await page.evaluate(
    () =>
      new Promise<string>((resolve, reject) => {
        const events = new EventSource("/api/session-briefs/events");
        const timer = window.setTimeout(() => {
          events.close();
          reject(new Error("Session brief SSE did not publish."));
        }, 5_000);
        events.addEventListener("session-briefs", (event) => {
          window.clearTimeout(timer);
          events.close();
          resolve((event as MessageEvent<string>).data);
        });
      }),
  );
  expect(JSON.parse(liveBrief)).toMatchObject({
    total: 2,
    queued: 2,
  });
  expect(liveBrief).not.toContain("deterministic_placeholder");
  expect(liveBrief).not.toMatch(/SECRET RESPONSE|SECRET PREVIEW|prompt|reasoning|turns/);
});
