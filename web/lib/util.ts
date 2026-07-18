import type { Json } from "./types";

/** Format an ISO-8601 timestamp compactly, without inventing a locale. */
export function fmtTs(iso: Json): string {
  if (typeof iso !== "string" || !iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return String(iso);
  const p = (x: number) => String(x).padStart(2, "0");
  return `${d.getUTCFullYear()}-${p(d.getUTCMonth() + 1)}-${p(
    d.getUTCDate()
  )} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}Z`;
}

export function fmtDate(iso: Json): string {
  if (typeof iso !== "string" || !iso) return "—";
  return iso.slice(0, 10);
}

/** Round for display without pretending to more precision than we have. */
export function fmtNum(v: Json, digits = 1): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "string") return v;
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  if (Number.isInteger(v)) return String(v);
  return v.toFixed(digits);
}

export function fmtMoney(v: Json): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  if (v >= 1000) return `$${(v / 1000).toFixed(0)}K`;
  return `$${v}`;
}

export function fmtSigned(v: Json, digits = 1): string {
  if (typeof v !== "number" || !Number.isFinite(v)) return "—";
  const s = v.toFixed(digits);
  return v >= 0 ? `+${s}` : s;
}

/** Human label from a snake_case token. */
export function humanize(s: Json): string {
  if (typeof s !== "string" || !s) return "—";
  return s.replace(/_/g, " ");
}

export function titleize(s: Json): string {
  const h = humanize(s);
  return h.charAt(0).toUpperCase() + h.slice(1);
}

/** Clamp for chart geometry. */
export function clamp(v: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, v));
}

/** Safe array. */
export function arr(v: Json): Json[] {
  return Array.isArray(v) ? v.filter((x) => x !== null && x !== undefined) : [];
}

export function isObj(v: Json): boolean {
  return !!v && typeof v === "object" && !Array.isArray(v);
}

/** Extract a comparable number from a Quantity-or-number. */
export function qval(q: Json): number | null {
  if (typeof q === "number" && Number.isFinite(q)) return q;
  if (isObj(q) && typeof q.value === "number" && Number.isFinite(q.value))
    return q.value;
  return null;
}

export const CLAIM_STATE_STYLE: Record<
  string,
  { label: string; dot: string; text: string; bg: string; border: string }
> = {
  verified: {
    label: "VERIFIED",
    dot: "bg-emerald-400",
    text: "text-emerald-300",
    bg: "bg-emerald-500/10",
    border: "border-emerald-500/30",
  },
  unverified: {
    label: "UNVERIFIED",
    dot: "bg-amber-400",
    text: "text-amber-300",
    bg: "bg-amber-500/10",
    border: "border-amber-500/30",
  },
  contradicted: {
    label: "CONTRADICTED",
    dot: "bg-rose-500",
    text: "text-rose-300",
    bg: "bg-rose-500/10",
    border: "border-rose-500/30",
  },
  absent_but_expected: {
    label: "ABSENT BUT EXPECTED",
    dot: "bg-violet-400",
    text: "text-violet-300",
    bg: "bg-violet-500/10",
    border: "border-violet-500/30",
  },
};

export const PROVENANCE_STYLE: Record<
  string,
  { label: string; cls: string }
> = {
  live: { label: "LIVE", cls: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40" },
  fixture: { label: "FIXTURE", cls: "bg-sky-500/15 text-sky-300 border-sky-500/40" },
  synthetic: { label: "AUTHORED", cls: "bg-amber-500/15 text-amber-300 border-amber-500/40" },
};

export const VERDICT_STYLE: Record<string, string> = {
  conditional: "bg-amber-500/15 text-amber-200 border-amber-500/50",
  probe_further: "bg-sky-500/15 text-sky-200 border-sky-500/50",
  pass: "bg-zinc-600/20 text-zinc-300 border-zinc-500/50",
  invest: "bg-emerald-500/15 text-emerald-200 border-emerald-500/50",
  decide_now: "bg-emerald-500/15 text-emerald-200 border-emerald-500/50",
};

export const TREND: Record<string, { arrow: string; cls: string }> = {
  improving: { arrow: "▲", cls: "text-emerald-400" },
  declining: { arrow: "▼", cls: "text-rose-400" },
  stable: { arrow: "▬", cls: "text-zinc-400" },
  insufficient_data: { arrow: "?", cls: "text-zinc-500" },
};

export const MARKET_STYLE: Record<string, string> = {
  bullish: "text-emerald-300",
  neutral: "text-zinc-300",
  bear: "text-rose-300",
  bearish: "text-rose-300",
};
