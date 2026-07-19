import React from "react";
import type { Json } from "@/lib/types";
import { Badge, EmptyState, N, Panel, Refusal, Stat } from "./primitives";
import { ErrorBarChart } from "./charts";
import { arr, fmtNum, fmtTs, humanize, isObj, titleize } from "@/lib/util";

/* ------------------------------------------------------------------ */
/* Days of Edge                                                        */
/* ------------------------------------------------------------------ */

export function DaysOfEdge({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  const rows = arr(block.rows);

  return (
    <Panel
      title={block.title ?? "Days of Edge"}
      plain={
        block.plain_language ??
        "How many days earlier this channel finds someone than the market does."
      }
      right={
        block.asof ? (
          <span className="font-mono text-[10.5px] text-zinc-500">
            asof {fmtTs(block.asof)}
          </span>
        ) : null
      }
    >
      {block.design_rule ? (
        <div className="mb-3 rounded border border-zinc-800 bg-zinc-900/50 px-3 py-2 text-[12px] leading-relaxed text-zinc-300">
          <span className="mr-1.5 font-mono t-eyebrow">
            design rule
          </span>
          {block.design_rule}
        </div>
      ) : null}

      {rows.length ? (
        <ErrorBarChart rows={rows} valueKey="median_days" labelKey="channel" />
      ) : (
        <EmptyState text="No channels measured at this asof." />
      )}

      {/* Per-row prose: the limitations and the defunding argument. */}
      <div className="mt-3 space-y-2">
        {rows
          .filter(
            (r: Json) =>
              r?.rationale || r?.limitation || r?.note || r?.recommendation
          )
          .map((r: Json, i: number) => (
            <div
              key={r?.channel_id ?? i}
              className={`rounded border px-3 py-2 ${
                r?.kind === "declined" || r?.status === "defunded"
                  ? "border-rose-500/30 bg-rose-500/[0.05]"
                  : r?.thin_cell
                  ? "border-amber-500/30 bg-amber-500/[0.05]"
                  : "border-zinc-800 bg-zinc-950"
              }`}
            >
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[12.5px] font-medium text-zinc-200">
                  {r?.channel ?? r?.channel_id ?? "—"}
                </span>
                {r?.kind ? (
                  <Badge className="border-zinc-700 bg-zinc-900 text-zinc-500">
                    {humanize(r.kind)}
                  </Badge>
                ) : null}
                {r?.cold_start_native ? (
                  <Badge
                    className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                    title="Can fire for a person with no GitHub, no funding and no network."
                  >
                    cold-start native
                  </Badge>
                ) : null}
                {r?.thin_cell ? (
                  <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-300">
                    thin n
                  </Badge>
                ) : null}
                {r?.status === "defunded" ? (
                  <Badge className="border-rose-500/50 bg-rose-500/10 text-rose-300">
                    defunded
                  </Badge>
                ) : null}
              </div>
              <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">
                {r?.rationale ?? r?.limitation ?? r?.recommendation ?? r?.note}
              </p>
            </div>
          ))}
      </div>

      {block.method ? (
        <p className="mt-3 border-t border-zinc-900 pt-2 text-[11.5px] leading-relaxed text-zinc-500">
          <span className="mr-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
            method
          </span>
          {block.method}
        </p>
      ) : null}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Channel outcomes — deliberately empty                               */
/* ------------------------------------------------------------------ */

export function ChannelOutcomes({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  const rows = arr(block.rows);
  const cols = arr(block.schema_columns);

  return (
    <Panel
      title={block.title ?? "Channel quality by funded outcome"}
      plain="We have not funded anyone yet, so this table is empty. We are showing you the empty table and its schema rather than a number we could not have earned."
    >
      {rows.length ? (
        <EmptyState text="Rows present — render pending schema confirmation." />
      ) : (
        <>
          <Refusal>
            {block.display ??
              "0 funded outcomes. This is why we do not rank channels on quality yet — here is the schema that would."}
          </Refusal>
          {cols.length ? (
            <div className="mt-3 overflow-x-auto rounded border border-zinc-800">
              <table className="w-full text-[11.5px]">
                <thead>
                  <tr className="border-b border-zinc-800 text-left t-eyebrow">
                    {cols.map((c: Json, i: number) => (
                      <th key={i} className="px-3 py-1.5 font-medium">
                        {String(c)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td
                      colSpan={cols.length}
                      className="px-3 py-4 text-center text-[12px] italic text-zinc-600"
                    >
                      no rows — fills over 18 months
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          ) : null}
        </>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Not collected, and why                                              */
/* ------------------------------------------------------------------ */

const REASON_STYLE: Record<string, string> = {
  pedigree_proxy: "border-rose-500/40 bg-rose-500/10 text-rose-300",
  measures_already_visible: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  auth_wall: "border-zinc-600 bg-zinc-900 text-zinc-400",
  js_rendering: "border-zinc-600 bg-zinc-900 text-zinc-400",
  tos_risk: "border-violet-500/40 bg-violet-500/10 text-violet-300",
  out_of_scope: "border-zinc-700 bg-zinc-900 text-zinc-500",
};

export function NotCollected({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  const rows = arr(block.rows);

  return (
    <Panel
      title={block.title ?? "Not collected, and why"}
      plain="Every source we chose not to use, with the reason. Sources the challenge brief itself named are flagged, so you find them addressed here rather than missing everywhere."
      right={block.n ? <N q={block.n} digits={0} /> : null}
      dense
    >
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="border-b border-zinc-800 text-left t-eyebrow">
                <th className="px-4 py-1.5 font-medium">Source</th>
                <th className="px-4 py-1.5 font-medium">Reason class</th>
                <th className="px-4 py-1.5 font-medium">Why</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: Json, i: number) => (
                // A source we chose not to collect is a catalogued absence, so
                // it wears the same material as every other absence here.
                <tr
                  key={i}
                  className="lacuna border-b border-zinc-900 align-top last:border-b-0"
                >
                  <td className="px-4 py-2">
                    <div className="text-zinc-100">{r?.source_name ?? "—"}</div>
                    {r?.brief_named ? (
                      <Badge
                        className="mt-1 border-sky-500/40 bg-sky-500/10 text-sky-300"
                        title="Named in the challenge brief as a source to ingest. We declined it and say why."
                      >
                        brief-named
                      </Badge>
                    ) : null}
                  </td>
                  <td className="px-4 py-2">
                    <Badge
                      className={
                        REASON_STYLE[String(r?.reason_class)] ??
                        "border-zinc-700 bg-zinc-900 text-zinc-500"
                      }
                    >
                      {humanize(r?.reason_class)}
                    </Badge>
                  </td>
                  <td className="max-w-2xl px-4 py-2 leading-relaxed text-zinc-300">
                    {r?.reason_text ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="p-4">
          <EmptyState text="No declined sources recorded." />
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Recognition probe                                                   */
/* ------------------------------------------------------------------ */

export function RecognitionProbe({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  const leak = block.leak_rate;
  const rate =
    isObj(leak) && typeof leak.value === "number" ? leak.value : null;

  return (
    <Panel
      title={block.title ?? "Recognition probe — model leakage on pre-fame artifacts"}
      plain={
        block.plain_language ??
        "Before claiming a hit rate, we tested whether the model already knows the answer. It does."
      }
      right={
        block.run_at ? (
          <span className="font-mono text-[10.5px] text-zinc-500">
            run {fmtTs(block.run_at)}
          </span>
        ) : null
      }
    >
      <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
        <div>
          <div className="t-eyebrow">
            Leak rate
          </div>
          <div className="mt-0.5 flex items-baseline gap-2">
            <span className="text-[26px] font-semibold tabular-nums leading-none text-rose-300">
              {rate !== null ? `${(rate * 100).toFixed(0)}%` : "—"}
            </span>
            {isObj(leak) ? <N q={leak} digits={2} hideN={false} /> : null}
          </div>
          {isObj(leak) && leak.basis ? (
            <div className="mt-1 font-mono text-[10px] text-zinc-500">
              {String(leak.basis)}
            </div>
          ) : null}
        </div>

        {block.n_artifacts ? (
          <Stat label="Artifacts shown">
            <N q={block.n_artifacts} digits={0} />
          </Stat>
        ) : null}
        {block.n_identified ? (
          <Stat label="Model identified">
            <N q={block.n_identified} digits={0} />
          </Stat>
        ) : null}
      </div>

      {block.statement ? (
        <p className="mt-3 rounded border-l-2 border-rose-500/50 bg-rose-500/[0.05] px-3 py-2 text-[13px] leading-relaxed text-zinc-200">
          {block.statement}
        </p>
      ) : null}

      {arr(block.examples).length ? (
        <div className="mt-3 overflow-x-auto rounded border border-zinc-800">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-zinc-800 text-left t-eyebrow">
                <th className="px-3 py-1.5 font-medium">Redacted artifact</th>
                <th className="px-3 py-1.5 font-medium">Identified</th>
                <th className="px-3 py-1.5 font-medium">Model answer</th>
              </tr>
            </thead>
            <tbody>
              {arr(block.examples).map((e: Json, i: number) => (
                <tr key={e?.artifact_id ?? i} className="border-b border-zinc-900 last:border-b-0">
                  <td className="px-3 py-1.5 italic text-zinc-300">
                    “{e?.redacted_excerpt ?? "—"}”
                  </td>
                  <td className="px-3 py-1.5">
                    {e?.identified ? (
                      <span className="text-rose-400">leaked</span>
                    ) : (
                      <span className="text-emerald-400">clean</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-[11px] text-zinc-400">
                    {e?.model_answer ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}

      {block.method ? (
        <p className="mt-2.5 text-[11.5px] leading-relaxed text-zinc-500">
          <span className="mr-1.5 font-mono text-[10px] uppercase tracking-wider text-zinc-600">
            method
          </span>
          {block.method}
        </p>
      ) : null}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Source reliability table                                            */
/* ------------------------------------------------------------------ */

export function ReliabilityTable({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  const rows = arr(block.rows);
  const maxAbs = Math.max(
    1,
    ...rows.map((r: Json) => Math.abs(Number(r?.log_odds) || 0))
  );

  return (
    <Panel
      title={block.title ?? "Source reliability"}
      plain={
        block.plain_line ??
        "These weights are ours. We set them by hand, we print them, and we will argue any row."
      }
      right={block.n_rows ? <N q={block.n_rows} digits={0} /> : null}
    >
      <div className="space-y-1">
        {rows.map((r: Json, i: number) => {
          const v = Number(r?.log_odds) || 0;
          const pct = (Math.abs(v) / maxAbs) * 50;
          return (
            <div
              key={i}
              className="grid grid-cols-[minmax(0,10rem)_minmax(0,10rem)_1fr] items-start gap-3 border-b border-zinc-900 py-1.5 last:border-b-0"
            >
              <div className="font-mono text-[11.5px] text-zinc-300">
                {r?.source_class ?? "—"}
              </div>
              <div className="flex items-center gap-2">
                <div className="relative h-3 flex-1 rounded-sm bg-zinc-900">
                  <div className="absolute inset-y-0 left-1/2 w-px bg-zinc-700" />
                  <div
                    className={`absolute inset-y-0 ${
                      v >= 0 ? "bg-emerald-500/70" : "bg-rose-500/70"
                    }`}
                    style={
                      v >= 0
                        ? { left: "50%", width: `${pct}%` }
                        : { right: "50%", width: `${pct}%` }
                    }
                  />
                </div>
                <span
                  className={`w-9 shrink-0 text-right font-mono text-[11px] tabular-nums ${
                    v >= 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {v >= 0 ? `+${v.toFixed(1)}` : v.toFixed(1)}
                </span>
              </div>
              <div className="text-[12px] leading-relaxed text-zinc-400">
                {r?.rationale ?? ""}
              </div>
            </div>
          );
        })}
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 border-t border-zinc-900 pt-2 font-mono text-[10.5px] text-zinc-500">
        {isObj(block.thresholds) ? (
          <span>
            verified ≥ {fmtNum(block.thresholds.verified, 1)} · contradicted ≤{" "}
            {fmtNum(block.thresholds.contradicted, 1)}
          </span>
        ) : null}
        {isObj(block.confidence_mapping)
          ? ["high", "medium", "low"]
              .filter((k) => block.confidence_mapping[k])
              .map((k) => (
                <span key={k}>
                  {k}: {String(block.confidence_mapping[k])}
                </span>
              ))
          : null}
      </div>
      {isObj(block.confidence_mapping) && block.confidence_mapping.note ? (
        <p className="mt-1.5 text-[11.5px] italic leading-relaxed text-zinc-500">
          {String(block.confidence_mapping.note)}
        </p>
      ) : null}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Research area 3 design                                              */
/* ------------------------------------------------------------------ */

const RA3_FIELDS: { key: string; label: string }[] = [
  { key: "outcome_variable", label: "Outcome variable" },
  { key: "cohort_construction", label: "Cohort construction" },
  { key: "selection_diagnosis", label: "Selection diagnosis" },
  { key: "leakage_control", label: "Leakage control" },
  { key: "power_sketch", label: "Power sketch" },
];

export function ResearchDesign({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  return (
    <Panel
      title={
        block.title ??
        "How we would test whether public footprints predict founder success"
      }
      plain="Design only. Not run. The brief asks us to document the approach, so here is the approach and the reason it is not a result."
      right={block.n_words ? <N q={block.n_words} digits={0} unit=" words" /> : null}
    >
      {block.note ? (
        <p className="mb-3 text-[12px] italic text-zinc-500">{String(block.note)}</p>
      ) : null}
      <dl className="space-y-2.5">
        {RA3_FIELDS.filter((f) => block[f.key]).map((f) => (
          <div key={f.key}>
            <dt className="t-eyebrow">
              {f.label}
            </dt>
            <dd className="mt-0.5 max-w-4xl text-[12.5px] leading-relaxed text-zinc-300">
              {String(block[f.key])}
            </dd>
          </div>
        ))}
      </dl>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Latency — compute, not time-to-decision                             */
/* ------------------------------------------------------------------ */

export function LatencyTable({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  const rows = arr(block.rows);

  // "shown_only_if_real": the tile reads a real batch log or it does not appear.
  if (block.shown_only_if_real && !rows.length) return null;

  const maxP90 = Math.max(
    1,
    ...rows.map((r: Json) => Number(r?.p90_ms) || Number(r?.median_ms) || 0)
  );

  return (
    <Panel
      title={block.title ?? "Compute latency — unattended batch run"}
      plain="This measures how long our code takes, not how long a decision takes. Those two numbers live in different places on purpose and are four orders of magnitude apart."
      right={
        block.run_id ? (
          <span className="font-mono text-[10.5px] text-zinc-500">
            {String(block.run_id)}
          </span>
        ) : null
      }
    >
      {rows.length ? (
        <div className="space-y-1">
          {rows.map((r: Json, i: number) => {
            const med = Number(r?.median_ms) || 0;
            const p90 = Number(r?.p90_ms) || med;
            return (
              <div
                key={i}
                className="grid grid-cols-[minmax(0,14rem)_1fr_auto] items-center gap-3 border-b border-zinc-900 py-1.5 last:border-b-0"
              >
                <span className="font-mono text-[11.5px] text-zinc-300">
                  {r?.step ?? "—"}
                </span>
                <div className="relative h-3 rounded-sm bg-zinc-900">
                  <div
                    className="absolute inset-y-0 left-0 rounded-sm bg-zinc-700"
                    style={{ width: `${(p90 / maxP90) * 100}%` }}
                    title={`p90 ${p90}ms`}
                  />
                  <div
                    className="absolute inset-y-0 left-0 rounded-sm bg-sky-500/80"
                    style={{ width: `${(med / maxP90) * 100}%` }}
                    title={`median ${med}ms`}
                  />
                </div>
                <span className="shrink-0 font-mono text-[11px] tabular-nums text-zinc-400">
                  {med}ms
                  <span className="ml-1.5 text-zinc-600">p90 {p90}ms</span>
                  <span className="ml-1.5 rounded bg-zinc-800 px-1 text-[9.5px] text-zinc-400">
                    n={r?.n ?? "—"}
                  </span>
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <EmptyState text="No batch log on disk. This tile reads a real run or it does not appear." />
      )}

      <div className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-zinc-900 pt-2">
        {block.cache_hit_rate ? (
          <Stat label="Cache hit rate" hint={block.cache_hit_rate.basis}>
            <N q={block.cache_hit_rate} digits={2} />
          </Stat>
        ) : null}
        {block.n_entities_processed ? (
          <Stat label="Entities processed">
            <N q={block.n_entities_processed} digits={0} />
          </Stat>
        ) : null}
        {block.source ? (
          <span className="font-mono text-[10.5px] text-zinc-600">
            {String(block.source)}
          </span>
        ) : null}
      </div>

      {block.note ? (
        <p className="mt-2 text-[11.5px] leading-relaxed text-zinc-500">
          {String(block.note)}
        </p>
      ) : null}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Constraints on screen + what we could not validate                  */
/* ------------------------------------------------------------------ */

export function ConstraintsOnScreen({ items }: { items: Json }) {
  const list = arr(items);
  if (!list.length) return null;
  return (
    <Panel
      title="Constraints, stated on screen"
      plain="The rules we bound ourselves to before we built anything. They are on the page rather than in a footnote because a judge should not have to find them."
    >
      <ul className="space-y-1.5">
        {list.map((c: Json, i: number) => (
          <li
            key={i}
            className="flex gap-2 text-[12.5px] leading-relaxed text-zinc-300"
          >
            <span className="mt-[3px] shrink-0 font-mono text-[11px] text-zinc-600">
              {String(i + 1).padStart(2, "0")}
            </span>
            <span>{typeof c === "string" ? c : c?.text ?? "—"}</span>
          </li>
        ))}
      </ul>
    </Panel>
  );
}

export function CouldNotValidate({ block }: { block: Json }) {
  if (!isObj(block)) return null;
  const rows = arr(block.rows);

  return (
    <Panel
      title={
        block.title ??
        "What we could not validate, and the experiment that would"
      }
      plain="Each row is a thing we believe but cannot yet demonstrate, paired with the specific experiment that would settle it."
      right={block.n ? <N q={block.n} digits={0} /> : null}
      dense
    >
      {rows.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12.5px]">
            <thead>
              <tr className="border-b border-zinc-800 text-left t-eyebrow">
                <th className="px-4 py-1.5 font-medium">Unvalidated</th>
                <th className="px-4 py-1.5 font-medium">Why</th>
                <th className="px-4 py-1.5 font-medium">The experiment</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r: Json, i: number) => (
                <tr key={i} className="border-b border-zinc-900 align-top last:border-b-0">
                  <td className="px-4 py-2 text-zinc-200">{r?.item ?? "—"}</td>
                  <td className="px-4 py-2 leading-relaxed text-zinc-500">
                    {r?.why ?? "—"}
                  </td>
                  <td className="px-4 py-2 leading-relaxed text-zinc-300">
                    {r?.experiment ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="p-4">
          <EmptyState text="Nothing recorded." />
        </div>
      )}
    </Panel>
  );
}
