import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { SessionBriefSnapshot } from "../../shared/session-briefs";
import {
  getSessionBriefs,
  parseSessionBriefSnapshot,
  refreshSessionBrief,
  refreshSessionBriefs,
} from "../api/session-briefs-client";

interface SessionBriefData {
  snapshot: SessionBriefSnapshot | null;
  loading: boolean;
  loadError: string | null;
  streamError: string | null;
  mutationError: string | null;
  pendingThreadIds: ReadonlySet<string>;
  refreshingAll: boolean;
  refreshAll: () => Promise<void>;
  refreshThread: (threadId: string) => Promise<void>;
}

const SessionBriefContext = createContext<SessionBriefData | null>(null);

export function SessionBriefProvider({ children }: PropsWithChildren) {
  const [snapshot, setSnapshot] = useState<SessionBriefSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [streamError, setStreamError] = useState<string | null>(null);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [pendingThreadIds, setPendingThreadIds] = useState<ReadonlySet<string>>(
    () => new Set(),
  );
  const [refreshingAll, setRefreshingAll] = useState(false);
  const refreshingAllRef = useRef(false);
  const pendingThreadIdsRef = useRef(new Set<string>());

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
              setSnapshot(parseSessionBriefSnapshot(
                JSON.parse((event as MessageEvent<string>).data) as unknown,
              ));
              setStreamError(null);
            } catch {
              setStreamError(
                "A live session-brief update could not be read; the last snapshot remains visible.",
              );
            }
          });
          events.onerror = () => {
            if (active) {
              setStreamError("Live brief updates paused; the last snapshot remains visible.");
            }
          };
        }
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setLoadError(
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
    if (refreshingAllRef.current) return;
    refreshingAllRef.current = true;
    setRefreshingAll(true);
    setMutationError(null);
    try {
      setSnapshot(await refreshSessionBriefs());
    } catch (reason) {
      setMutationError(
        reason instanceof Error
          ? reason.message
          : "Session briefs could not be refreshed.",
      );
    } finally {
      refreshingAllRef.current = false;
      setRefreshingAll(false);
    }
  }, []);

  const refreshThread = useCallback(async (threadId: string) => {
    if (pendingThreadIdsRef.current.has(threadId)) return;
    pendingThreadIdsRef.current.add(threadId);
    setPendingThreadIds(new Set(pendingThreadIdsRef.current));
    setMutationError(null);
    try {
      setSnapshot(await refreshSessionBrief(threadId));
    } catch (reason) {
      setMutationError(
        reason instanceof Error
          ? reason.message
          : "The session brief could not be refreshed.",
      );
    } finally {
      pendingThreadIdsRef.current.delete(threadId);
      setPendingThreadIds(new Set(pendingThreadIdsRef.current));
    }
  }, []);

  const value = useMemo<SessionBriefData>(
    () => ({
      snapshot,
      loading,
      loadError,
      streamError,
      mutationError,
      pendingThreadIds,
      refreshingAll,
      refreshAll,
      refreshThread,
    }),
    [
      snapshot,
      loading,
      loadError,
      streamError,
      mutationError,
      pendingThreadIds,
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
