// @vitest-environment node
import { describe, expect, it } from "vitest";
import {
  assertReportTime,
  assertTimezone,
  instantForLocal,
  reportDayBounds,
} from "../../../src/server/reports/report-time.js";

describe("report timezone scheduling", () => {
  it("uses exact Europe/Berlin DST day bounds", () => {
    expect(reportDayBounds("2026-03-29", "Europe/Berlin")).toEqual({
      start: "2026-03-28T23:00:00.000Z",
      end: "2026-03-29T22:00:00.000Z",
    });
    expect(reportDayBounds("2026-10-25", "Europe/Berlin")).toEqual({
      start: "2026-10-24T22:00:00.000Z",
      end: "2026-10-25T23:00:00.000Z",
    });
  });

  it("moves a nonexistent time to the first valid minute and chooses the earlier overlap", () => {
    expect(
      instantForLocal("2026-03-29", "02:30", "Europe/Berlin").toISOString(),
    ).toBe("2026-03-29T01:00:00.000Z");
    expect(
      instantForLocal("2026-10-25", "02:30", "Europe/Berlin").toISOString(),
    ).toBe("2026-10-25T00:30:00.000Z");
  });

  it("rejects malformed preferences without normalizing them", () => {
    expect(() => assertReportTime("24:00")).toThrow(/HH:MM/);
    expect(() => assertTimezone("Mars/Olympus")).toThrow(/IANA/);
  });

  it("maps another configured timezone to exact local-day boundaries", () => {
    expect(reportDayBounds("2026-07-29", "America/New_York")).toEqual({
      start: "2026-07-29T04:00:00.000Z",
      end: "2026-07-30T04:00:00.000Z",
    });
  });
});
