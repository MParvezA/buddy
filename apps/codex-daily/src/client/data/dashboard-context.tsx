import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { DashboardSnapshot } from "../../shared/dashboard";
import { getDashboard } from "../api/dashboard-client";

interface DashboardData {
  snapshot: DashboardSnapshot | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

const DashboardDataContext = createContext<DashboardData | null>(null);

export function DashboardDataProvider({ children }: PropsWithChildren) {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [requestNumber, setRequestNumber] = useState(0);

  const reload = useCallback(() => {
    setSnapshot(null);
    setLoading(true);
    setError(null);
    setRequestNumber((value) => value + 1);
  }, []);

  useEffect(() => {
    let active = true;

    getDashboard()
      .then((day) => {
        if (active) {
          setSnapshot(day);
          setLoading(false);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "The day could not be loaded.");
          setLoading(false);
        }
      });

    return () => {
      active = false;
    };
  }, [requestNumber]);

  const value = useMemo(
    () => ({ snapshot, loading, error, reload }),
    [snapshot, loading, error, reload],
  );

  return <DashboardDataContext.Provider value={value}>{children}</DashboardDataContext.Provider>;
}

// The provider and its paired hook intentionally share one private context.
// eslint-disable-next-line react-refresh/only-export-components
export function useDashboardData(): DashboardData {
  const value = useContext(DashboardDataContext);
  if (!value) {
    throw new Error("useDashboardData must be used inside DashboardDataProvider");
  }
  return value;
}
