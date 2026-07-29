import type { OperationsDiagnostics } from "../../shared/operations.js";
import { ObserverService } from "../codex/observer-service.js";
import { PrivacyService } from "../privacy/privacy-service.js";
import { ReportRepository } from "../reports/report-repository.js";
import { ReportScheduler } from "../reports/report-scheduler.js";
import { SessionBriefService } from "../briefs/session-brief-service.js";

export interface DiagnosticsServiceOptions {
  dataLocation: string;
  privacy: PrivacyService;
  observer: ObserverService;
  scheduler: ReportScheduler;
  reports: ReportRepository;
  sessionBriefs: SessionBriefService;
  version: string;
}

export class DiagnosticsService {
  constructor(private readonly options: DiagnosticsServiceOptions) {}

  snapshot(): OperationsDiagnostics {
    const latest = this.options.reports.latestSnapshot();
    return {
      localOnly: true,
      dataLocation:
        this.options.dataLocation === ":memory:"
          ? "Temporary in-memory database"
          : this.options.dataLocation,
      schedule: this.options.reports.getSchedule(),
      retainedCounts: this.options.privacy.retainedCounts(),
      retainedDates: this.options.privacy.retainedDates(),
      database: this.options.privacy.databaseHealth(),
      observer: this.options.observer.operationalDiagnostics(),
      scheduler: this.options.scheduler.operationalDiagnostics(),
      reports: {
        lastFactualReportAt: latest?.createdAt ?? null,
        lastNarrativeOutcome: latest?.narrative.status ?? null,
      },
      sessionBriefs: this.options.sessionBriefs.operationalDiagnostics(),
      runtime: {
        application: "codex-daily",
        version: this.options.version,
        node: process.version,
      },
    };
  }
}
