import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { SessionBriefSnapshot } from "../../shared/session-briefs";
import {
  getSessionBriefs,
  refreshSessionBrief,
  refreshSessionBriefs,
} from "../api/session-briefs-client";

interface SessionBriefData {
  snapshot: SessionBriefSnapshot | null;
  loading: boolean;
  error: string | null;
  pendingThreadId: string | null;
  refreshingAll: boolean;
  refreshAll: () => Promise<void>;
  refreshThread: (threadId: string) => Promise<void>;
}

const SessionBriefContext = createContext<SessionBriefData | null>(null);

export function SessionBriefProvider({ children }: PropsWithChildren) {
  const [snapshot, setSnapshot] = useState<SessionBriefSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingThreadId, setPendingThreadId] = useState<string | null>(null);
  const [refreshingAll, setRefreshingAll] = useState(false);

  useEffect(() => {
    let active = true;
    let events: EventSource | null = null;
    getSessionBriefs()
      .then((value) => {
        if (!active) return;
        setSnapshot(value);
        setLoading(false);
        if (typeof EventSource !== "undefined") {
          events = new EventSource("/api/session-briefs/events");
          events.addEventListener("session-briefs", (event) => {
            if (!active) return;
            try {
              setSnapshot(
                JSON.parse(
                  (event as MessageEvent<string>).data,
                ) as SessionBriefSnapshot,
              );
              setError(null);
            } catch {
              setError("A live session-brief update could not be read.");
            }
          });
          events.onerror = () => {
            if (active) {
              setError(
                "Live session-brief updates paused; the last snapshot remains visible.",
              );
            }
          };
        }
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "Session briefs could not be loaded.",
        );
        setLoading(false);
      });
    return () => {
      active = false;
      events?.close();
    };
  }, []);

  const refreshAll = useCallback(async () => {
    setRefreshingAll(true);
    setError(null);
    try {
      setSnapshot(await refreshSessionBriefs());
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "Session briefs could not be refreshed.",
      );
      throw reason;
    } finally {
      setRefreshingAll(false);
    }
  }, []);

  const refreshThread = useCallback(async (threadId: string) => {
    setPendingThreadId(threadId);
    setError(null);
    try {
      setSnapshot(await refreshSessionBrief(threadId));
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "The session brief could not be refreshed.",
      );
      throw reason;
    } finally {
      setPendingThreadId(null);
    }
  }, []);

  const value = useMemo<SessionBriefData>(
    () => ({
      snapshot,
      loading,
      error,
      pendingThreadId,
      refreshingAll,
      refreshAll,
      refreshThread,
    }),
    [
      snapshot,
      loading,
      error,
      pendingThreadId,
      refreshingAll,
      refreshAll,
      refreshThread,
    ],
  );

  return (
    <SessionBriefContext.Provider value={value}>
      {children}
    </SessionBriefContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useSessionBriefs(): SessionBriefData {
  const value = useContext(SessionBriefContext);
  if (!value) {
    throw new Error("useSessionBriefs must be used inside SessionBriefProvider");
  }
  return value;
}
