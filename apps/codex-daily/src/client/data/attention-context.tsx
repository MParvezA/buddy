import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type { AttentionSnapshot } from "../../shared/attention";
import {
  acknowledgeAttention,
  dismissAttention,
  getAttention,
} from "../api/attention-client";

interface AttentionData {
  snapshot: AttentionSnapshot | null;
  loading: boolean;
  error: string | null;
  pendingId: string | null;
  acknowledge: (id: string) => Promise<void>;
  dismiss: (id: string) => Promise<void>;
}

const AttentionContext = createContext<AttentionData | null>(null);

export function AttentionProvider({ children }: PropsWithChildren) {
  const [snapshot, setSnapshot] = useState<AttentionSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    let events: EventSource | null = null;
    getAttention()
      .then((value) => {
        if (!active) return;
        setSnapshot(value);
        setLoading(false);
        if (typeof EventSource !== "undefined") {
          events = new EventSource("/api/attention/events");
          events.addEventListener("attention", (event) => {
            if (!active) return;
            try {
              setSnapshot(
                JSON.parse((event as MessageEvent<string>).data) as AttentionSnapshot,
              );
              setError(null);
            } catch {
              setError("A live attention update could not be read.");
            }
          });
          events.onerror = () => {
            if (active) {
              setError("Live attention updates paused; the last queue remains visible.");
            }
          };
        }
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(
          reason instanceof Error
            ? reason.message
            : "The attention queue could not be loaded.",
        );
        setLoading(false);
      });
    return () => {
      active = false;
      events?.close();
    };
  }, []);

  const mutate = useCallback(
    async (
      id: string,
      action: (attentionId: string) => Promise<AttentionSnapshot>,
    ) => {
      setPendingId(id);
      setError(null);
      try {
        setSnapshot(await action(id));
      } catch (reason) {
        setError(
          reason instanceof Error
            ? reason.message
            : "The local attention state could not be saved.",
        );
        throw reason;
      } finally {
        setPendingId(null);
      }
    },
    [],
  );

  const value = useMemo<AttentionData>(
    () => ({
      snapshot,
      loading,
      error,
      pendingId,
      acknowledge: (id) => mutate(id, acknowledgeAttention),
      dismiss: (id) => mutate(id, dismissAttention),
    }),
    [snapshot, loading, error, pendingId, mutate],
  );

  return (
    <AttentionContext.Provider value={value}>
      {children}
    </AttentionContext.Provider>
  );
}

// eslint-disable-next-line react-refresh/only-export-components
export function useAttention(): AttentionData {
  const value = useContext(AttentionContext);
  if (!value) throw new Error("useAttention must be used inside AttentionProvider");
  return value;
}
