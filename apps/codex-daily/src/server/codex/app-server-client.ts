import { spawn, type ChildProcessWithoutNullStreams } from "node:child_process";
import { EventEmitter } from "node:events";
import {
  decodeEnvelope,
  type ProtocolMethodEnvelope,
  type ProtocolResponse,
} from "./app-server-protocol.js";

export type ProcessFactory = (
  executable: string,
  args: readonly string[],
) => ChildProcessWithoutNullStreams;

export interface AppServerClientOptions {
  executable: string;
  args: readonly string[];
  processFactory?: ProcessFactory;
  requestTimeoutMs?: number;
  setTimer?: typeof setTimeout;
  clearTimer?: typeof clearTimeout;
}

interface PendingCall {
  resolve: (value: unknown) => void;
  reject: (error: Error) => void;
  timer: ReturnType<typeof setTimeout>;
}

const defaultProcessFactory: ProcessFactory = (executable, args) =>
  spawn(executable, [...args], {
    shell: false,
    stdio: ["pipe", "pipe", "pipe"],
  });

export class AppServerClient extends EventEmitter {
  private child: ChildProcessWithoutNullStreams | null = null;
  private stdoutBuffer = "";
  private nextRequestId = 1;
  private readonly pending = new Map<string | number, PendingCall>();
  private initialized = false;
  private stopping = false;
  private stderrDiagnostic = "";
  private readonly processFactory: ProcessFactory;
  private readonly requestTimeoutMs: number;
  private readonly setTimer: typeof setTimeout;
  private readonly clearTimer: typeof clearTimeout;

  constructor(private readonly options: AppServerClientOptions) {
    super();
    this.processFactory = options.processFactory ?? defaultProcessFactory;
    this.requestTimeoutMs = options.requestTimeoutMs ?? 8_000;
    this.setTimer = options.setTimer ?? setTimeout;
    this.clearTimer = options.clearTimer ?? clearTimeout;
  }

  async start(): Promise<void> {
    if (this.child) throw new Error("Codex App Server client is already running.");
    this.stopping = false;
    this.initialized = false;
    this.stderrDiagnostic = "";
    const child = this.processFactory(this.options.executable, this.options.args);
    this.child = child;

    child.stdout.setEncoding("utf8");
    child.stdout.on("data", (chunk: string) => this.onStdout(chunk));
    child.stderr.setEncoding("utf8");
    child.stderr.on("data", (chunk: string) => {
      this.stderrDiagnostic = `${this.stderrDiagnostic}${chunk}`.slice(-2_000);
    });
    child.on("error", (error) => this.fail(error));
    child.on("exit", (code, signal) => {
      const suffix = this.stderrDiagnostic.trim() ? " See the local service diagnostic." : "";
      const error = new Error(
        `Codex App Server exited (${signal ?? `code ${String(code)}`}).${suffix}`,
      );
      this.child = null;
      this.initialized = false;
      this.rejectPending(error);
      if (!this.stopping) this.emit("disconnect", error);
    });

    await this.requestRaw("initialize", {
      clientInfo: {
        name: "codex-daily",
        title: "Codex Daily",
        version: "0.1.0",
      },
      capabilities: {
        experimentalApi: false,
        requestAttestation: false,
      },
    });
    this.sendEnvelope({ method: "initialized" });
    this.initialized = true;
  }

  request(method: "thread/list" | "thread/read", params: unknown): Promise<unknown> {
    if (!this.initialized) {
      return Promise.reject(new Error("Codex App Server is not initialized."));
    }
    return this.requestRaw(method, params);
  }

  async stop(): Promise<void> {
    this.stopping = true;
    this.initialized = false;
    const child = this.child;
    this.child = null;
    this.rejectPending(new Error("Codex App Server client stopped."));
    if (!child || child.exitCode !== null || child.signalCode !== null) return;
    child.kill("SIGTERM");
    await new Promise<void>((resolve) => {
      const timer = this.setTimer(() => {
        if (child.exitCode === null && child.signalCode === null) child.kill("SIGKILL");
        resolve();
      }, 1_000);
      child.once("exit", () => {
        this.clearTimer(timer);
        resolve();
      });
    });
  }

  private requestRaw(method: string, params: unknown): Promise<unknown> {
    const id = this.nextRequestId++;
    return new Promise((resolve, reject) => {
      const timer = this.setTimer(() => {
        this.pending.delete(id);
        reject(new Error(`Codex App Server ${method} request timed out.`));
      }, this.requestTimeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      try {
        this.sendEnvelope({ id, method, params });
      } catch (error) {
        this.clearTimer(timer);
        this.pending.delete(id);
        reject(error instanceof Error ? error : new Error("Codex App Server stdin failed."));
      }
    });
  }

  private sendEnvelope(value: unknown): void {
    if (!this.child?.stdin.writable) throw new Error("Codex App Server stdin is unavailable.");
    this.child.stdin.write(`${JSON.stringify(value)}\n`, (error) => {
      if (error) this.fail(new Error("Codex App Server stdin failed."));
    });
  }

  private onStdout(chunk: string): void {
    this.stdoutBuffer += chunk;
    let newline = this.stdoutBuffer.indexOf("\n");
    while (newline >= 0) {
      const line = this.stdoutBuffer.slice(0, newline).trim();
      this.stdoutBuffer = this.stdoutBuffer.slice(newline + 1);
      if (line) {
        try {
          const envelope = decodeEnvelope(line);
          if ("method" in envelope) {
            this.emit("message", envelope as ProtocolMethodEnvelope);
          } else {
            this.onResponse(envelope as ProtocolResponse);
          }
        } catch (error) {
          this.fail(error instanceof Error ? error : new Error("Invalid App Server protocol."));
          return;
        }
      }
      newline = this.stdoutBuffer.indexOf("\n");
    }
  }

  private onResponse(response: ProtocolResponse): void {
    const pending = this.pending.get(response.id);
    if (!pending) return;
    this.pending.delete(response.id);
    this.clearTimer(pending.timer);
    if (response.error) {
      pending.reject(new Error("Codex App Server rejected a read-only request."));
    } else {
      pending.resolve(response.result);
    }
  }

  private fail(error: Error): void {
    const child = this.child;
    this.rejectPending(error);
    this.initialized = false;
    if (child && child.exitCode === null && child.signalCode === null) child.kill("SIGTERM");
    this.emit("protocolError", error);
  }

  private rejectPending(error: Error): void {
    for (const pending of this.pending.values()) {
      this.clearTimer(pending.timer);
      pending.reject(error);
    }
    this.pending.clear();
  }
}
