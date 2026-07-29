import type { PlanningErrorCode } from "../../shared/planning.js";

export class PlanningError extends Error {
  constructor(
    public readonly code: PlanningErrorCode,
    message: string,
  ) {
    super(message);
    this.name = "PlanningError";
  }
}
