import React from "react";
import type { Json } from "@/lib/types";
import { arr, clamp, fmtDate, fmtNum, isObj, qval } from "@/lib/util";
import { EmptyState } from "./primitives";

/* ------------------------------------------------------------------ */
/* Interval bar — a point estimate inside its credible interval        */
/* ------------------------------------------------------------------ */

export function IntervalBar({
  point,
  interval,
  domain = [0, 100],
  threshold,
  height = 34,
  label,
}: {
  point: number | null;
  interval: Json;
  domain?: [number, number];
  /** The conviction gate. Capital deploys only when the LOWER bound clears it. */
  threshold?: number | null;
  height?: number;
  label?: string;
}) {
  const [lo, hi] = domain;
  const span = hi - lo || 1;
  const pct = (v: number) => clamp(((v - lo) / span) * 100, 0, 100);

  const iv =
    Array.isArray(interval) && interval.length === 2
      ? [Number(interval[0]), Number(interval[1])]
      : null;

  if (point === null && !iv) {
    return (
      <div className="text-[12px] text-zinc-600">
        No interval at this asof.
      </div>
    );
  }

  const ivLo = iv ? pct(iv[0]) : null;
  const ivHi = iv ? pct(iv[1]) : null;
  const clears = iv && threshold != null ? iv[0] >= threshold : null;

  return (
    <div className="w-full" style={{ height }}>
      <div className="relative h-2.5 w-full rounded-full bg-zinc-800">
        {/* interval */}
        {ivLo !== null && ivHi !== null ? (
          <div
            className={`absolute top-0 h-2.5 rounded-full ${
              clears ? "bg-emerald-500/40" : "bg-amber-500/35"
            }`}
            style={{ left: `${ivLo}%`, width: `${Math.max(ivHi - ivLo, 0.5)}%` }}
            title={label ? `${label}: [${iv![0]}, ${iv![1]}]` : undefined}
          />
        ) : null}
        {/* point */}
        {point !== null ? (
          <div
            className="absolute top-[-3px] h-4 w-[2px] rounded bg-zinc-100"
            style={{ left: `${pct(point)}%` }}
            title={`point ${point}`}
          />
        ) : null}
        {/* threshold */}
        {threshold != null ? (
          <div
            className="absolute top-[-5px] h-5 border-l border-dashed border-rose-400/80"
            style={{ left: `${pct(threshold)}%` }}
            title={`conviction threshold ${threshold}`}
          />
        ) : null}
      </div>
      <div className="mt-1 flex justify-between font-mono text-[10px] text-zinc-600">
        <span>{lo}</span>
        {iv ? (
          <span className={clears ? "text-emerald-400" : "text-amber-400"}>
            lower bound {fmtNum(iv[0])}
            {threshold != null
              ? clears
                ? ` clears ${threshold}`
                : ` below ${threshold}`
              : ""}
          </span>
        ) : null}
        <span>{hi}</span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Founder score history — step function across ventures               */
/* ------------------------------------------------------------------ */

interface HistPoint {
  t: number;
  label: string;
  point: number | null;
  lo: number | null;
  hi: number | null;
  venture: string | null;
  reason: string | null;
}

function normalizeHistory(history: Json): HistPoint[] {
  return arr(history)
    .map((h: Json) => {
      const ts =
        h?.observed_at ?? h?.created_at ?? h?.asof ?? h?.at ?? h?.date ?? null;
      const t = ts ? new Date(ts).getTime() : NaN;
      const point =
        qval(h?.point) ?? qval(h?.value) ?? qval(h?.score) ?? null;
      const iv = h?.interval;
      const lo = Array.isArray(iv) ? Number(iv[0]) : qval(h?.interval_low);
      const hi = Array.isArray(iv) ? Number(iv[1]) : qval(h?.interval_high);
      return {
        t: Number.isNaN(t) ? 0 : t,
        label: ts ? fmtDate(ts) : String(h?.version ?? ""),
        point,
        lo: lo ?? null,
        hi: hi ?? null,
        venture: h?.org_name ?? h?.org_id ?? h?.venture ?? null,
        reason: h?.reason ?? h?.note ?? h?.event ?? null,
      };
    })
    .filter((h) => h.point !== null || h.lo !== null)
    .sort((a, b) => a.t - b.t);
}

/**
 * The Founder Score is per-person, append-only, and NEVER resets. Rendering it
 * as a step function across two ventures is the point: the line does not go
 * back to zero when the company changes, because the schema has no mechanism
 * that would let it.
 */
export function ScoreHistoryChart({ history }: { history: Json }) {
  const pts = normalizeHistory(history);
  if (pts.length < 2) {
    return (
      <EmptyState
        text={
          pts.length === 1
            ? "One scored version so far — a step function needs at least two."
            : "No founder score history at this asof."
        }
      />
    );
  }

  const W = 720;
  const H = 220;
  const PAD = { l: 34, r: 12, t: 14, b: 30 };
  const innerW = W - PAD.l - PAD.r;
  const innerH = H - PAD.t - PAD.b;

  const t0 = pts[0].t;
  const t1 = pts[pts.length - 1].t;
  const tSpan = t1 - t0 || 1;

  const allVals = pts.flatMap((p) =>
    [p.point, p.lo, p.hi].filter((v): v is number => v !== null)
  );
  const vMin = Math.max(0, Math.min(...allVals) - 8);
  const vMax = Math.min(100, Math.max(...allVals) + 8);
  const vSpan = vMax - vMin || 1;

  const x = (t: number) => PAD.l + ((t - t0) / tSpan) * innerW;
  const y = (v: number) => PAD.t + innerH - ((v - vMin) / vSpan) * innerH;

  // Step path: hold the previous value until the next observation lands.
  const stepPath: string[] = [];
  pts.forEach((p, i) => {
    if (p.point === null) return;
    const px = x(p.t);
    const py = y(p.point);
    if (!stepPath.length) stepPath.push(`M ${px} ${py}`);
    else {
      const prev = pts[i - 1];
      if (prev?.point !== null && prev !== undefined) {
        stepPath.push(`L ${px} ${y(prev.point!)}`);
      }
      stepPath.push(`L ${px} ${py}`);
    }
  });

  // Interval ribbon
  const band = pts.filter((p) => p.lo !== null && p.hi !== null);
  let bandPath = "";
  if (band.length >= 2) {
    const top = band.map((p, i) => {
      const cmd = i === 0 ? "M" : "L";
      const prev = band[i - 1];
      return i === 0
        ? `${cmd} ${x(p.t)} ${y(p.hi!)}`
        : `L ${x(p.t)} ${y(prev.hi!)} L ${x(p.t)} ${y(p.hi!)}`;
    });
    const bot = [...band]
      .reverse()
      .map((p, i, a) => {
        const prev = a[i - 1];
        return i === 0
          ? `L ${x(p.t)} ${y(p.lo!)}`
          : `L ${x(prev.t)} ${y(p.lo!)} L ${x(p.t)} ${y(p.lo!)}`;
      });
    bandPath = [...top, ...bot, "Z"].join(" ");
  }

  // Venture boundaries
  const boundaries: { t: number; from: string | null; to: string | null }[] = [];
  for (let i = 1; i < pts.length; i++) {
    if (pts[i].venture && pts[i].venture !== pts[i - 1].venture) {
      boundaries.push({
        t: pts[i].t,
        from: pts[i - 1].venture,
        to: pts[i].venture,
      });
    }
  }

  const ticks = [vMin, (vMin + vMax) / 2, vMax];

  return (
    <div className="w-full overflow-x-auto">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full min-w-[560px]"
        role="img"
        aria-label="Founder score history across ventures"
      >
        {ticks.map((tv) => (
          <g key={tv}>
            <line
              x1={PAD.l}
              x2={W - PAD.r}
              y1={y(tv)}
              y2={y(tv)}
              stroke="#27323a"
              strokeWidth="1"
            />
            <text
              x={PAD.l - 6}
              y={y(tv) + 3}
              textAnchor="end"
              className="fill-zinc-600"
              style={{ fontSize: 9, fontFamily: "monospace" }}
            >
              {tv.toFixed(0)}
            </text>
          </g>
        ))}

        {/* The interval ribbon sits behind the line and must stay behind it:
            filled too strongly it reads as a solid block and the step — the
            actual subject of the chart — disappears into it. */}
        {bandPath ? (
          <path
            d={bandPath}
            fill="rgba(63,169,138,0.10)"
            stroke="rgba(99,193,163,0.35)"
            strokeWidth="1"
          />
        ) : null}

        {boundaries.map((b, i) => (
          <g key={i}>
            <line
              x1={x(b.t)}
              x2={x(b.t)}
              y1={PAD.t}
              y2={PAD.t + innerH}
              stroke="#d5a955"
              strokeWidth="1"
              strokeDasharray="3 3"
            />
            <text
              x={x(b.t) + 4}
              y={PAD.t + 10}
              className="fill-amber-400"
              style={{ fontSize: 9 }}
            >
              new venture — score carries over
            </text>
          </g>
        ))}

        {stepPath.length ? (
          <path
            d={stepPath.join(" ")}
            fill="none"
            stroke="#f1efe9"
            strokeWidth="2.25"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        ) : null}

        {pts.map((p, i) =>
          p.point !== null ? (
            <g key={i}>
              <circle
                cx={x(p.t)}
                cy={y(p.point)}
                r="3.5"
                fill="#f1efe9"
                stroke="#0a0e11"
                strokeWidth="1.5"
              />
              <title>
                {`${p.label} · ${fmtNum(p.point)}${
                  p.lo !== null && p.hi !== null
                    ? ` [${fmtNum(p.lo)}, ${fmtNum(p.hi)}]`
                    : ""
                }${p.venture ? ` · ${p.venture}` : ""}${
                  p.reason ? ` · ${p.reason}` : ""
                }`}
              </title>
            </g>
          ) : null
        )}

        <text
          x={PAD.l}
          y={H - 8}
          className="fill-zinc-600"
          style={{ fontSize: 9, fontFamily: "monospace" }}
        >
          {pts[0].label}
        </text>
        <text
          x={W - PAD.r}
          y={H - 8}
          textAnchor="end"
          className="fill-zinc-600"
          style={{ fontSize: 9, fontFamily: "monospace" }}
        >
          {pts[pts.length - 1].label}
        </text>
      </svg>

      <ol className="mt-2 space-y-1">
        {pts.map((p, i) => (
          <li
            key={i}
            className="flex flex-wrap items-baseline gap-x-2 border-b border-zinc-900 py-1 text-[11.5px]"
          >
            <span className="font-mono text-zinc-500">{p.label}</span>
            <span className="font-mono tabular-nums text-zinc-200">
              {fmtNum(p.point)}
            </span>
            {p.lo !== null && p.hi !== null ? (
              <span className="font-mono text-[10.5px] text-zinc-500">
                [{fmtNum(p.lo)}, {fmtNum(p.hi)}]
              </span>
            ) : null}
            {p.venture ? (
              <span className="text-zinc-500">· {p.venture}</span>
            ) : null}
            {p.reason ? (
              <span className="text-zinc-400">— {p.reason}</span>
            ) : null}
          </li>
        ))}
      </ol>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Horizontal error-bar chart — Days of Edge                           */
/* ------------------------------------------------------------------ */

export function ErrorBarChart({
  rows,
  valueKey = "median_days",
  labelKey = "channel",
}: {
  rows: Json[];
  valueKey?: string;
  labelKey?: string;
}) {
  const list = arr(rows);
  if (!list.length) return <EmptyState />;

  const vals = list.flatMap((r) => {
    const q = r?.[valueKey];
    const v = qval(q);
    const ci = isObj(q) && Array.isArray(q.ci) ? q.ci : null;
    return [v, ci?.[0], ci?.[1]].filter(
      (x): x is number => typeof x === "number" && Number.isFinite(x)
    );
  });
  const max = Math.max(10, ...vals);

  return (
    <div className="space-y-1.5">
      {list.map((r, i) => {
        const q = r?.[valueKey];
        const v = qval(q);
        const n = isObj(q) ? q.n : null;
        const ci = isObj(q) && Array.isArray(q.ci) ? q.ci : null;
        const declined = r?.kind === "declined" || r?.status === "defunded";
        const thin = !!r?.thin_cell;

        const pct = (x: number) => clamp((x / max) * 100, 0, 100);

        return (
          <div
            key={r?.channel_id ?? i}
            className={`grid grid-cols-1 items-center gap-x-3 gap-y-1 border-b border-zinc-900 py-2 sm:grid-cols-[minmax(0,18rem)_1fr] ${
              declined ? "opacity-45" : ""
            }`}
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="truncate text-[12.5px] text-zinc-200">
                  {r?.[labelKey] ?? r?.channel_id ?? "—"}
                </span>
                {declined ? (
                  <span className="rounded border border-zinc-600 px-1 font-mono text-[9px] uppercase text-zinc-400">
                    defunded
                  </span>
                ) : null}
                {thin ? (
                  <span
                    className="rounded border border-amber-500/40 bg-amber-500/10 px-1 font-mono text-[9px] uppercase text-amber-300"
                    title="n is too thin to be confident. The error bar says so."
                  >
                    thin
                  </span>
                ) : null}
              </div>
              {r?.kind ? (
                <span className="text-[10.5px] text-zinc-600">{r.kind}</span>
              ) : null}
            </div>

            <div className="flex items-center gap-3">
              <div className="relative h-5 flex-1 rounded bg-zinc-900">
                {ci && typeof ci[0] === "number" && typeof ci[1] === "number" ? (
                  <div
                    className="absolute top-1/2 h-[1.5px] -translate-y-1/2 bg-zinc-600"
                    style={{
                      left: `${pct(ci[0])}%`,
                      width: `${Math.max(pct(ci[1]) - pct(ci[0]), 0.4)}%`,
                    }}
                    title={`95% interval [${ci[0]}, ${ci[1]}]`}
                  />
                ) : null}
                {ci
                  ? [ci[0], ci[1]].map((c, k) =>
                      typeof c === "number" ? (
                        <div
                          key={k}
                          className="absolute top-1/2 h-2.5 w-[1.5px] -translate-y-1/2 bg-zinc-600"
                          style={{ left: `${pct(c)}%` }}
                        />
                      ) : null
                    )
                  : null}
                {v !== null ? (
                  <div
                    className={`absolute top-1/2 h-3.5 -translate-y-1/2 rounded-sm ${
                      declined ? "bg-zinc-600" : "bg-sky-500"
                    }`}
                    style={{ left: 0, width: `${Math.max(pct(v), 0.6)}%` }}
                  />
                ) : null}
                {/* n printed inside every bar */}
                <span className="absolute left-1.5 top-1/2 -translate-y-1/2 font-mono text-[9.5px] text-zinc-950/90 mix-blend-normal">
                  {n !== null && n !== undefined ? `n=${n}` : ""}
                </span>
              </div>
              <span className="w-16 shrink-0 text-right font-mono text-[12px] tabular-nums text-zinc-200">
                {v === null ? "—" : `${fmtNum(v, 0)}d`}
              </span>
            </div>

            {(r?.note || r?.rationale || r?.limitation || r?.recommendation) && (
              <p className="text-[11.5px] leading-relaxed text-zinc-500 sm:col-start-2">
                {r.recommendation ?? r.rationale ?? r.limitation ?? r.note}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stacked claim distribution bar                                      */
/* ------------------------------------------------------------------ */

const DIST_COLORS: Record<string, string> = {
  verified: "bg-emerald-500",
  unverified: "bg-amber-500",
  contradicted: "bg-rose-500",
  absent_but_expected: "bg-violet-500",
};

export function ClaimDistributionBar({ dist }: { dist: Json }) {
  if (!isObj(dist)) return <EmptyState text="No claim distribution." />;
  const keys = ["verified", "unverified", "contradicted", "absent_but_expected"];
  const counts = keys.map((k) => ({ k, v: Number(dist[k] ?? 0) }));
  const total =
    Number(dist.n ?? 0) || counts.reduce((s, c) => s + (c.v || 0), 0);
  if (!total) return <EmptyState text="No claims extracted yet." />;

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-sm bg-zinc-900">
        {counts.map(({ k, v }) =>
          v > 0 ? (
            <div
              key={k}
              className={DIST_COLORS[k]}
              style={{ width: `${(v / total) * 100}%` }}
              title={`${v} ${k.replace(/_/g, " ")}`}
            />
          ) : null
        )}
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
        {counts.map(({ k, v }) => (
          <span key={k} className="flex items-center gap-1.5 text-[11.5px]">
            <span className={`h-2 w-2 rounded-sm ${DIST_COLORS[k]}`} />
            <span className="font-mono tabular-nums text-zinc-200">{v}</span>
            <span className="text-zinc-500">{k.replace(/_/g, " ")}</span>
          </span>
        ))}
        <span className="ml-auto font-mono text-[11px] text-zinc-500">
          {total} claims · never averaged into a company score
        </span>
      </div>
    </div>
  );
}
