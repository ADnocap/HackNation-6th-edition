"use client";

import Link from "next/link";
import React, {
  useCallback,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { Json } from "@/lib/types";
import {
  arr,
  fmtNum,
  fmtTs,
  humanize,
  isObj,
  qval,
  titleize,
  VERDICT_STYLE,
} from "@/lib/util";
import { Badge, EmptyState, N, Panel, ProvenanceBadge } from "./primitives";

type Mode = "raw" | "neutralized";

/* ------------------------------------------------------------------ */
/* Ranking                                                             */
/* ------------------------------------------------------------------ */

function num(v: Json): number | null {
  const q = qval(v);
  return q;
}

/** Higher is better. Returns null when the row carries no score for this mode. */
function scoreFor(row: Json, mode: Mode): number | null {
  if (!isObj(row)) return null;
  const rankKeys =
    mode === "raw"
      ? ["rank_raw", "raw_rank"]
      : ["rank_neutralized", "neutralized_rank", "rank_pedigree_neutralized"];
  for (const k of rankKeys) {
    const r = num(row[k]);
    // A rank is ascending (1 = best); invert so higher is better.
    if (r !== null) return -r;
  }
  const scoreKeys =
    mode === "raw"
      ? ["score_raw", "raw_score", "pedigree_score", "score"]
      : [
          "score_neutralized",
          "neutralized_score",
          "score_pedigree_neutralized",
          "pedigree_residual",
          "residual",
        ];
  for (const k of scoreKeys) {
    const s = num(row[k]);
    if (s !== null) return s;
  }
  const nested = row.ranking ?? row.scores;
  if (isObj(nested)) {
    const s = num(nested[mode]) ?? num(nested[mode === "raw" ? "raw" : "neutralized"]);
    if (s !== null) return s;
  }
  return null;
}

function hasAnyScore(rows: Json[], mode: Mode): boolean {
  return rows.some((r) => scoreFor(r, mode) !== null);
}

function rowKey(row: Json, i: number): string {
  return String(
    row?.opportunity_id ?? row?.person_id ?? row?.id ?? `row-${i}`
  );
}

/* ------------------------------------------------------------------ */
/* FLIP reorder                                                        */
/* ------------------------------------------------------------------ */

/**
 * The neutralization toggle is the single most important two seconds of the
 * demo: the board must VISIBLY reorder. A re-sort alone snaps and reads as a
 * page change, so we FLIP — measure before, measure after, animate the delta.
 */
function useFlip(keys: string[]) {
  const refs = useRef(new Map<string, HTMLElement>());
  const prev = useRef(new Map<string, number>());

  const register = useCallback((key: string, el: HTMLElement | null) => {
    if (el) refs.current.set(key, el);
    else refs.current.delete(key);
  }, []);

  const snapshot = useCallback(() => {
    const m = new Map<string, number>();
    refs.current.forEach((el, k) => m.set(k, el.getBoundingClientRect().top));
    prev.current = m;
  }, []);

  useLayoutEffect(() => {
    if (!prev.current.size) return;
    const reduce =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    refs.current.forEach((el, k) => {
      const before = prev.current.get(k);
      if (before === undefined) return;
      const after = el.getBoundingClientRect().top;
      const dy = before - after;
      if (!dy) return;
      if (reduce) return;
      el.style.transition = "none";
      el.style.transform = `translateY(${dy}px)`;
      requestAnimationFrame(() => {
        el.style.transition =
          "transform 520ms cubic-bezier(0.22, 1, 0.36, 1)";
        el.style.transform = "";
      });
    });
    prev.current = new Map();
  }, [keys.join("|")]);

  return { register, snapshot };
}

/* ------------------------------------------------------------------ */
/* Funnel                                                              */
/* ------------------------------------------------------------------ */

const FUNNEL_ORDER = [
  "discovered",
  "contactable",
  "outbound_activated",
  "activated",
  "inbound",
  "inbound_applications",
  "entered_screening",
  "screened_out",
  "diligence",
  "decision",
  "reached_decision",
  "stalled",
];

function FunnelStrip({ funnel }: { funnel: Json }) {
  if (!isObj(funnel)) return null;

  const counts = isObj(funnel.counts) ? funnel.counts : funnel;
  const entries = Object.entries(counts).filter(([k, v]) => {
    if (k === "timing" || k === "note" || k === "asof") return false;
    return typeof v === "number" || (isObj(v) && "value" in (v as object));
  });

  if (!entries.length) return null;

  entries.sort((a, b) => {
    const ia = FUNNEL_ORDER.indexOf(a[0]);
    const ib = FUNNEL_ORDER.indexOf(b[0]);
    return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
  });

  return (
    <div className="flex flex-wrap items-center gap-x-1 gap-y-2">
      {entries.map(([k, v], i) => (
        <React.Fragment key={k}>
          {i > 0 ? <span className="px-1 text-zinc-700">·</span> : null}
          <span className="flex items-baseline gap-1.5">
            <span className="font-mono text-[15px] font-semibold tabular-nums text-zinc-100">
              {typeof v === "number" ? v : fmtNum((v as Json).value, 0)}
            </span>
            <span className="text-[11.5px] text-zinc-500">{humanize(k)}</span>
          </span>
        </React.Fragment>
      ))}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* SLA clock                                                           */
/* ------------------------------------------------------------------ */

function SlaClock({ sla }: { sla: Json }) {
  if (!isObj(sla)) return null;
  const state = String(sla.state ?? "");
  const remaining = qval(sla.hours_remaining);
  const elapsed = qval(sla.hours_elapsed);

  const breached = state === "breached" || (remaining !== null && remaining < 0);
  const cls = breached
    ? "border-rose-500/50 bg-rose-500/10 text-rose-300"
    : state === "at_risk"
    ? "border-amber-500/50 bg-amber-500/10 text-amber-300"
    : "border-zinc-700 bg-zinc-900 text-zinc-400";

  return (
    <div className="flex flex-col items-end gap-1">
      <Badge className={`${cls} ${breached ? "cp-pulse" : ""}`}>
        {breached ? "SLA BREACHED" : state ? state.replace(/_/g, " ") : "SLA"}
        {remaining !== null ? (
          <span className="ml-1 tabular-nums">
            {remaining < 0
              ? `+${Math.abs(remaining).toFixed(0)}h over`
              : `${remaining.toFixed(0)}h left`}
          </span>
        ) : null}
      </Badge>
      {elapsed !== null ? (
        <span className="font-mono text-[10px] text-zinc-600">
          first signal {elapsed.toFixed(0)}h ago
        </span>
      ) : null}
      {sla.blocked_on ? (
        <span className="text-[10px] text-zinc-500">
          blocked on: {humanize(sla.blocked_on)}
        </span>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Row                                                                 */
/* ------------------------------------------------------------------ */

function FeedRow({
  row,
  index,
  delta,
  mode,
  registerRef,
}: {
  row: Json;
  index: number;
  delta: number | null;
  mode: Mode;
  registerRef: (el: HTMLElement | null) => void;
}) {
  const oppId = row?.opportunity_id ?? row?.id;
  const personId = row?.person_id;
  const name =
    row?.org_name ?? row?.company ?? row?.name ?? row?.person_display_name ?? "—";
  const verdict = row?.verdict ?? row?.verdict_label;
  const verdictKey = String(row?.verdict ?? "").toLowerCase();
  const score = scoreFor(row, mode);

  const channel =
    row?.channel ?? row?.channel_id ?? row?.source_channel ?? row?.track;

  return (
    <div
      ref={registerRef}
      className="grid grid-cols-[2.25rem_1fr_auto] items-start gap-3 border-b border-zinc-900 px-3 py-3 transition-colors hover:bg-zinc-900/50 sm:grid-cols-[2.25rem_minmax(0,1fr)_10rem_11rem]"
    >
      {/* rank */}
      <div className="flex flex-col items-center pt-0.5">
        <span className="font-mono text-[15px] font-semibold tabular-nums text-zinc-300">
          {index + 1}
        </span>
        {delta !== null && delta !== 0 ? (
          <span
            className={`font-mono text-[10px] ${
              delta > 0 ? "text-emerald-400" : "text-rose-400"
            }`}
            title="Position change under pedigree neutralization"
          >
            {delta > 0 ? `▲${delta}` : `▼${Math.abs(delta)}`}
          </span>
        ) : null}
      </div>

      {/* identity */}
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          {oppId ? (
            <Link
              href={`/opportunity/${oppId}`}
              className="truncate text-[14px] font-medium text-zinc-100 hover:text-white hover:underline"
            >
              {name}
            </Link>
          ) : (
            <span className="truncate text-[14px] font-medium text-zinc-100">
              {name}
            </span>
          )}
          <ProvenanceBadge value={row?.provenance_class} />
          {row?.axes_disagree ? (
            <Badge className="border-amber-500/50 bg-amber-500/10 text-amber-300">
              axes disagree
            </Badge>
          ) : null}
        </div>

        <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11.5px] text-zinc-500">
          {personId ? (
            <Link
              href={`/person/${personId}`}
              className="text-zinc-400 hover:text-zinc-200 hover:underline"
            >
              {row?.person_display_name ?? personId}
            </Link>
          ) : null}
          {row?.sector ? <span>{humanize(row.sector)}</span> : null}
          {channel ? (
            <Badge className="border-zinc-700 bg-zinc-900/80 text-zinc-400">
              {humanize(channel)}
            </Badge>
          ) : null}
          {row?.stage ? (
            <span className="text-zinc-500">stage: {humanize(row.stage)}</span>
          ) : null}
          {row?.first_signal_at ? (
            <span className="font-mono text-[10.5px] text-zinc-600">
              {fmtTs(row.first_signal_at)}
            </span>
          ) : null}
        </div>

        {/* Why this row moved. The reorder is the argument, so the sentence
            that explains it belongs next to the row, not in a caption. */}
        {row?.note ? (
          <p className="mt-1.5 max-w-2xl text-[11.5px] leading-relaxed text-zinc-500">
            {row.note}
          </p>
        ) : null}
      </div>

      {/* score for the active mode */}
      <div className="hidden flex-col gap-1 sm:flex">
        <span className="text-[10px] uppercase tracking-wider text-zinc-600">
          {mode === "raw" ? "raw" : "neutralized"}
        </span>
        {score !== null ? (
          <span className="font-mono text-[14px] tabular-nums text-zinc-200">
            {fmtNum(score, 1)}
          </span>
        ) : (
          <span className="text-[11px] text-zinc-600">not scored</span>
        )}
        {row?.interval_width ? (
          <span className="font-mono text-[10px] text-zinc-500">
            width <N q={row.interval_width} hideN />
          </span>
        ) : null}
      </div>

      {/* verdict + SLA */}
      <div className="flex flex-col items-end gap-1.5">
        {verdict ? (
          <Badge
            className={
              VERDICT_STYLE[verdictKey] ??
              "border-zinc-700 bg-zinc-900 text-zinc-300"
            }
          >
            {row?.verdict_label ?? humanize(verdict)}
          </Badge>
        ) : null}
        <SlaClock sla={row?.sla} />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Main                                                                */
/* ------------------------------------------------------------------ */

export default function SignalFeed({
  rows,
  funnel,
  trigger,
  derived,
  neutralizationNote,
  meta,
}: {
  rows: Json[];
  funnel: Json;
  trigger: Json;
  derived: boolean;
  neutralizationNote?: string | null;
  /** The signal_feed block itself, for its authored headline and reorder summary. */
  meta?: Json;
}) {
  const [mode, setMode] = useState<Mode>("raw");
  const reorder = isObj(meta) ? meta.reorder_summary : null;

  const canNeutralize = useMemo(
    () => hasAnyScore(rows, "neutralized") && hasAnyScore(rows, "raw"),
    [rows]
  );

  const ordered = useMemo(() => {
    const withScores = rows.map((r, i) => ({
      row: r,
      key: rowKey(r, i),
      raw: scoreFor(r, "raw"),
      neu: scoreFor(r, "neutralized"),
      original: i,
    }));

    const sortBy = (m: Mode) =>
      [...withScores].sort((a, b) => {
        const av = m === "raw" ? a.raw : a.neu;
        const bv = m === "raw" ? b.raw : b.neu;
        if (av === null && bv === null) return a.original - b.original;
        if (av === null) return 1;
        if (bv === null) return -1;
        if (bv !== av) return bv - av;
        return a.original - b.original;
      });

    const rawOrder = sortBy("raw");
    const neuOrder = sortBy("neutralized");
    const rawPos = new Map(rawOrder.map((x, i) => [x.key, i]));

    const active = mode === "raw" ? rawOrder : neuOrder;
    return active.map((x, i) => ({
      ...x,
      // Positive delta = moved UP when pedigree was removed.
      delta:
        mode === "neutralized" && canNeutralize
          ? (rawPos.get(x.key) ?? i) - i
          : null,
    }));
  }, [rows, mode, canNeutralize]);

  const keys = ordered.map((o) => o.key);
  const { register, snapshot } = useFlip(keys);

  const switchMode = (m: Mode) => {
    if (m === mode) return;
    snapshot();
    setMode(m);
  };

  const movers = ordered.filter((o) => o.delta !== null && o.delta !== 0).length;

  return (
    <div className="space-y-4">
      {/* The claim the whole board is making. */}
      {isObj(meta) && meta.headline_line ? (
        <div className="rounded-md border border-zinc-800 bg-zinc-900/40 px-4 py-3">
          <p className="max-w-3xl text-[13.5px] leading-relaxed text-zinc-200">
            {String(meta.headline_line)}
          </p>
          {meta.never_met_an_investor ? (
            <p className="mt-1.5 text-[11.5px] text-zinc-500">
              never met an investor:{" "}
              <N q={meta.never_met_an_investor} digits={0} />
            </p>
          ) : null}
        </div>
      ) : null}

      {/* Trigger banner */}
      {isObj(trigger) && (trigger.text || trigger.headline || trigger.event) ? (
        <div className="flex items-start gap-3 rounded-md border border-amber-500/40 bg-amber-500/[0.07] px-4 py-3">
          <span className="mt-0.5 h-2 w-2 shrink-0 rounded-full bg-amber-400 cp-pulse" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-amber-300">
                {trigger.label ?? "Trigger fired"}
              </span>
              <ProvenanceBadge value={trigger.provenance_class} />
              {trigger.fired_at ? (
                <span className="font-mono text-[10.5px] text-amber-200/60">
                  {fmtTs(trigger.fired_at)}
                </span>
              ) : null}
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-amber-100/90">
              {trigger.headline ?? trigger.text ?? trigger.event}
            </p>
            {trigger.opportunity_id ? (
              <Link
                href={`/opportunity/${trigger.opportunity_id}`}
                className="mt-1.5 inline-block text-[12px] text-amber-300 underline underline-offset-2 hover:text-amber-200"
              >
                Open the opportunity it created →
              </Link>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Funnel */}
      <Panel
        title="Sourcing funnel"
        plain="How many people we found, how many we could actually reach, and how many we contacted. The gap between the first two numbers is our largest structural weakness, so we print it."
      >
        {isObj(funnel) && Object.keys(funnel).length ? (
          <FunnelStrip funnel={funnel} />
        ) : (
          <EmptyState text="No funnel counts in demo.json." />
        )}
      </Panel>

      {/* Board */}
      <Panel
        dense
        title="Signal feed"
        plain="The ranked board. Flip the switch and the ranking is recomputed with access signals — prior VC-backed employer, company and domain age, whether a funding announcement already exists — regressed out. Watch the order change."
        right={
          <div className="flex flex-col items-end gap-1.5">
            <div
              role="tablist"
              aria-label="Ranking mode"
              className="inline-flex overflow-hidden rounded border border-zinc-700"
            >
              {(["raw", "neutralized"] as Mode[]).map((m) => (
                <button
                  key={m}
                  role="tab"
                  aria-selected={mode === m}
                  disabled={m === "neutralized" && !canNeutralize}
                  onClick={() => switchMode(m)}
                  className={`px-3 py-1.5 text-[11px] font-medium uppercase tracking-wide transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${
                    mode === m
                      ? "bg-zinc-100 text-zinc-900"
                      : "bg-zinc-950 text-zinc-400 hover:bg-zinc-900 hover:text-zinc-200"
                  }`}
                >
                  {m === "raw" ? "Raw" : "Access-neutralized"}
                </button>
              ))}
            </div>
            {mode === "neutralized" && canNeutralize ? (
              <span className="text-[11px] text-amber-300">
                {movers} of {ordered.length} rows moved
              </span>
            ) : null}
            {mode === "neutralized" && canNeutralize && isObj(reorder) ? (
              <span className="max-w-[16rem] text-right text-[10.5px] leading-snug text-zinc-500">
                {reorder.largest_fall
                  ? `largest fall ${(reorder.largest_fall as Json)?.from}→${
                      (reorder.largest_fall as Json)?.to
                    }`
                  : null}
                {reorder.largest_climb
                  ? ` · largest climb ${(reorder.largest_climb as Json)?.from}→${
                      (reorder.largest_climb as Json)?.to
                    }`
                  : null}
              </span>
            ) : null}
            {!canNeutralize ? (
              <span className="text-[10.5px] text-zinc-600">
                no neutralized scores in demo.json
              </span>
            ) : null}
          </div>
        }
      >
        {!ordered.length ? (
          <div className="p-4">
            <EmptyState detail="Expected signal_feed.rows, or an opportunities collection to derive the board from." />
          </div>
        ) : (
          <>
            <div className="border-b border-zinc-900 px-3 py-1.5">
              <p className="text-[11.5px] leading-relaxed text-zinc-500">
                {mode === "raw"
                  ? "Raw ranking. Access signals are still in the score."
                  : neutralizationNote ??
                    "Access-neutralized. We deliberately do not print an R² — it would not be externally anchored, and the reorder carries the argument on its own."}
              </p>
              {mode === "neutralized" && isObj(reorder) && reorder.line ? (
                <p className="mt-1 text-[11.5px] font-medium text-amber-300">
                  {String(reorder.line)}
                </p>
              ) : null}
              {isObj(meta) && meta.n_rows_note ? (
                <p className="mt-1 text-[10.5px] text-zinc-600">
                  {String(meta.n_rows_note)}
                </p>
              ) : null}
            </div>
            <div>
              {ordered.map((o, i) => (
                <FeedRow
                  key={o.key}
                  row={o.row}
                  index={i}
                  delta={o.delta}
                  mode={mode}
                  registerRef={(el) => register(o.key, el)}
                />
              ))}
            </div>
          </>
        )}
        {derived && ordered.length ? (
          <p className="px-3 py-2 text-[11px] text-zinc-600">
            Board derived from the opportunities collection — demo.json carried no
            explicit signal_feed block.
          </p>
        ) : null}
      </Panel>
    </div>
  );
}
