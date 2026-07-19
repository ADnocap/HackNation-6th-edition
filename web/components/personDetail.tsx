import React from "react";
import type { Json } from "@/lib/types";
import { arr, fmtDate, fmtNum, humanize, isObj, qval } from "@/lib/util";
import { Badge, Bullets, EmptyState, KVTable, N, Refusal } from "./primitives";
import { IntervalBar } from "./charts";
import { TrendChip } from "./person";

/* ------------------------------------------------------------------ */
/* Score definition strip                                              */
/* ------------------------------------------------------------------ */

/**
 * Three different things get called a "founder score". The brief treats them as
 * distinct and so does the schema, so the UI labels which is which before it
 * shows any number. Without this strip a judge reads the Founder Score and the
 * Founder axis as the same quantity, which is exactly the confusion the
 * contract exists to prevent.
 */
export function ScoreDefinitionStrip({ strip }: { strip: Json }) {
  if (!isObj(strip)) return null;
  const chain = arr(strip.chain);
  if (!chain.length) return null;

  return (
    <div className="rounded-md border border-zinc-800 bg-zinc-900/40 px-4 py-3">
      {strip.plain_line ? (
        <p className="text-[12.5px] leading-relaxed text-zinc-400">
          {strip.plain_line}
        </p>
      ) : null}

      <div className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1.5">
        {chain.map((c: Json, i: number) => {
          const text = String(typeof c === "string" ? c : c?.text ?? "");
          // Connector rows in the authored chain are prose, not nodes.
          const isConnector = /^\d+ of \d+|^never averaged/i.test(text);
          return (
            <span
              key={i}
              className={
                isConnector
                  ? "font-mono text-[10.5px] text-zinc-600"
                  : "rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-[11.5px] text-zinc-200"
              }
            >
              {text}
            </span>
          );
        })}
      </div>

      {strip.n_inputs_to_founder_axis ? (
        <div className="mt-2 text-[11px] text-zinc-500">
          inputs to the founder axis:{" "}
          <N q={strip.n_inputs_to_founder_axis} digits={0} />
        </div>
      ) : null}

      {strip.note ? (
        <p className="mt-1.5 text-[11.5px] leading-relaxed text-zinc-500">
          {strip.note}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Founder Score — per person, append-only, never resets               */
/* ------------------------------------------------------------------ */

function ScoreComponent({
  comp,
  threshold,
}: {
  comp: Json;
  threshold?: number | null;
}) {
  if (!isObj(comp)) return null;
  const point = qval(comp.point) ?? qval(comp.value);
  const interval = comp.interval ?? null;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-950/70 p-3">
      <div className="flex items-start justify-between gap-2">
        <span className="text-[11.5px] font-medium text-zinc-300">
          {comp.label ?? "—"}
        </span>
        <TrendChip axis={comp} />
      </div>

      <div className="mt-2 flex items-baseline gap-2">
        <span className="text-[22px] font-semibold tabular-nums text-zinc-100">
          {point === null ? "—" : fmtNum(point, 1)}
        </span>
        {Array.isArray(interval) ? (
          <span className="font-mono text-[11px] text-zinc-500">
            [{fmtNum(interval[0], 1)}, {fmtNum(interval[1], 1)}]
          </span>
        ) : null}
        {comp.n !== undefined && comp.n !== null ? (
          <span className="rounded bg-zinc-800 px-1 font-mono text-[10px] text-zinc-400">
            n={comp.n}
          </span>
        ) : null}
      </div>

      <div className="mt-2.5">
        <IntervalBar
          point={point}
          interval={interval}
          threshold={threshold}
          label={String(comp.label ?? "")}
        />
      </div>
    </div>
  );
}

/**
 * The Founder Score is NOT the three-axis score. It belongs to the person, it
 * persists across companies, and it never resets. It carries two components
 * that are deliberately never combined: a lie about revenue must not erase a
 * real build record. That divergence is what makes a verdict conditional
 * rather than a flat pass.
 */
export function FounderScorePanel({
  score,
  threshold,
}: {
  score: Json;
  threshold?: number | null;
}) {
  if (!isObj(score)) {
    return <EmptyState text="No Founder Score for this person at this asof." />;
  }

  const credibility = score.credibility ?? null;
  const build = score.build_capability ?? null;

  // Unknown shape: show it rather than dropping authored data on the floor.
  if (!isObj(credibility) && !isObj(build)) {
    return <KVTable obj={score} />;
  }

  return (
    <div className="space-y-3">
      {score.plain_line ? (
        <p className="text-[13px] leading-relaxed text-zinc-300">
          {score.plain_line}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <ScoreComponent comp={credibility} threshold={threshold} />
        <ScoreComponent comp={build} threshold={threshold} />
      </div>

      {score.divergence_note ? (
        <div className="rounded border border-amber-500/40 bg-amber-500/[0.07] px-3 py-2.5">
          <div className="text-[10px] uppercase tracking-wider text-amber-400">
            Why these two are never averaged
          </div>
          <p className="mt-1 text-[12.5px] leading-relaxed text-amber-100/90">
            {score.divergence_note}
          </p>
        </div>
      ) : null}

      {score.never_resets ? (
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 border-t border-zinc-900 pt-2.5">
          <Badge className="border-sky-500/40 bg-sky-500/10 text-sky-300">
            never resets
          </Badge>
          {score.never_resets_mechanism ? (
            <span className="text-[11.5px] leading-relaxed text-zinc-400">
              {score.never_resets_mechanism}
            </span>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Founder–market fit                                                  */
/* ------------------------------------------------------------------ */

/** A soft-skill construct the brief names — scored, and carrying its own interval. */
export function FounderMarketFit({ fmf }: { fmf: Json }) {
  if (!isObj(fmf)) return null;
  const point = qval(fmf.point);
  const interval = fmf.interval ?? null;

  return (
    <div className="space-y-2.5">
      {fmf.plain_line ? (
        <p className="text-[12.5px] leading-relaxed text-zinc-400">
          {fmf.plain_line}
        </p>
      ) : null}

      <div className="flex items-baseline gap-2">
        <span className="text-[22px] font-semibold tabular-nums text-zinc-100">
          {point === null ? "—" : fmtNum(point, 1)}
        </span>
        {Array.isArray(interval) ? (
          <span className="font-mono text-[11px] text-zinc-500">
            [{fmtNum(interval[0], 1)}, {fmtNum(interval[1], 1)}]
          </span>
        ) : null}
        {fmf.n_atoms ? (
          <span className="text-[11px] text-zinc-500">
            atoms: <N q={fmf.n_atoms} digits={0} />
          </span>
        ) : null}
      </div>

      <IntervalBar point={point} interval={interval} label="Founder-market fit" />

      {fmf.evidence_basis ? (
        <p className="text-[11.5px] leading-relaxed text-zinc-400">
          <span className="text-zinc-500">Evidence basis: </span>
          {fmf.evidence_basis}
        </p>
      ) : null}

      {fmf.caveat ? <Refusal>{fmf.caveat}</Refusal> : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Entity resolution — two ventures, one person                        */
/* ------------------------------------------------------------------ */

/**
 * The merge is keyed on a handle and a registrant domain, never on a name —
 * the name spelling actually differs across the two ventures. Printing what we
 * did NOT match on is the honest half of this panel.
 */
export function EntityResolution({ er }: { er: Json }) {
  if (!isObj(er)) return null;
  const reasons = arr(er.match_reasons);

  return (
    <div className="space-y-2.5">
      {er.plain_line ? (
        <p className="text-[12.5px] leading-relaxed text-zinc-400">
          {er.plain_line}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {er.merged ? (
          <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
            merged
          </Badge>
        ) : null}
        {er.merge_key ? (
          <span className="font-mono text-[11px] text-zinc-400">
            key: {humanize(er.merge_key)}
          </span>
        ) : null}
      </div>

      {[er.prior_org, er.current_org].some(isObj) ? (
        <div className="flex flex-wrap items-center gap-2 text-[12.5px]">
          {isObj(er.prior_org) ? (
            <span className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-zinc-300">
              {er.prior_org.org_name ?? er.prior_org.org_id}
            </span>
          ) : null}
          <span className="text-zinc-600">→</span>
          {isObj(er.current_org) ? (
            <span className="rounded border border-zinc-700 bg-zinc-950 px-2 py-1 text-zinc-300">
              {er.current_org.org_name ?? er.current_org.org_id}
            </span>
          ) : null}
        </div>
      ) : null}

      {reasons.length ? (
        <div>
          <div className="mb-1 t-eyebrow">
            Matched on
          </div>
          <Bullets items={reasons} />
        </div>
      ) : null}

      {er.did_not_match_on ? (
        <div>
          <div className="mb-1 t-eyebrow">
            Did not match on
          </div>
          <p className="text-[12.5px] leading-relaxed text-amber-200/80">
            {er.did_not_match_on}
          </p>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Milestones                                                          */
/* ------------------------------------------------------------------ */

/** Kept in the one ledger as observations; rendered here as a dated spine. */
export function Milestones({
  milestones,
  note,
}: {
  milestones: Json;
  note?: Json;
}) {
  const rows = arr(milestones);
  if (!rows.length) return null;

  return (
    <div>
      <ol className="space-y-1">
        {rows.map((m: Json, i: number) => (
          <li
            key={i}
            className="flex flex-wrap items-baseline gap-x-2 border-b border-zinc-900 py-1 text-[12px]"
          >
            <span className="font-mono text-[11px] text-zinc-500">
              {fmtDate(m?.at ?? m?.observed_at)}
            </span>
            <span className="text-zinc-200">
              {m?.label ?? humanize(m?.milestone_type)}
            </span>
            {m?.milestone_type ? (
              <Badge className="border-zinc-700 bg-zinc-900 text-zinc-500">
                {humanize(m.milestone_type)}
              </Badge>
            ) : null}
          </li>
        ))}
      </ol>
      {note ? (
        <p className="mt-2 text-[11.5px] leading-relaxed text-zinc-500">
          {String(note)}
        </p>
      ) : null}
    </div>
  );
}
