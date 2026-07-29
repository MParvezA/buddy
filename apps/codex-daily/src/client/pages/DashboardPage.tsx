import { DashboardSections } from "../components/DashboardSections";
import { usePlanning } from "../data/planning-context";

export function DashboardPage() {
  const planning = usePlanning();
  const dateLabel = planning.view
    ? new Intl.DateTimeFormat("en-GB", {
        weekday: "long",
        day: "numeric",
        month: "long",
        timeZone: "UTC",
      }).format(new Date(`${planning.view.localDate}T12:00:00Z`))
    : "Today";

  return (
    <>
      <header className="page-header">
        <div>
          <p className="eyebrow">Your operating day</p>
          <h1>{dateLabel}</h1>
          <p>See what needs you, what moved, and what remains—without opening every chat.</p>
        </div>
        <div className="local-stamp">
          <span aria-hidden="true">◇</span>
          Local daily monitor
          <small>Codex metadata · read-only</small>
        </div>
      </header>

      <DashboardSections />
    </>
  );
}
