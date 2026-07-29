import { useAttention } from "../../data/attention-context";
import { useObserver } from "../../data/observer-context";
import { AttentionCard } from "./AttentionCard";

interface NeedsYouProps {
  timezone: string;
}

export function NeedsYou({ timezone }: NeedsYouProps) {
  const attention = useAttention();
  const observer = useObserver();
  const items = attention.snapshot?.items ?? [];

  const act = (
    action: (id: string) => Promise<void>,
    id: string,
  ) => {
    void action(id).catch(() => undefined);
  };

  return (
    <section
      className="panel attention-panel"
      data-section-order="1"
      aria-labelledby="attention-title"
    >
      <div className="section-heading">
        <div>
          <p className="eyebrow">Priority 01</p>
          <h2 id="attention-title">Needs your attention</h2>
        </div>
        <span className="count-pill">{items.length} open</span>
      </div>

      {attention.snapshot?.liveRequestCoverage ===
        "external_clients_unavailable" && (
        <p className="inline-notice capability-notice">
          Standalone history mode cannot see live approvals or direct questions
          owned by other Codex clients. No request items are inferred.
        </p>
      )}
      {attention.snapshot?.connectionState !== "connected" &&
        !attention.loading && (
          <p className="inline-notice">
            Codex monitoring is paused. This is the last-known queue; no new
            explicit or stale items are being inferred while disconnected.
          </p>
        )}
      {attention.error && (
        <p className="inline-notice attention-error" role="alert">
          {attention.error}
        </p>
      )}

      {attention.loading ? (
        <p className="empty-inline" role="status">Loading the local attention queue…</p>
      ) : items.length === 0 ? (
        <div className="empty-inline">
          <h3>Nothing needs you right now</h3>
          <p>Failures, interruptions, blockers, and supported live requests will appear here.</p>
        </div>
      ) : (
        <>
          <ul className="card-list attention-list">
            {items.map((item) => (
              <AttentionCard
                key={item.id}
                item={item}
                thread={
                  observer.snapshot?.threads.find(
                    (thread) => thread.id === item.threadId,
                  ) ?? null
                }
                timezone={timezone}
                pending={attention.pendingId === item.id}
                onAcknowledge={() => act(attention.acknowledge, item.id)}
                onDismiss={() => act(attention.dismiss, item.id)}
              />
            ))}
          </ul>
          <p className="attention-readonly-note">
            Acknowledge and dismiss only change this local queue. Codex Daily never
            answers or changes the source chat.
          </p>
        </>
      )}
    </section>
  );
}
