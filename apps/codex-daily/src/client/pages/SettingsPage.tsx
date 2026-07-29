import { Link } from "react-router-dom";

export function SettingsPage() {
  return (
    <article className="secondary-page">
      <Link className="back-link" to="/">← Back to Today</Link>
      <header className="page-header compact">
        <div>
          <p className="eyebrow">Local preferences</p>
          <h1>Settings</h1>
          <p>This representative slice shows the intended defaults without saving changes.</p>
        </div>
      </header>
      <div className="settings-grid">
        <section className="panel setting-card">
          <p className="eyebrow">Evening report</p>
          <h2>18:00</h2>
          <p>Europe/Berlin</p>
          <span className="read-only-label">Read-only preview</span>
        </section>
        <section className="panel setting-card">
          <p className="eyebrow">Data source</p>
          <h2>Representative</h2>
          <p>Codex is not connected in this slice.</p>
          <span className="read-only-label">Local service</span>
        </section>
        <section className="panel setting-card">
          <p className="eyebrow">Retention</p>
          <h2>Metadata only</h2>
          <p>No full transcripts or browser storage.</p>
          <span className="read-only-label">Minimal local retention</span>
        </section>
      </div>
    </article>
  );
}
