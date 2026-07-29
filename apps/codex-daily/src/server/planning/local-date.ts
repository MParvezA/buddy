import { PlanningError } from "./planning-errors.js";

const ISO_LOCAL_DATE = /^\d{4}-\d{2}-\d{2}$/;

export function assertLocalDate(value: string): string {
  if (!ISO_LOCAL_DATE.test(value)) {
    throw new PlanningError("validation", "Date must use YYYY-MM-DD.");
  }
  const parsed = new Date(`${value}T00:00:00Z`);
  if (Number.isNaN(parsed.valueOf()) || parsed.toISOString().slice(0, 10) !== value) {
    throw new PlanningError("validation", "Date is not a valid calendar date.");
  }
  return value;
}

export function priorLocalDate(value: string): string {
  const date = new Date(`${assertLocalDate(value)}T00:00:00Z`);
  date.setUTCDate(date.getUTCDate() - 1);
  return date.toISOString().slice(0, 10);
}

export function localDateFor(clock: () => Date, timezone: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(clock());
  const get = (type: Intl.DateTimeFormatPartTypes) =>
    parts.find((part) => part.type === type)?.value;
  return assertLocalDate(`${get("year")}-${get("month")}-${get("day")}`);
}
