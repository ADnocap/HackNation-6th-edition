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
        <header className="sticky top-0 z-40 border-b border-zinc-800 bg-zinc-950/95 backdrop-blur">
          <div className="mx-auto flex max-w-[1400px] items-center gap-5 px-5 py-2.5">
            <Link href="/" className="group flex items-baseline gap-2">
              <span className="text-[15px] font-semibold tracking-tight text-zinc-50">
                Counterproof
              </span>
              <span className="hidden text-[11px] text-zinc-500 group-hover:text-zinc-400 sm:inline">
                evidence before conviction
              </span>
            </Link>

            <nav className="flex items-center gap-1">
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

            <div className="ml-auto flex items-center gap-3">
              {riskAppetite ? (
                <Badge className="border-zinc-700 bg-zinc-900 text-zinc-400">
                  risk: {riskAppetite}
                </Badge>
              ) : null}
              {defaultAsof ? (
                <div
                  className="flex items-center gap-1.5 font-mono text-[11px] text-zinc-400"
                  title="Every read path filters WHERE observed_at <= asof. Move this back and the identical code is a backtest."
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                  asof {fmtTs(defaultAsof)}
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

        <main className="mx-auto max-w-[1400px] px-5 py-5">{children}</main>

        <footer className="mx-auto max-w-[1400px] px-5 pb-10 pt-4">
          <p className="border-t border-zinc-900 pt-3 text-[11px] leading-relaxed text-zinc-600">
            Renderer reads a committed <code className="text-zinc-500">demo.json</code>{" "}
            only — no database, no API, no client env vars. Real people are
            pseudonymized. Outbound messages are drafted and rendered; none was
            sent. The three axes are never averaged into a single number,
            anywhere in this system.
          </p>
        </footer>
      </body>
    </html>
  );
}
