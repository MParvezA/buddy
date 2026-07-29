import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { ObserverSnapshot } from "../../shared/observer-types";
import {
  getObserver,
  linkTask as putTaskLink,
  unlinkTask as deleteTaskLink,
} from "../api/observer-client";

interface ObserverData {
  snapshot: ObserverSnapshot | null;
  loading: boolean;
  error: string | null;
  pendingLink: string | null;
  reload: () => void;
  linkTask: (taskId: string, threadId: string) => Promise<void>;
  unlinkTask: (taskId: string, threadId: string) => Promise<void>;
}

const ObserverContext = createContext<ObserverData | null>(null);

export function ObserverProvider({ children }: PropsWithChildren) {
  const [snapshot, setSnapshot] = useState<ObserverSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingLink, setPendingLink] = useState<string | null>(null);
  const [requestNumber, setRequestNumber] = useState(0);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    setRequestNumber((value) => value + 1);
  }, []);

  useEffect(() => {
    let active = true;
    let events: EventSource | null = null;
    getObserver()
      .then((result) => {
        if (!active) return;
        setSnapshot(result);
        setLoading(false);
        if (typeof EventSource !== "undefined") {
          events = new EventSource("/api/observer/events");
          events.addEventListener("observer", (event) => {
            if (!active) return;
            try {
              setSnapshot(JSON.parse((event as MessageEvent<string>).data) as ObserverSnapshot);
              setError(null);
            } catch {
              setError("A live observer update could not be read.");
            }
          });
          events.onerror = () => {
            if (active) setError("Live updates paused; the last observer snapshot remains visible.");
          };
        }
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "Observer data could not be loaded.");
        setLoading(false);
      });
    return () => {
      active = false;
      events?.close();
    };
  }, [requestNumber]);

  const mutateLink = useCallback(
    async (
      taskId: string,
      threadId: string,
      action: (task: string, thread: string) => Promise<ObserverSnapshot>,
    ) => {
      const pending = `${taskId}:${threadId}`;
      setPendingLink(pending);
      setError(null);
      try {
        setSnapshot(await action(taskId, threadId));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "The task link could not be saved.");
        throw reason;
      } finally {
        setPendingLink(null);
      }
    },
    [],
  );

  const value = useMemo<ObserverData>(
    () => ({
      snapshot,
      loading,
      error,
      pendingLink,
      reload,
      linkTask: (taskId, threadId) => mutateLink(taskId, threadId, putTaskLink),
      unlinkTask: (taskId, threadId) => mutateLink(taskId, threadId, deleteTaskLink),
    }),
    [snapshot, loading, error, pendingLink, reload, mutateLink],
  );

  return <ObserverContext.Provider value={value}>{children}</ObserverContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function useObserver(): ObserverData {
  const value = useContext(ObserverContext);
  if (!value) throw new Error("useObserver must be used inside ObserverProvider");
  return value;
}
