import React from "react";
import Link from "next/link";
import type { Json } from "@/lib/types";
import { Badge, N, Panel, ProvenanceBadge, Refusal, Stat } from "./primitives";
import { arr, fmtNum, fmtTs, humanize, isObj, titleize } from "@/lib/util";

/* ------------------------------------------------------------------ */
/* Opportunity header — identity, track, provenance, nav               */
/* ------------------------------------------------------------------ */

export function OpportunityHeader({
  opp,
  active,
}: {
  opp: Json;
  active: "claims" | "memo";
}) {
  const id = opp?.opportunity_id ?? "";
  const tabs = [
    { key: "claims", href: `/opportunity/${id}`, label: "Evidence check" },
    { key: "memo", href: `/opportunity/${id}/memo`, label: "Decision" },
  ];

  return (
    <div className="mb-5">
      <Link
        href="/"
        className="text-[11.5px] text-zinc-400 transition-colors hover:text-zinc-200"
      >
        ← Discovery
      </Link>

      <div className="mt-2 flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0">
          <div className="t-eyebrow mb-1.5">
            Opportunity · {opp?.opportunity_id ?? "—"}
          </div>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="t-title text-[26px] leading-tight text-zinc-50">
              {opp?.org_name ?? opp?.opportunity_id ?? "Opportunity"}
            </h1>
            <ProvenanceBadge value={opp?.provenance_class} />
            {opp?.track ? (
              <Badge className="border-zinc-700 bg-zinc-900 text-zinc-400">
                {opp.track}
              </Badge>
            ) : null}
            {opp?.sector ? (
              <Badge className="border-zinc-700 bg-zinc-900 text-zinc-400">
                {humanize(opp.sector)}
              </Badge>
            ) : null}
          </div>
        </div>

        {opp?.person_id ? (
          <Link
            href={`/person/${opp.person_id}`}
            className="shrink-0 rounded border border-zinc-700 bg-zinc-900 px-2.5 py-1.5 text-[12px] text-sky-300 transition-colors hover:border-sky-500/50 hover:text-sky-200"
          >
            {opp?.person_display_name ?? opp.person_id} — understand the founder →
          </Link>
        ) : null}
      </div>

      <nav
        className="mt-4 flex gap-1 border-b border-zinc-800"
        aria-label="Opportunity views"
      >
        {tabs.map((t) => (
          <Link
            key={t.key}
            href={t.href}
            aria-current={active === t.key ? "page" : undefined}
            className={`-mb-px border-b-2 px-3 py-2 text-[12.5px] transition-colors ${
              active === t.key
                ? "border-amber-400 text-zinc-50"
                : "border-transparent text-zinc-400 hover:border-zinc-700 hover:text-zinc-200"
            }`}
          >
            {t.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* SLA clock                                                           */
/* ------------------------------------------------------------------ */

export function SlaStrip({ sla }: { sla: Json }) {
  if (!isObj(sla)) return null;
  const state = String(sla.state ?? "");
  const breached = state === "breached";
  const remaining = isObj(sla.hours_remaining) ? sla.hours_remaining : null;

  return (
    <div
      className={`flex flex-wrap items-center gap-x-5 gap-y-2 rounded-md border px-3 py-2 ${
        breached
          ? "border-rose-500/40 bg-rose-500/[0.06]"
          : "border-zinc-800 bg-zinc-950/70"
      }`}
    >
      <div className="flex items-center gap-2">
        <span
          className={`h-2 w-2 rounded-full ${
            breached ? "bg-rose-500" : "bg-emerald-400"
          }`}
        />
        <span
          className={`font-mono text-[11px] uppercase tracking-wider ${
            breached ? "text-rose-300" : "text-emerald-300"
          }`}
        >
          SLA {state || "unknown"}
        </span>
      </div>

      {isObj(sla.hours_elapsed) ? (
        <Stat label="Elapsed" hint={sla.hours_elapsed.basis}>
          <N q={sla.hours_elapsed} digits={1} unit="h" />
        </Stat>
      ) : null}

      {remaining ? (
        <Stat label="Remaining" hint={remaining.basis}>
          <span className={breached ? "text-rose-300" : "text-zinc-100"}>
            <N q={remaining} digits={1} unit="h" />
          </span>
        </Stat>
      ) : null}

      {sla.due_at ? (
        <Stat label="Due">
          <span className="font-mono text-[11.5px]">{fmtTs(sla.due_at)}</span>
        </Stat>
      ) : null}

      {sla.blocked_on ? (
        <Stat
          label="Blocked on"
          hint="Human wait, not compute latency. We distinguish the two everywhere."
        >
          <span className="text-amber-300">{humanize(sla.blocked_on)}</span>
        </Stat>
      ) : null}

      {sla.badge ? (
        <p className="w-full text-[12px] leading-relaxed text-zinc-400">
          {sla.badge}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Stage timeline                                                      */
/* ------------------------------------------------------------------ */

const STAGE_ORDER = ["sourcing", "screening", "diligence", "decision"];

export function StageTimeline({ timeline }: { timeline: Json }) {
  const list = arr(timeline);
  if (!list.length) return null;

  const fmtDur = (m: Json) => {
    if (typeof m !== "number" || !Number.isFinite(m)) return null;
    if (m < 60) return `${fmtNum(m, 0)}m`;
    if (m < 1440) return `${fmtNum(m / 60, 1)}h`;
    return `${fmtNum(m / 1440, 1)}d`;
  };

  return (
    <Panel
      title="Stage timeline"
      plain="Sourcing → Screening → Diligence → Decision. Where the clock stopped for a human is marked separately from where our compute was slow — they are four orders of magnitude apart."
    >
      <ol className="space-y-0">
        {list.map((s: Json, i: number) => {
          const idx = STAGE_ORDER.indexOf(String(s?.stage));
          const terminal = s?.is_terminal === true;
          const open = s?.exited_reason === null || s?.exited_reason === undefined;
          const dur = fmtDur(s?.duration_minutes);
          return (
            <li key={i} className="relative flex gap-3 pb-4 last:pb-0">
              <div className="flex flex-col items-center">
                <span
                  className={`mt-1 h-2.5 w-2.5 shrink-0 rounded-full ${
                    open ? "bg-amber-400" : "bg-zinc-500"
                  }`}
                />
                {i < list.length - 1 ? (
                  <span className="mt-1 w-px flex-1 bg-zinc-800" />
                ) : null}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-[13px] font-medium text-zinc-100">
                    {idx >= 0 ? `${idx + 1}. ` : ""}
                    {titleize(s?.stage)}
                  </span>
                  {s?.entered_by ? (
                    <Badge className="border-zinc-800 bg-zinc-900 text-zinc-500">
                      by {s.entered_by}
                    </Badge>
                  ) : null}
                  {s?.screen_result ? (
                    <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
                      screen: {s.screen_result}
                    </Badge>
                  ) : null}
                  {s?.wait_is_human ? (
                    <Badge className="border-amber-500/40 bg-amber-500/10 text-amber-300">
                      human wait
                    </Badge>
                  ) : null}
                  {terminal ? (
                    <Badge className="border-zinc-600 bg-zinc-900 text-zinc-300">
                      terminal
                    </Badge>
                  ) : null}
                </div>

                <div className="mt-0.5 flex flex-wrap gap-x-3 font-mono text-[10.5px] text-zinc-500">
                  {s?.entered_at ? <span>{fmtTs(s.entered_at)}</span> : null}
                  {dur ? <span>held {dur}</span> : <span>open</span>}
                  {s?.exited_reason ? <span>→ {s.exited_reason}</span> : null}
                  {s?.blocked_on ? (
                    <span className="text-amber-400">
                      blocked on {humanize(s.blocked_on)}
                    </span>
                  ) : null}
                </div>

                {s?.note ? (
                  <p className="mt-1 max-w-3xl text-[12px] leading-relaxed text-zinc-400">
                    {s.note}
                  </p>
                ) : null}
              </div>
            </li>
          );
        })}
      </ol>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Deck / apply form summary                                           */
/* ------------------------------------------------------------------ */

export function SourceArtifact({ opp }: { opp: Json }) {
  const deck = opp?.deck;
  const form = opp?.apply_form;

  if (isObj(deck)) {
    return (
      <Panel
        title="Source artifact — deck"
        plain="Claims below were extracted from this file. Every one of them points back to a page and a region of it."
      >
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
          {deck.filename ? (
            <Stat label="File">
              <span className="font-mono text-[11.5px]">{deck.filename}</span>
            </Stat>
          ) : null}
          {deck.n_slides !== undefined ? (
            <Stat label="Slides">
              <N q={deck.n_slides} digits={0} />
            </Stat>
          ) : null}
          {deck.received_at ? (
            <Stat label="Received">
              <span className="font-mono text-[11.5px]">
                {fmtTs(deck.received_at)}
              </span>
            </Stat>
          ) : null}
          {deck.provenance_class ? (
            <Stat label="Provenance">
              <ProvenanceBadge value={deck.provenance_class} />
            </Stat>
          ) : null}
        </div>
        {deck.note ? (
          <p className="mt-2 text-[12px] leading-relaxed text-zinc-400">
            {deck.note}
          </p>
        ) : null}
      </Panel>
    );
  }

  if (isObj(form)) {
    return (
      <Panel
        title="Source artifact — inbound apply"
        plain="Two fields. We didn't ask for team size, market or traction — if we need it, we find it or we ask one specific question about it."
      >
        <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
          {Object.entries(form)
            .filter(([, v]) => v !== null && v !== undefined)
            .map(([k, v]) => (
              <div
                key={k}
                className="flex items-baseline justify-between gap-3 border-b border-zinc-900 py-1"
              >
                <dt className="text-[12px] text-zinc-500">{titleize(k)}</dt>
                <dd className="text-right text-[12.5px] text-zinc-200">
                  {typeof v === "object" ? JSON.stringify(v) : String(v)}
                </dd>
              </div>
            ))}
        </dl>
      </Panel>
    );
  }

  return (
    <Panel
      title="Source artifact"
      plain="This opportunity came from outbound sourcing, not from a submission."
    >
      <Refusal>
        No deck. Claims are derived from observations and from the elicitation
        response, and follow the identical claim shape.
      </Refusal>
    </Panel>
  );
}
