import { assertLocalDate } from "../planning/local-date.js";

const LOCAL_TIME = /^([01]\d|2[0-3]):([0-5]\d)$/;

export function assertReportTime(value: string): string {
  if (!LOCAL_TIME.test(value)) throw new Error("Time must use 24-hour HH:MM.");
  return value;
}

export function assertTimezone(value: string): string {
  if (!value || value.length > 100) throw new Error("Timezone is invalid.");
  try {
    new Intl.DateTimeFormat("en", { timeZone: value }).format(new Date(0));
  } catch {
    throw new Error("Timezone must be a valid IANA timezone.");
  }
  return value;
}

interface ZonedParts {
  year: number;
  month: number;
  day: number;
  hour: number;
  minute: number;
  second: number;
}

function partsAt(instant: Date, timezone: string): ZonedParts {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timezone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  }).formatToParts(instant);
  const value = (type: Intl.DateTimeFormatPartTypes) =>
    Number(parts.find((part) => part.type === type)?.value);
  return {
    year: value("year"),
    month: value("month"),
    day: value("day"),
    hour: value("hour"),
    minute: value("minute"),
    second: value("second"),
  };
}

export function instantForLocal(
  localDate: string,
  localTime: string,
  timezone: string,
): Date {
  assertLocalDate(localDate);
  assertReportTime(localTime);
  assertTimezone(timezone);
  const [year, month, day] = localDate.split("-").map(Number);
  const [hour, minute] = localTime.split(":").map(Number);
  const target = Date.UTC(year, month - 1, day, hour, minute, 0);
  const offsets = new Set<number>();
  for (const probe of [target - 86_400_000, target, target + 86_400_000]) {
    const parts = partsAt(new Date(probe), timezone);
    offsets.add(
      Date.UTC(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second) -
        probe,
    );
  }
  const exact = [...offsets]
    .map((offset) => target - offset)
    .filter((candidate) => {
      const parts = partsAt(new Date(candidate), timezone);
      return (
        parts.year === year &&
        parts.month === month &&
        parts.day === day &&
        parts.hour === hour &&
        parts.minute === minute
      );
    })
    .sort((a, b) => a - b);
  // During a fall-back overlap, the first occurrence is the deterministic slot.
  if (exact[0] !== undefined) return new Date(exact[0]);

  // During a spring-forward gap, run at the first valid local minute after the
  // requested wall time. The preference itself is retained for following days.
  const candidates = [...offsets].map((offset) => target - offset);
  const start = Math.min(...candidates) - 3 * 60 * 60_000;
  const end = Math.max(...candidates) + 3 * 60 * 60_000;
  for (let candidate = start; candidate <= end; candidate += 60_000) {
    const parts = partsAt(new Date(candidate), timezone);
    const represented = Date.UTC(
      parts.year,
      parts.month - 1,
      parts.day,
      parts.hour,
      parts.minute,
      0,
    );
    if (
      parts.year === year &&
      parts.month === month &&
      parts.day === day &&
      represented >= target
    ) {
      return new Date(candidate);
    }
  }
  throw new Error("The configured local schedule could not be resolved.");
}

export function nextLocalDate(localDate: string): string {
  const date = new Date(`${assertLocalDate(localDate)}T00:00:00.000Z`);
  date.setUTCDate(date.getUTCDate() + 1);
  return date.toISOString().slice(0, 10);
}

export function reportDayBounds(localDate: string, timezone: string): {
  start: string;
  end: string;
} {
  return {
    start: instantForLocal(localDate, "00:00", timezone).toISOString(),
    end: instantForLocal(nextLocalDate(localDate), "00:00", timezone).toISOString(),
  };
}
