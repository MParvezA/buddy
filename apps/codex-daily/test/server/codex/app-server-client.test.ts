// @vitest-environment node
import { spawn } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { AppServerClient } from "../../../src/server/codex/app-server-client.js";
import { decodeEnvelope } from "../../../src/server/codex/app-server-protocol.js";

const fixture = path.resolve(
  path.dirname(fileURLToPath(import.meta.url)),
  "../../fixtures/fake-codex-app-server.py",
);

describe("AppServerClient", () => {
  it("initializes before read requests, correlates JSONL responses, and stops its child", async () => {
    const invocations: Array<{ executable: string; args: readonly string[] }> = [];
    const client = new AppServerClient({
      executable: fixture,
      args: ["app-server", "--stdio"],
      processFactory: (executable, args) => {
        invocations.push({ executable, args });
        return spawn(executable, [...args], {
          shell: false,
          stdio: ["pipe", "pipe", "pipe"],
        });
      },
      requestTimeoutMs: 2_000,
    });

    await client.start();
    const page = await client.request("thread/list", {
      sourceKinds: ["cli", "vscode", "appServer"],
      archived: false,
    });
    expect(page).toMatchObject({ nextCursor: "page-two" });
    expect(invocations).toEqual([{ executable: fixture, args: ["app-server", "--stdio"] }]);
    await client.stop();
  });

  it("rejects malformed protocol lines without copying their content into an error", () => {
    expect(() => decodeEnvelope("{not-json")).toThrow("invalid JSONL");
    expect(() => decodeEnvelope(JSON.stringify({ arbitrary: "SECRET" }))).toThrow(
      "malformed envelope",
    );
  });

  it("detaches an aborted request and ignores its late response ID", async () => {
    const client = new AppServerClient({
      executable: fixture,
      args: ["app-server", "--stdio"],
      requestTimeoutMs: 2_000,
    });
    await client.start();
    const controller = new AbortController();
    const request = client.requestInternal(
      "thread/start",
      {
        model: "gpt-5.6-sol",
        ephemeral: true,
      },
      controller.signal,
    );
    controller.abort();
    await expect(request).rejects.toThrow("unavailable");
    await new Promise((resolve) => setTimeout(resolve, 70));
    await expect(
      client.request("thread/list", {
        sourceKinds: ["cli"],
        archived: false,
      }),
    ).resolves.toMatchObject({ nextCursor: "page-two" });
    await client.stop();
  });
});
