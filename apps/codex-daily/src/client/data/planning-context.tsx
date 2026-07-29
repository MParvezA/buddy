import {
  createContext,
  type PropsWithChildren,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import type {
  CreateTaskRequest,
  PlanningView,
  ReviewDecisionRequest,
  UpdateTaskRequest,
} from "../../shared/planning";
import {
  createTask,
  decideReview,
  getPlanning,
  reorderTasks,
  transitionTask,
  updateTask,
} from "../api/planning-client";

interface PlanningData {
  view: PlanningView | null;
  loading: boolean;
  error: string | null;
  pendingId: string | null;
  reload: () => void;
  add: (request: CreateTaskRequest) => Promise<void>;
  edit: (taskId: string, request: UpdateTaskRequest) => Promise<void>;
  reorder: (taskIds: string[]) => Promise<void>;
  transition: (taskId: string, action: "confirm" | "reopen") => Promise<void>;
  review: (taskId: string, request: ReviewDecisionRequest) => Promise<void>;
  clearError: () => void;
}

const PlanningContext = createContext<PlanningData | null>(null);

export function PlanningProvider({ children }: PropsWithChildren) {
  const [view, setView] = useState<PlanningView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [requestNumber, setRequestNumber] = useState(0);

  const reload = useCallback(() => {
    setLoading(true);
    setError(null);
    setRequestNumber((value) => value + 1);
  }, []);

  useEffect(() => {
    let active = true;
    getPlanning()
      .then((result) => {
        if (active) {
          setView(result);
          setLoading(false);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Planning could not be loaded.");
          setLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [requestNumber]);

  const mutate = useCallback(
    async (id: string, action: (current: PlanningView) => Promise<PlanningView>) => {
      if (!view) return;
      setPendingId(id);
      setError(null);
      try {
        setView(await action(view));
      } catch (reason) {
        setError(reason instanceof Error ? reason.message : "The planning change could not be saved.");
        throw reason;
      } finally {
        setPendingId(null);
      }
    },
    [view],
  );

  const value = useMemo<PlanningData>(
    () => ({
      view,
      loading,
      error,
      pendingId,
      reload,
      clearError: () => setError(null),
      add: (request) => mutate("create", (current) => createTask(current.localDate, request)),
      edit: (id, request) =>
        mutate(id, (current) => updateTask(current.localDate, id, request)),
      reorder: (taskIds) =>
        mutate("reorder", (current) => reorderTasks(current.localDate, { taskIds })),
      transition: (id, action) =>
        mutate(id, (current) => transitionTask(current.localDate, id, { action })),
      review: (id, request) =>
        mutate(id, (current) => decideReview(current.localDate, id, request)),
    }),
    [view, loading, error, pendingId, reload, mutate],
  );

  return <PlanningContext.Provider value={value}>{children}</PlanningContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components
export function usePlanning(): PlanningData {
  const value = useContext(PlanningContext);
  if (!value) throw new Error("usePlanning must be used inside PlanningProvider");
  return value;
}
