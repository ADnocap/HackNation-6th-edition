import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";
import { loadDemo, getAsofSlices, getThesis } from "@/lib/data";
import { at, pick } from "@/lib/data";
import { fmtTs } from "@/lib/util";
import { Badge } from "@/components/primitives";

export const metadata: Metadata = {
  title: "Counterproof — the VC brain that shows its receipts",
  description:
    "Per-claim trust, three axes never averaged, and an append-only ledger read at a point in time.",
};

const NAV = [
  { href: "/", label: "Signal Feed" },
  { href: "/honesty", label: "Honesty" },
];

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const { demo, ok } = loadDemo();
  const asof = getAsofSlices(demo);
  const thesis = getThesis(demo);
  const defaultAsof =
    pick<string>(asof, "default") ??
    at<string>(demo, "meta.asof") ??
    null;
  const riskAppetite =
    pick<string>(thesis, "risk_appetite") ??
    at<string>(thesis, "risk.appetite") ??
    null;

  return (
    <html lang="en">
      <body className="min-h-screen antialiased">
        <a
          href="#main"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-3 focus:z-50 focus:rounded focus:border focus:border-amber-400 focus:bg-zinc-950 focus:px-3 focus:py-1.5 focus:text-[12px] focus:text-zinc-100"
        >
          Skip to content
        </a>

        <header className="sticky top-0 z-40 border-b border-zinc-800 bg-[#0a0e11]/95 backdrop-blur">
          <div className="mx-auto flex max-w-[1400px] flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3">
            <Link href="/" className="group flex items-baseline gap-2.5">
              <span className="t-display text-[17px] text-zinc-50">
                Counterproof
              </span>
              <span className="hidden text-[11px] italic text-zinc-500 transition-colors group-hover:text-zinc-400 sm:inline">
                evidence before conviction
              </span>
            </Link>

            <nav className="flex items-center gap-1" aria-label="Primary">
              {NAV.map((n) => (
                <Link
                  key={n.href}
                  href={n.href}
                  className="rounded px-2.5 py-1 text-[12.5px] text-zinc-400 transition-colors hover:bg-zinc-900 hover:text-zinc-100"
                >
                  {n.label}
                </Link>
              ))}
            </nav>

            <div className="ml-auto flex flex-wrap items-center gap-x-4 gap-y-2">
              {riskAppetite ? (
                <span className="flex items-baseline gap-1.5">
                  <span className="t-eyebrow">risk</span>
                  <span className="font-mono text-[11px] text-zinc-300">
                    {riskAppetite}
                  </span>
                </span>
              ) : null}
              {defaultAsof ? (
                // The point-in-time stamp. Every read in the system filters on
                // it, so it belongs in the masthead rather than inside a panel.
                <div
                  className="flex items-center gap-2 rounded border border-zinc-700 bg-zinc-900 px-2 py-1"
                  title="Every read path filters WHERE observed_at <= asof. Move this back and the identical code is a backtest."
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  <span className="t-eyebrow text-zinc-500">asof</span>
                  <span className="font-mono text-[11px] tabular-nums text-zinc-200">
                    {fmtTs(defaultAsof)}
                  </span>
                </div>
              ) : null}
              {!ok ? (
                <Badge className="border-rose-500/50 bg-rose-500/10 text-rose-300">
                  no demo.json
                </Badge>
              ) : null}
            </div>
          </div>
        </header>

        <main id="main" className="mx-auto max-w-[1400px] px-5 py-6">
          {children}
        </main>

        <footer className="mx-auto max-w-[1400px] px-5 pb-10 pt-4">
          <p className="max-w-[80ch] border-t border-zinc-900 pt-3 text-[11px] leading-[1.7] text-zinc-500">
            Renderer reads a committed{" "}
            <code className="font-mono text-zinc-400">demo.json</code> only — no
            database, no API, no client env vars. Real people are pseudonymized.
            Outbound messages are drafted and rendered; none was sent. The three
            axes are never averaged into a single number, anywhere in this
            system.
          </p>
        </footer>
      </body>
    </html>
  );
}
