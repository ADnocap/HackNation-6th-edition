import React from "react";
import type { Json } from "@/lib/types";
import {
  arr,
  fmtNum,
  humanize,
  isObj,
  MARKET_STYLE,
  qval,
  titleize,
  TREND,
} from "@/lib/util";
import {
  Badge,
  Bullets,
  EmptyState,
  KVTable,
  N,
  Panel,
  Refusal,
  Stat,
} from "./primitives";
import { IntervalBar } from "./charts";

/* ------------------------------------------------------------------ */
/* Axes                                                                */
/* ------------------------------------------------------------------ */

const AXIS_ORDER = ["founder", "market", "idea_vs_market"];
const AXIS_LABEL: Record<string, string> = {
  founder: "Founder",
  market: "Market",
  idea_vs_market: "Idea vs Market",
};

export function normalizeAxes(person: Json): { key: string; axis: Json }[] {
  const raw =
    person?.axes ?? person?.axis_scores ?? person?.scores ?? person?.axis ?? null;
  if (!raw) return [];

  let list: { key: string; axis: Json }[] = [];
  if (Array.isArray(raw)) {
    list = raw
      .filter(isObj)
      .map((a) => ({ key: String(a.axis ?? a.name ?? a.key ?? ""), axis: a }));
  } else if (isObj(raw)) {
    list = Object.entries(raw)
      .filter(([, v]) => isObj(v))
      .map(([k, v]) => ({ key: k, axis: v as Json }));
  }

  return list.sort((a, b) => {
    const ia = AXIS_ORDER.indexOf(a.key);
    const ib = AXIS_ORDER.indexOf(b.key);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });
}

function TrendChip({ axis }: { axis: Json }) {
  const label = String(axis?.trend ?? axis?.trend_label ?? "");
  if (!label) return null;
  const t = TREND[label] ?? { arrow: "·", cls: "text-zinc-500" };
  const band = axis?.trend_band;
  const nPts = axis?.n_trend_points;

  return (
    <span
      className={`inline-flex items-center gap-1 font-mono text-[11px] ${t.cls}`}
      title={
        Array.isArray(band)
          ? `OLS slope band [${band[0]}, ${band[1]}] — the label is only improving/declining when this band excludes zero.`
          : "Trend is computed by re-scoring at asof −90/−60/−30/0, never asserted."
      }
    >
      <span>{t.arrow}</span>
      <span>{humanize(label)}</span>
      {Array.isArray(band) ? (
        <span className="text-zinc-600">
          [{fmtNum(band[0], 2)}, {fmtNum(band[1], 2)}]
        </span>
      ) : null}
      {nPts !== undefined && nPts !== null ? (
        <span className="text-zinc-600">·{nPts}pts</span>
      ) : null}
    </span>
  );
}

export function AxisCard({
  axisKey,
  axis,
  threshold,
}: {
  axisKey: string;
  axis: Json;
  threshold?: number | null;
}) {
  const isMarket = axisKey === "market";
  const point = qval(axis?.value) ?? qval(axis?.point);
  const interval = axis?.interval ?? null;
  const n = axis?.n ?? axis?.n_observations ?? null;

  // Market is categorical by construction so it structurally cannot be averaged.
  const stance = String(
    axis?.label ?? axis?.stance ?? axis?.category ?? axis?.state ?? ""
  ).toLowerCase();

  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-950/70 p-3.5">
      <div className="flex items-start justify-between gap-2">
        <h3 className="text-[12.5px] font-semibold tracking-wide text-zinc-200">
          {AXIS_LABEL[axisKey] ?? titleize(axisKey)}
        </h3>
        <TrendChip axis={axis} />
      </div>

      <div className="mt-2.5">
        {isMarket ? (
          <div>
            <div
              className={`text-[22px] font-semibold uppercase tracking-tight ${
                MARKET_STYLE[stance] ?? "text-zinc-300"
              }`}
            >
              {stance || "—"}
            </div>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-zinc-500">
              Categorical on purpose. There is no number here to average with the
              other two axes.
            </p>
          </div>
        ) : (
          <>
            <div className="flex items-baseline gap-2">
              <span className="text-[22px] font-semibold tabular-nums text-zinc-100">
                {point === null ? "—" : fmtNum(point, 1)}
              </span>
              {Array.isArray(interval) ? (
                <span className="font-mono text-[11px] text-zinc-500">
                  [{fmtNum(interval[0], 1)}, {fmtNum(interval[1], 1)}]
                </span>
              ) : null}
              {n !== null && n !== undefined ? (
                <span className="rounded bg-zinc-800 px-1 font-mono text-[10px] text-zinc-400">
                  n={n}
                </span>
              ) : (
                <span className="rounded border border-rose-500/60 bg-rose-500/10 px-1 font-mono text-[10px] text-rose-300">
                  n missing
                </span>
              )}
            </div>
            <div className="mt-2.5">
              <IntervalBar
                point={point}
                interval={interval}
                threshold={threshold}
                label={AXIS_LABEL[axisKey] ?? axisKey}
              />
            </div>
          </>
        )}
      </div>

      {axis?.rationale || axis?.note || axis?.reason ? (
        <p className="mt-2.5 border-t border-zinc-900 pt-2 text-[11.5px] leading-relaxed text-zinc-400">
          {axis.rationale ?? axis.note ?? axis.reason}
        </p>
      ) : null}
    </div>
  );
}

