import { useEffect, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { getHealth } from "../api/dashboard-client";
import { ConnectionIndicator } from "./ConnectionIndicator";

const navigation = [
  { to: "/", label: "Today", end: true },
  { to: "/reports", label: "Reports", end: false },
  { to: "/settings", label: "Settings", end: false },
];

export function AppShell() {
  const [serviceAvailable, setServiceAvailable] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    getHealth()
      .then(() => {
        if (active) setServiceAvailable(true);
      })
      .catch(() => {
        if (active) setServiceAvailable(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="app-frame">
      <a className="skip-link" href="#main-content">
        Skip to main content
      </a>
      <header className="topbar">
        <NavLink className="wordmark" to="/" aria-label="Codex Daily home">
          <span className="wordmark-mark" aria-hidden="true">
            CD
          </span>
          <span>
            Codex Daily
            <small>Daily operations</small>
          </span>
        </NavLink>
        <ConnectionIndicator serviceAvailable={serviceAvailable} />
      </header>

      <div className="shell-grid">
        <nav className="primary-nav" aria-label="Primary">
          <p className="nav-kicker">Workspace</p>
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            >
              <span className="nav-symbol" aria-hidden="true">
                {item.label.slice(0, 1)}
              </span>
              {item.label}
            </NavLink>
          ))}
          <div className="privacy-note">
            <span aria-hidden="true">⌂</span>
            <p>
              <strong>Private by default</strong>
              Representative data stays in this local service.
            </p>
          </div>
        </nav>

        <main id="main-content" className="main-content" tabIndex={-1}>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
