// @vitest-environment node
import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

const scriptPath = path.resolve("scripts/prove-session-brief-host.mjs");

describe("session brief installed-host proof boundary", () => {
  it("is opt-in, content-safe, and cannot enumerate or read local history", () => {
    const source = readFileSync(scriptPath, "utf8");
    expect(source).toContain('requestInternal("thread/start"');
    expect(source).toContain('requestInternal("turn/start"');
    expect(source).not.toMatch(/request(?:Internal)?\("thread\/(?:list|read)"/);
    expect(source).toContain('model: MODEL');
    expect(source).toContain('effort: EFFORT');
    expect(source).toContain("allowProviderModelFallback: false");
    expect(source).toContain("ephemeral: true");
    expect(source).toContain("dynamicTools: []");
    expect(source).toContain("runtimeWorkspaceRoots: []");
    expect(source).toContain("outputSchema: sessionBriefOutputSchema(evidence)");
    expect(source).not.toMatch(/console\.(?:log|error)/);

    const optInGuard = source.indexOf(
      'process.env.CODEX_DAILY_RUN_HOST_MODEL_PROOF !== "1"',
    );
    const productionImport = source.indexOf(
      'await import("../dist/server/server/codex/app-server-client.js")',
    );
    expect(optInGuard).toBeGreaterThan(0);
    expect(productionImport).toBeGreaterThan(optInGuard);
    expect(source).toContain(
      'fixedSummary("blocked", "opt_in_required", 0)',
    );
    expect(source).toContain('"synthetic_only=true"');
    expect(source).toContain('"history_read=false"');
    expect(source).toContain('"request_rejected"');
    expect(source).toContain('return "model_contract_failed"');
    expect(source).toContain('return "host_unavailable"');
    expect(source).not.toContain('"contract_failed"');
  });
});
