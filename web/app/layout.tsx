import type { Metadata } from "next";
import "./globals.css";
import { loadDemo, getAsofSlices, getThesis } from "@/lib/data";
import { at, pick } from "@/lib/data";
import AppShell from "@/components/AppShell";

export const metadata: Metadata = {
  title: "Counterproof — the VC brain that shows its receipts",
  description:
    "Per-claim trust, three axes never averaged, and an append-only ledger read at a point in time.",
};

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

        <AppShell
          asof={defaultAsof}
          risk={riskAppetite}
          dataOk={ok}
          showcase={at<boolean>(demo, "meta.showcase_mode") === true}
        >
          {children}
        </AppShell>
      </body>
    </html>
  );
}