export function AxesDisagreeHeadline({
  headline,
  axes,
}: {
  headline: Json;
  axes: { key: string; axis: Json }[];
}) {
  if (!headline) return null;
  return (
    <div className="rounded-md border border-amber-500/50 bg-amber-500/[0.08] px-4 py-3">
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-bold uppercase tracking-widest text-amber-300">
          Axes disagree
        </span>
      </div>
      <p className="mt-1.5 text-[13.5px] leading-relaxed text-amber-100/90">
        {typeof headline === "string" ? headline : headline?.text}
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Cold-Start Bench                                                    */
/* ------------------------------------------------------------------ */

/**
 * The founder with no GitHub, no funding and no network. The bench states the
 * split between direct evidence and the reference-class prior out loud, then
 * names what would narrow the interval — because a wide interval is a request
 * for evidence, not a verdict.
 */
export function ColdStartBench({ bench }: { bench: Json }) {
  if (!isObj(bench)) {
    return (
      <EmptyState text="No cold-start bench block for this person at this asof." />
    );
  }

  const priorWeight = bench.prior_weight ?? bench.w ?? bench.weight_prior;
  const nDirect =
    bench.n_direct ?? bench.n_direct_observations ?? bench.n_evidence ?? bench.n;
  const interval = bench.interval ?? bench.posterior_interval ?? null;
  const point = qval(bench.point) ?? qval(bench.posterior_mean) ?? null;
  const refClass = bench.reference_class ?? bench.class ?? null;
  const narrow =
    bench.what_would_narrow_it ??
    bench.what_would_narrow ??
    bench.narrowing_actions ??
    bench.next_evidence ??
    null;
  const statement = bench.statement ?? bench.plain_line ?? bench.summary ?? null;

  const pw = qval(priorWeight);

  return (
    <div className="space-y-3.5">
      {statement ? (
        <p className="text-[13px] leading-relaxed text-zinc-300">{statement}</p>
      ) : null}

      <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
        <Stat
          label="Prior weight"
          hint="w = n/(n+k). With few direct observations the reference class carries most of the estimate — and we say so."
        >
          {pw === null ? (
            <N q={priorWeight} />
          ) : (
            <span className="tabular-nums">
              {pw <= 1 ? `${(pw * 100).toFixed(0)}%` : fmtNum(pw)}
            </span>
          )}
        </Stat>
        <Stat label="Direct observations">
          <N q={nDirect} digits={0} />
        </Stat>
        <Stat label="Point">
          {point === null ? (
            <span className="text-zinc-600">—</span>
          ) : (
            <span className="tabular-nums">{fmtNum(point)}</span>
          )}
        </Stat>
        <Stat label="Interval">
          {Array.isArray(interval) ? (
            <span className="font-mono text-[12px] tabular-nums">
              [{fmtNum(interval[0])}, {fmtNum(interval[1])}]
            </span>
          ) : (
            <span className="text-zinc-600">—</span>
          )}
        </Stat>
      </div>

      {/* Weight split bar */}
      {pw !== null && pw <= 1 ? (
        <div>
          <div className="flex h-2.5 overflow-hidden rounded-sm bg-zinc-900">
            <div
              className="bg-sky-500"
              style={{ width: `${(1 - pw) * 100}%` }}
              title="Direct evidence"
            />
            <div
              className="bg-zinc-600"
              style={{ width: `${pw * 100}%` }}
              title="Reference-class prior"
            />
          </div>
          <div className="mt-1 flex justify-between text-[10.5px] text-zinc-500">
            <span>direct evidence {((1 - pw) * 100).toFixed(0)}%</span>
            <span>reference-class prior {(pw * 100).toFixed(0)}%</span>
          </div>
        </div>
      ) : null}

      {isObj(refClass) ? (
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
            Reference class — contains no pedigree field
          </div>
          <KVTable obj={refClass} />
        </div>
      ) : typeof refClass === "string" ? (
        <p className="text-[12px] text-zinc-400">
          Reference class: <span className="text-zinc-300">{refClass}</span>
        </p>
      ) : null}

      {narrow ? (
        <div>
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-zinc-500">
            Here is what would narrow it
          </div>
          <Bullets items={narrow} />
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Expected-evidence manifest                                          */
/* ------------------------------------------------------------------ */

/**
 * The load-bearing asymmetry: missing expected evidence WIDENS the interval and
 * never lowers the score. Absence the findability prior predicted for this
 * resource class is stamped "not expected for this founder profile — not
 * penalised" and rendered grey. This is what stops the system re-encoding the
 * network gate.
 */
export function ManifestChecklist({ manifest }: { manifest: Json }) {
  const rows = arr(
    isObj(manifest) ? manifest.rows ?? manifest.items ?? manifest.artifacts : manifest
  );
  if (!rows.length) {
    return <EmptyState text="No expected-evidence manifest at this asof." />;
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left">
        <thead>
          <tr className="border-b border-zinc-800 text-[10px] uppercase tracking-wider text-zinc-500">
            <th className="py-1.5 pr-3 font-medium">Artifact</th>
            <th className="py-1.5 pr-3 font-medium">Found</th>
            <th className="py-1.5 pr-3 font-medium">Expected</th>
            <th className="py-1.5 pr-3 font-medium">Findability prior</th>
            <th className="py-1.5 font-medium">Effect on the estimate</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r: Json, i: number) => {
            const found = r?.found === true;
            const expected = r?.expected === true;
            const penalised = r?.penalised === true;
            const notExpected = !expected;

            return (
              <tr
                key={r?.evidence_id ?? r?.artifact_type ?? i}
                className={`border-b border-zinc-900 align-top ${
                  notExpected ? "opacity-50" : ""
                }`}
              >
                <td className="py-2 pr-3">
                  <div className="text-[12.5px] text-zinc-200">
                    {humanize(r?.artifact_type ?? r?.label ?? r?.name)}
                  </div>
                  {r?.note ? (
                    <div className="mt-0.5 text-[11px] leading-snug text-zinc-500">
                      {r.note}
                    </div>
                  ) : null}
                </td>
                <td className="py-2 pr-3">
                  {found ? (
                    <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
                      found
                    </Badge>
                  ) : (
                    <Badge className="border-zinc-700 bg-zinc-900 text-zinc-400">
                      absent
                    </Badge>
                  )}
                </td>
                <td className="py-2 pr-3">
                  {expected ? (
                    <span className="text-[12px] text-zinc-300">expected</span>
                  ) : (
                    <span
                      className="text-[11.5px] italic text-zinc-500"
                      title="Absence the findability prior predicted for this resource class."
                    >
                      not expected for this founder profile
                    </span>
                  )}
                </td>
                <td className="py-2 pr-3">
                  {r?.findability_prior ? (
                    <N q={r.findability_prior} digits={2} />
                  ) : (
                    <span className="text-zinc-600">—</span>
                  )}
                </td>
                <td className="py-2">
                  {found ? (
                    <span className="text-[11.5px] text-emerald-300">
                      informs the estimate
                    </span>
                  ) : penalised ? (
                    <span
                      className="text-[11.5px] text-amber-300"
                      title="Missing expected evidence widens the interval. It never lowers the score."
                    >
                      widens the interval
                      {qval(r?.interval_widen) !== null
                        ? ` by ${fmtNum(qval(r?.interval_widen))}`
                        : ""}{" "}
                      — score unchanged
                    </span>
                  ) : (
                    <span className="text-[11.5px] text-zinc-500">
                      not penalised
                    </span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <p className="mt-2.5 text-[11.5px] leading-relaxed text-zinc-500">
        Missing evidence widens the interval and never lowers the score. Grey rows
        are absences our findability prior already predicted for this resource
        class, so they cost nothing. That asymmetry is what keeps this from
        re-encoding the network gate.
      </p>
    </div>
  );
}
