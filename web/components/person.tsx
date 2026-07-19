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

export function TrendChip({ axis }: { axis: Json }) {
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
export function ColdStartBench({
  bench,
  blockedReason,
}: {
  bench: Json;
  blockedReason?: Json;
}) {
  if (!isObj(bench)) {
    // ui_rules.refusal_render_rule — a null with a sibling *_blocked_reason MUST
    // render the reason string. Rendering the refusal is the feature.
    if (typeof blockedReason === "string" && blockedReason) {
      return <Refusal>{blockedReason}</Refusal>;
    }
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
  const notNarrow = bench.what_would_not_narrow_it ?? null;
  const narrowedTo = bench.narrowed_to ?? null;
  const narrowedBy = bench.narrowed_by ?? null;

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

      {/* Weight split bar — the load-bearing admission on this page.
          The prior half wears the lacuna hatch, because a prior is what we
          reach for exactly where direct evidence is absent. Saying that in
          the material is more honest than saying it in a footnote. */}
      {pw !== null && pw <= 1 ? (
        <div className="rounded border border-zinc-800 bg-zinc-950/70 p-3">
          <div className="t-eyebrow mb-2">What this estimate is made of</div>
          <div
            className="flex h-5 overflow-hidden rounded-sm border border-zinc-800"
            role="img"
            aria-label={`Direct evidence ${((1 - pw) * 100).toFixed(
              0
            )} percent, reference-class prior ${(pw * 100).toFixed(0)} percent`}
          >
            <div
              className="bg-sky-500/80"
              style={{ width: `${(1 - pw) * 100}%` }}
              title="Direct evidence about this founder"
            />
            <div
              className="lacuna"
              style={{ width: `${pw * 100}%` }}
              title="Reference-class prior — used where direct evidence is absent"
            />
          </div>
          <div className="mt-2 flex flex-wrap justify-between gap-x-4 gap-y-1 text-[11.5px]">
            <span className="flex items-center gap-1.5 text-zinc-300">
              <span className="h-2 w-2 rounded-sm bg-sky-500/80" />
              direct evidence{" "}
              <span className="font-mono tabular-nums text-zinc-100">
                {((1 - pw) * 100).toFixed(0)}%
              </span>
            </span>
            <span className="flex items-center gap-1.5 text-zinc-300">
              <span className="lacuna-chip lacuna h-2 w-4" />
              reference-class prior{" "}
              <span className="font-mono tabular-nums text-zinc-100">
                {(pw * 100).toFixed(0)}%
              </span>
            </span>
          </div>
          {bench.prior_weight_formula ? (
            <p className="mt-2 border-t border-zinc-900 pt-2 font-mono text-[10.5px] leading-relaxed text-zinc-400">
              {bench.prior_weight_formula}
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Evidence bought certainty, not a higher score. */}
      {Array.isArray(narrowedTo) ? (
        <div className="rounded border border-emerald-500/30 bg-emerald-500/[0.06] p-3">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
            <span className="text-[10px] uppercase tracking-wider text-emerald-400">
              Interval narrowed
            </span>
            <span className="font-mono text-[12px] tabular-nums text-zinc-200">
              [{fmtNum(narrowedTo[0])}, {fmtNum(narrowedTo[1])}]
            </span>
            {narrowedBy ? (
              <span className="font-mono text-[11px] text-zinc-400">
                by <N q={narrowedBy} />
              </span>
            ) : null}
          </div>
          {bench.interval_note ? (
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-zinc-400">
              {bench.interval_note}
            </p>
          ) : null}
        </div>
      ) : bench.interval_note ? (
        <p className="text-[11.5px] leading-relaxed text-zinc-500">
          {bench.interval_note}
        </p>
      ) : null}

      {isObj(refClass) ? (
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
          <div className="mb-1.5 t-eyebrow">
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
          <div className="mb-1.5 t-eyebrow">
            Here is what would narrow it
          </div>
          <Bullets items={narrow} />
        </div>
      ) : null}

      {notNarrow ? (
        <div>
          <div className="mb-1.5 t-eyebrow">
            And what would not
          </div>
          <div className="opacity-60">
            <Bullets items={notNarrow} />
          </div>
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

  // Three kinds of row, and only one of them costs anything.
  const kindOf = (r: Json): "found" | "priced" | "unpriced" => {
    if (r?.found === true) return "found";
    return r?.expected === true && r?.penalised === true ? "priced" : "unpriced";
  };

  const nFound = rows.filter((r: Json) => kindOf(r) === "found").length;
  const nPriced = rows.filter((r: Json) => kindOf(r) === "priced").length;
  const nUnpriced = rows.filter((r: Json) => kindOf(r) === "unpriced").length;

  // Total width bought by absence — the honest price of the gaps.
  const totalWiden = rows.reduce((s: number, r: Json) => {
    const w = qval(r?.interval_widen);
    return s + (w ?? 0);
  }, 0);

  const maxWiden = Math.max(
    0.1,
    ...rows.map((r: Json) => Math.abs(qval(r?.interval_widen) ?? 0))
  );

  return (
    <div>
      {/* The ledger of the manifest itself, before the rows. */}
      <div className="mb-3 flex flex-wrap items-center gap-x-6 gap-y-2 border-b border-zinc-800 pb-3">
        <span className="flex items-baseline gap-1.5">
          <span className="font-mono text-[17px] tabular-nums text-emerald-300">
            {nFound}
          </span>
          <span className="text-[11.5px] text-zinc-400">found</span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="font-mono text-[17px] tabular-nums text-violet-300">
            {nPriced}
          </span>
          <span className="text-[11.5px] text-zinc-400">
            expected, not found
          </span>
        </span>
        <span className="flex items-baseline gap-1.5">
          <span className="font-mono text-[17px] tabular-nums text-zinc-400">
            {nUnpriced}
          </span>
          <span className="text-[11.5px] text-zinc-400">not expected</span>
        </span>
        {totalWiden > 0 ? (
          <span className="ml-auto font-mono text-[11px] text-zinc-400">
            absence bought{" "}
            <span className="text-violet-300">+{fmtNum(totalWiden, 1)}</span> of
            interval width — and nothing off the score
          </span>
        ) : null}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-left">
          <caption className="sr-only">
            Expected-evidence manifest: what we looked for, what we found, and
            how each absence was priced.
          </caption>
          <thead>
            <tr className="border-b border-zinc-800">
              <th scope="col" className="t-eyebrow py-2 pr-3 text-left">
                Artifact
              </th>
              <th scope="col" className="t-eyebrow py-2 pr-3 text-left">
                Status
              </th>
              <th scope="col" className="t-eyebrow py-2 pr-3 text-left">
                P(findable) if it existed
              </th>
              <th scope="col" className="t-eyebrow py-2 text-left">
                Effect on the estimate
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r: Json, i: number) => {
              const kind = kindOf(r);
              const widen = qval(r?.interval_widen);
              const prior = qval(
                isObj(r?.findability_prior)
                  ? r.findability_prior.value
                  : r?.findability_prior
              );

              // Absence is hatched, never faded. A row you can barely read is
              // not a row the investor can act on — and acting on the gaps is
              // the entire proposition.
              const rowCls =
                kind === "priced"
                  ? "lacuna-priced"
                  : kind === "unpriced"
                  ? "lacuna"
                  : "";

              return (
                <tr
                  key={r?.evidence_id ?? r?.artifact_type ?? i}
                  className={`border-b border-zinc-900 align-top ${rowCls}`}
                >
                  <td className="py-2.5 pr-3">
                    <div className="flex items-baseline gap-2">
                      <span
                        aria-hidden
                        className={`font-mono text-[11px] ${
                          kind === "found"
                            ? "text-emerald-400"
                            : kind === "priced"
                            ? "text-violet-400"
                            : "text-zinc-500"
                        }`}
                      >
                        {kind === "found" ? "✓" : "▨"}
                      </span>
                      <span className="text-[12.5px] text-zinc-100">
                        {humanize(r?.artifact_type ?? r?.label ?? r?.name)}
                      </span>
                    </div>
                    {r?.note ? (
                      <div className="mt-1 max-w-[56ch] pl-[19px] text-[11px] leading-relaxed text-zinc-400">
                        {r.note}
                      </div>
                    ) : null}
                  </td>

                  <td className="py-2.5 pr-3">
                    {kind === "found" ? (
                      <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
                        found
                      </Badge>
                    ) : kind === "priced" ? (
                      <Badge
                        className="border-violet-500/40 bg-violet-500/10 text-violet-200"
                        title="We expected this for a founder with this profile and did not find it. It is priced as width."
                      >
                        expected · absent
                      </Badge>
                    ) : (
                      <span
                        className="text-[11.5px] leading-snug text-zinc-300"
                        title="Absence the findability prior already predicted for this resource class."
                      >
                        not expected for
                        <br />
                        this founder profile
                      </span>
                    )}
                  </td>

                  <td className="py-2.5 pr-3">
                    {r?.findability_prior ? (
                      <div className="w-[7.5rem]">
                        <N q={r.findability_prior} digits={2} />
                        {prior !== null && prior >= 0 && prior <= 1 ? (
                          <div
                            className="mt-1.5 h-1 w-full rounded-full bg-zinc-800"
                            aria-hidden
                          >
                            <div
                              className="h-1 rounded-full bg-zinc-500"
                              style={{ width: `${prior * 100}%` }}
                            />
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <span className="text-zinc-600">—</span>
                    )}
                  </td>

                  <td className="py-2.5">
                    {kind === "found" ? (
                      <span className="text-[11.5px] text-emerald-300">
                        informs the estimate
                      </span>
                    ) : kind === "priced" ? (
                      <div>
                        <span className="text-[11.5px] text-violet-200">
                          widens the interval
                          {widen !== null ? (
                            <span className="font-mono tabular-nums">
                              {" "}
                              +{fmtNum(widen, 1)}
                            </span>
                          ) : null}{" "}
                          — score unchanged
                        </span>
                        {widen !== null && widen > 0 ? (
                          <div
                            className="mt-1.5 h-1 w-full max-w-[9rem] rounded-full bg-zinc-800"
                            aria-hidden
                          >
                            <div
                              className="h-1 rounded-full bg-violet-400"
                              style={{
                                width: `${Math.max(
                                  (Math.abs(widen) / maxWiden) * 100,
                                  4
                                )}%`,
                              }}
                            />
                          </div>
                        ) : null}
                      </div>
                    ) : (
                      <span className="text-[11.5px] text-zinc-300">
                        not penalised — costs nothing
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <p className="mt-3 max-w-[74ch] border-t border-zinc-800 pt-3 text-[12px] leading-[1.65] text-zinc-300">
        Missing evidence widens the interval and never lowers the score. Hatched
        rows are absences — the graphite ones our findability prior already
        predicted for this resource class, so they cost nothing. That asymmetry
        is what keeps this from re-encoding the network gate: a founder is never
        marked down for lacking artifacts that someone in their position would
        not be expected to have.
      </p>
    </div>
  );
}
