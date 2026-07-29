import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ReportSchedulerState, ReportSnapshot } from "../../shared/report";
import {
  generateReport,
  getLatestReport,
  retryNarrative,
} from "../api/report-client";
import { REPORT_SCHEDULE_CHANGED_EVENT } from "./invalidation";

interface ReportData {
  latest: ReportSnapshot | null;
  scheduler: ReportSchedulerState | null;
  loading: boolean;
  pending: boolean;
  error: string | null;
  reload: () => void;
  generate: (localDate?: string) => Promise<void>;
  retry: (id: string) => Promise<void>;
}

const ReportContext = createContext<ReportData | null>(null);

export function ReportProvider({ children }: PropsWithChildren) {
  const [latest, setLatest] = useState<ReportSnapshot | null>(null);
  const [scheduler, setScheduler] = useState<ReportSchedulerState | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);
  const reload = useCallback(() => {
    setLoading(true);
    setScheduler(null);
    setVersion((value) => value + 1);
  }, []);

  useEffect(() => {
    window.addEventListener(REPORT_SCHEDULE_CHANGED_EVENT, reload);
    return () => window.removeEventListener(REPORT_SCHEDULE_CHANGED_EVENT, reload);
  }, [reload]);

  useEffect(() => {
    let active = true;
    getLatestReport()
      .then((response) => {
        if (!active) return;
        setLatest(response.snapshot);
        setScheduler(response.scheduler);
        setError(null);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "Reports could not load.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [version]);

  const mutate = useCallback(async (action: () => Promise<ReportSnapshot>) => {
    setPending(true);
    setError(null);
    try {
      setLatest(await action());
      setVersion((value) => value + 1);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Report generation failed.");
      throw reason;
    } finally {
      setPending(false);
    }
  }, []);

  const value = useMemo<ReportData>(
    () => ({
      latest,
      scheduler,
      loading,
      pending,
      error,
      reload,
      generate: (localDate) => mutate(() => generateReport(localDate)),
      retry: (id) => mutate(() => retryNarrative(id)),
    }),
    [latest, scheduler, loading, pending, error, reload, mutate],
  );
  return <ReportContext.Provider value={value}>{children}</ReportContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useReports(): ReportData {
  const value = useContext(ReportContext);
  if (!value) throw new Error("useReports must be used inside ReportProvider");
  return value;
}
