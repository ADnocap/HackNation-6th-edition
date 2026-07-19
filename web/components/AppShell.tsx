"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  {
    href: "/",
    label: "Discover",
    hint: "Signals and founders",
    icon: "scope",
  },
  {
    href: "/opportunities",
    label: "Review",
    hint: "Claims and decisions",
    icon: "stack",
  },
  {
    href: "/honesty",
    label: "Methods",
    hint: "Limits and reliability",
    icon: "pulse",
  },
];

function NavIcon({ name }: { name: string }) {
  if (name === "stack") {
    return (
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path d="m3 6 7-3 7 3-7 3-7-3Zm0 4 7 3 7-3M3 14l7 3 7-3" />
      </svg>
    );
  }
  if (name === "pulse") {
    return (
      <svg viewBox="0 0 20 20" aria-hidden="true">
        <path d="M2 10h3l2-5 4 10 2-5h5" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="6" />
      <path d="M10 1v3M10 16v3M1 10h3M16 10h3" />
    </svg>
  );
}

export default function AppShell({
  children,
  asof,
  risk,
  dataOk,
  showcase,
}: {
  children: React.ReactNode;
  asof?: string | null;
  risk?: string | null;
  dataOk: boolean;
  showcase?: boolean;
}) {
  const pathname = usePathname();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <Link href="/" className="brand" aria-label="Counterproof home">
          <span className="brand-mark" aria-hidden="true">
            <span />
          </span>
          <span>
            <strong>Counterproof</strong>
            <small>Evidence intelligence</small>
          </span>
        </Link>

        <nav className="side-nav" aria-label="Primary navigation">
          <span className="nav-kicker">Workspace</span>
          {NAV.map((item) => {
            const active =
              item.href === "/"
                ? pathname === "/" || pathname.startsWith("/person/")
                : pathname === item.href || pathname.startsWith(`${item.href}/`) ||
                  (item.href === "/opportunities" && pathname.startsWith("/opportunity/"));
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`side-nav-item ${active ? "active" : ""}`}
              >
                <span className="nav-icon"><NavIcon name={item.icon} /></span>
                <span>
                  <strong>{item.label}</strong>
                  <small>{item.hint}</small>
                </span>
              </Link>
            );
          })}
        </nav>

        <div className="system-card">
          <div className="system-card-head">
            <span className={`status-dot ${dataOk ? "live" : "down"}`} />
            <span>{dataOk ? "Ledger online" : "Ledger unavailable"}</span>
          </div>
          <dl>
            {risk ? <><dt>Risk posture</dt><dd>{risk}</dd></> : null}
            {asof ? <><dt>Snapshot</dt><dd>{asof.slice(0, 10)}</dd></> : null}
          </dl>
          <p>Every number is read from the same point-in-time ledger.</p>
        </div>
      </aside>

      <div className="app-column">
        <header className="mobile-header">
          <Link href="/" className="brand compact">
            <span className="brand-mark" aria-hidden="true"><span /></span>
            <strong>Counterproof</strong>
          </Link>
          <span className="mobile-status"><span className="status-dot live" /> live ledger</span>
        </header>

        <main id="main" className="app-main">
          {showcase ? (
            <div className="showcase-banner">
              <span>Offline showcase</span>
              <p>Authored examples are enabled so every claim state and decision path works without external services.</p>
              <strong>Fixture data is labelled AUTHORED</strong>
            </div>
          ) : null}
          {children}
        </main>

        <footer className="app-footer">
          <span>Point-in-time evidence, not company-level trust scores.</span>
          <span>No outbound message has been sent.</span>
        </footer>

        <nav className="bottom-nav" aria-label="Mobile navigation">
          {NAV.map((item) => {
            const active = item.href === "/" ? pathname === "/" || pathname.startsWith("/person/") : pathname === item.href || pathname.startsWith(item.href === "/opportunities" ? "/opportunit" : `${item.href}/`);
            return (
              <Link key={item.href} href={item.href} className={active ? "active" : ""}>
                <span className="nav-icon"><NavIcon name={item.icon} /></span>
                <span>{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </div>
    </div>
  );
}
