import React from "react";
import Link from "next/link";
import type { Json } from "@/lib/types";
import {
  Badge,
  EmptyState,
  N,
  Panel,
  Refusal,
  Stat,
} from "./primitives";
import { IntervalBar } from "./charts";
import {
  arr,
  fmtDate,
  fmtNum,
  fmtTs,
  humanize,
  isObj,
  MARKET_STYLE,
  titleize,
  VERDICT_STYLE,
} from "@/lib/util";

/* ------------------------------------------------------------------ */
/* The five required sections                                          */
/* ------------------------------------------------------------------ */

/**
 * The brief names five required memo sections. We do not silently omit one if
 * the generator failed to produce it — a missing required section renders as an
 * explicit "not produced" row, because a memo that is quietly four sections
 * long is exactly the failure mode this product exists to prevent.
 */
const REQUIRED_SECTIONS: { id: string; label: string; match: string[] }[] = [
  { id: "snapshot", label: "Company snapshot", match: ["snapshot", "company"] },
  {
    id: "hypotheses",
    label: "Investment hypotheses",
    match: ["hypothes", "investment"],
  },
  { id: "swot", label: "SWOT", match: ["swot"] },
  {
    id: "problem",
    label: "Problem & product",
    match: ["problem", "product"],
  },
  {
    id: "traction",
    label: "Traction & KPIs",
    match: ["traction", "kpi", "metric"],
  },
];

function sectionKey(s: Json): string {
  const raw = String(
    s?.key ?? s?.id ?? s?.section ?? s?.section_id ?? s?.title ?? s?.name ?? ""
  );
  return raw.toLowerCase().replace(/[^a-z]/g, "");
}

function matchSection(sections: Json[], spec: { match: string[] }): Json | null {
  for (const s of sections) {
    const k = sectionKey(s);
    if (spec.match.some((m) => k.includes(m))) return s;
  }
  return null;
}

/* ------------------------------------------------------------------ */
/* Bullets — a claim with zero evidence CANNOT render as prose         */
/* ------------------------------------------------------------------ */

function citationChips({
  claimIds,
  evidenceIds,
  oppId,
}: {
  claimIds: Json;
  evidenceIds: Json;
  oppId?: string;
}) {
  const cids = arr(claimIds);
  const eids = arr(evidenceIds);
  if (!cids.length && !eids.length) return null;
  return (
    <span className="ml-1.5 inline-flex flex-wrap items-baseline gap-1 align-baseline">
      {cids.map((c: Json, i: number) =>
        oppId ? (
          <Link
            key={`c${i}`}
            href={`/opportunity/${oppId}`}
            className="rounded border border-zinc-800 bg-zinc-900 px-1 font-mono text-[9.5px] text-sky-400/90 transition-colors hover:border-sky-500/50"
            title="Jump to the claim and its receipt"
          >
            {String(c)}
          </Link>
        ) : (
          <span
            key={`c${i}`}
            className="rounded border border-zinc-800 bg-zinc-900 px-1 font-mono text-[9.5px] text-zinc-500"
          >
            {String(c)}
          </span>
        )
      )}
      {eids.map((e: Json, i: number) => (
        <span
          key={`e${i}`}
          className="rounded border border-zinc-800 bg-zinc-900 px-1 font-mono text-[9.5px] text-zinc-500"
          title="Evidence row backing this sentence"
        >
          {String(e)}
        </span>
      ))}
    </span>
  );
}

export function MemoBullet({ b, oppId }: { b: Json; oppId?: string }) {
  if (typeof b === "string") {
    return (
      <li className="flex gap-2 text-[13px] leading-relaxed text-zinc-300">
        <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
        <span>{b}</span>
      </li>
    );
  }
  if (!isObj(b)) return null;

  const evidence = arr(b.evidence_ids);
  const blocked = b.render === "blocked" || evidence.length === 0;

  if (blocked) {
    return (
      <li className="flex gap-2">
        <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-zinc-700" />
        <div className="min-w-0 flex-1 rounded border border-dashed border-zinc-700 bg-zinc-900/50 px-2.5 py-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Badge className="border-zinc-600 bg-zinc-900 text-zinc-400">
              blocked
            </Badge>
            <span className="text-[12.5px] italic text-zinc-500 line-through decoration-zinc-700">
              {b.text ?? "—"}
            </span>
          </div>
          <p className="mt-1 text-[11.5px] leading-relaxed text-zinc-500">
            {b.reason ??
              "Zero evidence ids. A claim with no evidence physically cannot render as prose — it renders as this."}
          </p>
        </div>
      </li>
    );
  }

  return (
    <li className="flex gap-2 text-[13px] leading-relaxed text-zinc-200">
      <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
      <span className="min-w-0">
        {b.text ?? "—"}
        {citationChips({
          claimIds: b.claim_ids,
          evidenceIds: b.evidence_ids,
          oppId,
        })}
        {b.n !== undefined && b.n !== null ? (
          <span className="ml-1.5 rounded bg-zinc-800 px-1 font-mono text-[9.5px] text-zinc-400">
            n={typeof b.n === "object" ? b.n?.n ?? b.n?.value : b.n}
          </span>
        ) : null}
      </span>
    </li>
  );
}

function SwotGrid({ section }: { section: Json }) {
  const quads = [
    { k: "strengths", label: "Strengths", cls: "border-emerald-500/30" },
    { k: "weaknesses", label: "Weaknesses", cls: "border-rose-500/30" },
    { k: "opportunities", label: "Opportunities", cls: "border-sky-500/30" },
    { k: "threats", label: "Threats", cls: "border-amber-500/30" },
  ];
  const present = quads.filter((q) => arr(section?.[q.k]).length);
  if (!present.length) return null;

  return (
    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
      {quads.map((q) => (
        <div
          key={q.k}
          className={`rounded border bg-zinc-950 p-2.5 ${q.cls}`}
        >
          <div className="mb-1.5 text-[10px] uppercase tracking-wider text-zinc-400">
            {q.label}
          </div>
          {arr(section?.[q.k]).length ? (
            <ul className="space-y-1.5">
              {arr(section[q.k]).map((b: Json, i: number) => (
                <MemoBullet key={i} b={b} />
              ))}
            </ul>
          ) : (
            <p className="text-[11.5px] italic text-zinc-600">
              Nothing established with evidence.
            </p>
          )}
        </div>
      ))}
    </div>
  );
}

export function MemoSection({
  section,
  spec,
  oppId,
}: {
  section: Json | null;
  spec: { id: string; label: string };
  oppId?: string;
}) {
  if (!section) {
    return (
      <div className="border-b border-zinc-900 py-3 last:border-b-0">
        <h3 className="t-display text-[15px] text-zinc-300">{spec.label}</h3>
        <div className="mt-2">
          <Refusal>
            Required section not produced at this asof. It is named here rather
            than dropped, so a four-section memo cannot pass as a five-section
            one.
          </Refusal>
        </div>
      </div>
    );
  }

  const bullets = arr(section.bullets ?? section.rows ?? section.items);
  const isSwot = sectionKey(section).includes("swot");

  return (
    <div className="border-b border-zinc-900 py-3 last:border-b-0">
      <div className="flex flex-wrap items-baseline gap-2.5">
        <h3 className="t-display text-[15px] text-zinc-100">
          {section.title ?? spec.label}
        </h3>
        {section.n !== undefined && section.n !== null ? (
          <N q={section.n} digits={0} />
        ) : null}
      </div>

      {section.plain_line ? (
        <p className="t-plain mt-2">{section.plain_line}</p>
      ) : null}

      <div className="mt-2">
        {isSwot ? <SwotGrid section={section} /> : null}

        {bullets.length ? (
          <ul className={`space-y-1.5 ${isSwot ? "mt-3" : ""}`}>
            {bullets.map((b: Json, i: number) => (
              <MemoBullet key={i} b={b} oppId={oppId} />
            ))}
          </ul>
        ) : null}

        {typeof section.text === "string" && section.text ? (
          <p className="text-[13px] leading-relaxed text-zinc-200">
            {section.text}
          </p>
        ) : null}

        {!bullets.length && !isSwot && !section.text ? (
          <EmptyState text="No evidence-backed content for this section at this asof." />
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Gaps block — the part that proves nothing was fabricated            */
/* ------------------------------------------------------------------ */

export function GapsBlock({ gaps, oppId }: { gaps: Json; oppId?: string }) {
  if (!isObj(gaps)) return null;
  const rows = arr(gaps.rows);

  return (
    <Panel
      eyebrow="The gaps ledger"
      title={gaps.title ?? "What we could not establish"}
      plain={
        gaps.plain_line ??
        "The renderer physically cannot make these up. A missing number renders as this row, never as an estimate."
      }
      right={gaps.n ? <N q={gaps.n} digits={0} /> : null}
      dense
    >
      {rows.length ? (
        <table className="w-full text-[12.5px]">
          <tbody>
            {rows.map((r: Json, i: number) => (
              // Each row is a gap in the record, hatched like every other
              // absence in the product so it is read, not skimmed past.
              <tr
                key={i}
                className="lacuna border-b border-zinc-900 last:border-b-0"
              >
                <td className="w-52 px-4 py-2 align-top text-zinc-300">
                  {r?.label ?? "—"}
                </td>
                <td className="px-4 py-2 align-top">
                  <span className="text-zinc-200">{r?.value ?? "—"}</span>
                  {r?.brief_quoted ? (
                    <Badge
                      className="ml-2 border-zinc-700 bg-zinc-900 text-zinc-500"
                      title="This gap is one the challenge brief explicitly asks a memo to surface."
                    >
                      brief-named
                    </Badge>
                  ) : null}
                </td>
                <td className="w-40 px-4 py-2 text-right align-top">
                  {r?.claim_id ? (
                    oppId ? (
                      <Link
                        href={`/opportunity/${oppId}`}
                        className="font-mono text-[10px] text-sky-400/90 hover:underline"
                      >
                        {String(r.claim_id)}
                      </Link>
                    ) : (
                      <span className="font-mono text-[10px] text-zinc-500">
                        {String(r.claim_id)}
                      </span>
                    )
                  ) : (
                    <span
                      className="font-mono text-[10px] text-zinc-700"
                      title="No claim was ever asserted here. The gap is ours, not a contradiction of theirs."
                    >
                      no claim
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="p-4">
          <EmptyState text="No gaps recorded — which is itself unusual and worth checking." />
        </div>
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Bear case                                                           */
/* ------------------------------------------------------------------ */

export function BearCase({ bear, oppId }: { bear: Json; oppId?: string }) {
  if (!isObj(bear)) return null;
  const bullets = arr(bear.bullets);

  return (
    <Panel
      title={bear.title ?? "Bear case (adversarial view)"}
      plain="Assembled deterministically from the contradicted claims, the expected-but-absent ones and any dissenting axis. No new model call — there is nothing here we did not already have on the record."
      right={bear.n ? <N q={bear.n} digits={0} /> : null}
      className="border-rose-500/25"
    >
      {arr(bear.generated_from).length ? (
        <div className="mb-2.5 flex flex-wrap gap-1.5">
          {arr(bear.generated_from).map((g: Json, i: number) => (
            <Badge key={i} className="border-rose-500/30 bg-rose-500/[0.07] text-rose-300">
              {humanize(g)}
            </Badge>
          ))}
          {bear.computation ? (
            <Badge className="border-zinc-700 bg-zinc-900 text-zinc-500">
              {String(bear.computation)}
            </Badge>
          ) : null}
        </div>
      ) : null}

      {bullets.length ? (
        <ul className="space-y-2">
          {bullets.map((b: Json, i: number) => (
            <li key={i} className="flex gap-2">
              <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-rose-500" />
              <span className="min-w-0 text-[13px] leading-relaxed text-zinc-200">
                {b?.text ?? String(b)}
                {b?.axis ? (
                  <Badge className="ml-1.5 border-amber-500/40 bg-amber-500/10 text-amber-300">
                    {humanize(b.axis)} axis
                  </Badge>
                ) : null}
                {citationChips({
                  claimIds: b?.claim_ids,
                  evidenceIds: b?.evidence_ids,
                  oppId,
                })}
                {b?.n !== undefined && b?.n !== null ? (
                  <span className="ml-1.5 rounded bg-zinc-800 px-1 font-mono text-[9.5px] text-zinc-400">
                    n={typeof b.n === "object" ? b.n?.n ?? b.n?.value : b.n}
                  </span>
                ) : null}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <EmptyState text="No adversarial rows — no contradicted claims, no absent expected evidence, no dissent." />
      )}
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* Decision card                                                       */
/* ------------------------------------------------------------------ */

function ConditionList({
  title,
  plain,
  rows,
  tone,
}: {
  title: string;
  plain: string;
  rows: Json;
  tone: "neutral" | "danger";
}) {
  const list = arr(rows);
  return (
    <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
      <div
        className={`text-[11px] font-semibold uppercase tracking-wider ${
          tone === "danger" ? "text-rose-300" : "text-zinc-300"
        }`}
      >
        {title}
      </div>
      <p className="mt-1 text-[11.5px] leading-relaxed text-zinc-500">{plain}</p>
      {list.length ? (
        <ul className="mt-2 space-y-1.5">
          {list.map((c: Json, i: number) => (
            <li key={i} className="flex gap-2 text-[12.5px] leading-relaxed">
              <span
                className={`mt-[7px] h-1 w-1 shrink-0 rounded-full ${
                  tone === "danger" ? "bg-rose-500" : "bg-zinc-500"
                }`}
              />
              <span className="min-w-0 text-zinc-200">
                {c?.text ?? String(c)}
                <span className="ml-1.5 font-mono text-[9.5px] text-zinc-600">
                  {c?.resolves_claim_id ? `resolves ${c.resolves_claim_id}` : ""}
                  {c?.owner ? ` · ${c.owner}` : ""}
                  {c?.due_at ? ` · due ${fmtDate(c.due_at)}` : ""}
                </span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-[12px] italic text-zinc-600">
          None at this stage.
        </p>
      )}
    </div>
  );
}

function AxisCallout({
  kind,
  axis,
  reason,
}: {
  kind: "binding" | "dissenting";
  axis: Json;
  reason: Json;
}) {
  if (!axis) return null;
  const binding = kind === "binding";
  return (
    <div
      className={`rounded border p-3 ${
        binding
          ? "border-zinc-600 bg-zinc-900/70"
          : "border-amber-500/40 bg-amber-500/[0.06]"
      }`}
    >
      <div
        className={`text-[10px] font-semibold uppercase tracking-widest ${
          binding ? "text-zinc-400" : "text-amber-400"
        }`}
      >
        {binding ? "Binding axis" : "Dissenting axis"}
      </div>
      <div className="mt-0.5 text-[14px] font-semibold text-zinc-50">
        {titleize(axis)}
      </div>
      {reason ? (
        <p className="mt-1 text-[12.5px] leading-relaxed text-zinc-300">
          {String(reason)}
        </p>
      ) : null}
    </div>
  );
}

export function DecisionCard({ decision }: { decision: Json }) {
  if (!isObj(decision)) {
    return (
      <Panel title="Decision" plain="No decision object at this asof.">
        <EmptyState />
      </Panel>
    );
  }

  const verdict = String(decision.verdict ?? "");
  const vcls =
    VERDICT_STYLE[verdict] ?? "bg-zinc-800 text-zinc-200 border-zinc-600";
  const lo =
    typeof decision.interval_low === "number" ? decision.interval_low : null;
  const width =
    isObj(decision.interval_width) &&
    typeof decision.interval_width.value === "number"
      ? decision.interval_width.value
      : null;
  const hi = lo !== null && width !== null ? lo + width : null;
  const threshold =
    typeof decision.conviction_threshold === "number"
      ? decision.conviction_threshold
      : null;
  const maxWidth =
    typeof decision.max_interval_width === "number"
      ? decision.max_interval_width
      : null;

  return (
    <Panel
      title="Decision"
      plain="A verdict, the one axis that bound it, the one axis that dissented, and the conditions under which we would be wrong. The axes are never averaged into a single number, here or anywhere."
      right={
        <span
          className={`inline-flex items-center rounded border px-2.5 py-1 font-mono text-[12px] font-semibold uppercase tracking-wider ${vcls}`}
        >
          {decision.verdict_label ?? humanize(verdict) ?? "—"}
        </span>
      }
    >
      <div className="space-y-4">
        {decision.axes_disagree ? (
          <div className="rounded border border-amber-500/50 bg-amber-500/10 px-3 py-2">
            <div className="text-[10px] font-semibold uppercase tracking-widest text-amber-400">
              Axes disagree
            </div>
            <p className="mt-1 text-[13px] leading-relaxed text-amber-100">
              {decision.axes_disagree_headline ??
                "The three axes point in different directions. We do not average them and we do not resolve it."}
            </p>
          </div>
        ) : null}

        {/* money row */}
        <div className="flex flex-wrap items-start gap-x-8 gap-y-3">
          <Stat label="Check">
            {typeof decision.amount_usd === "number" ? (
              <span className="text-[16px] font-semibold tabular-nums text-zinc-50">
                ${(decision.amount_usd / 1000).toFixed(0)}K
              </span>
            ) : (
              <span className="text-zinc-500">no check</span>
            )}
          </Stat>

          <div className="min-w-0 flex-1">
            <div className="t-eyebrow">
              Implied ownership
            </div>
            <div className="mt-0.5">
              {decision.implied_ownership !== null &&
              decision.implied_ownership !== undefined ? (
                <span className="text-[13px] text-zinc-100">
                  <N q={decision.implied_ownership} digits={2} unit="%" />
                </span>
              ) : (
                <Refusal>
                  {decision.ownership_render ??
                    decision.ownership_blocked_reason ??
                    "Cannot compute."}
                </Refusal>
              )}
            </div>
          </div>

          {decision.n_claims ? (
            <Stat label="Claims on record">
              <N q={decision.n_claims} digits={0} />
            </Stat>
          ) : null}

          {decision.decided_at ? (
            <Stat label="Decided">
              <span className="font-mono text-[11.5px]">
                {fmtTs(decision.decided_at)}
              </span>
            </Stat>
          ) : null}
        </div>

        {/* axes */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <AxisCallout
            kind="binding"
            axis={decision.binding_axis}
            reason={decision.binding_axis_reason}
          />
          {decision.dissenting_axis ? (
            <AxisCallout
              kind="dissenting"
              axis={decision.dissenting_axis}
              reason={decision.dissenting_axis_reason}
            />
          ) : (
            <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
              <div className="text-[10px] font-semibold uppercase tracking-widest text-zinc-500">
                Dissenting axis
              </div>
              <p className="mt-1 text-[12.5px] italic text-zinc-500">
                None. No axis contradicts the binding read at this asof.
              </p>
            </div>
          )}
        </div>

        {/* the gate */}
        <div className="rounded border border-zinc-800 bg-zinc-950 p-3">
          <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-300">
            The gate
          </div>
          <p className="mt-1 text-[12px] leading-relaxed text-zinc-500">
            Capital deploys only when the interval&apos;s{" "}
            <em className="not-italic text-zinc-300">lower bound</em> clears the
            conviction bar. That is what makes a wide interval cost money instead
            of being rounded away.
          </p>

          {lo !== null ? (
            <div className="mt-2.5">
              <IntervalBar
                point={hi !== null ? (lo + hi) / 2 : lo}
                interval={hi !== null ? [lo, hi] : null}
                threshold={threshold}
                label="binding axis interval"
              />
            </div>
          ) : null}

          <div className="mt-2.5 flex flex-wrap items-center gap-x-6 gap-y-2">
            <Stat label="Lower bound">
              <span className="tabular-nums">{fmtNum(lo, 1)}</span>
            </Stat>
            <Stat label="Threshold">
              <span className="tabular-nums">{fmtNum(threshold, 1)}</span>
            </Stat>
            <Stat
              label="Width"
              hint="Risk appetite is expressed as the maximum interval width at which capital deploys."
            >
              <span
                className={
                  width !== null && maxWidth !== null && width > maxWidth
                    ? "text-rose-300"
                    : "text-zinc-100"
                }
              >
                <N q={decision.interval_width} digits={1} />
                {maxWidth !== null ? (
                  <span className="ml-1 text-[11px] text-zinc-500">
                    / max {fmtNum(maxWidth, 0)}
                  </span>
                ) : null}
              </span>
            </Stat>
            <Stat label="Gate">
              <span
                className={
                  decision.gate_passed ? "text-emerald-300" : "text-amber-300"
                }
              >
                {decision.gate_passed ? "passed" : "not passed"}
              </span>
            </Stat>
            {decision.gate_rule_applied ? (
              <Stat label="Rule">
                <span className="font-mono text-[11px] text-zinc-400">
                  {String(decision.gate_rule_applied)}
                </span>
              </Stat>
            ) : null}
          </div>

          {decision.gate_sentence ? (
            <p className="mt-2.5 border-t border-zinc-800 pt-2 text-[12.5px] leading-relaxed text-zinc-300">
              {decision.gate_sentence}
            </p>
          ) : null}
        </div>

        {/* conditions */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
          <ConditionList
            title="Conditions to close"
            plain="Each one resolves a specific claim. Nothing here is a vibe."
            rows={decision.conditions_to_close}
            tone="neutral"
          />
          <ConditionList
            title="Falsification conditions before wire"
            plain={
              String(decision.falsification_naming_note ?? "") ||
              "If any of these turns out to be true, this is a pass — not a renegotiation."
            }
            rows={decision.falsification_conditions_before_wire}
            tone="danger"
          />
        </div>

        {/* footer */}
        <div className="flex flex-wrap items-start gap-x-8 gap-y-3 border-t border-zinc-800 pt-3">
          {isObj(decision.next_action) ? (
            <Stat label="Next action">
              <span className="text-zinc-100">{decision.next_action.text}</span>
              <span className="ml-1.5 font-mono text-[10px] text-zinc-500">
                {decision.next_action.owner ?? ""}
                {decision.next_action.due_at
                  ? ` · due ${fmtTs(decision.next_action.due_at)}`
                  : ""}
              </span>
            </Stat>
          ) : null}
          {decision.portfolio_conflict ? (
            <Stat label="Portfolio conflict">
              <span className="text-[12.5px] text-zinc-300">
                {String(decision.portfolio_conflict)}
              </span>
            </Stat>
          ) : null}
          {isObj(decision.elapsed_first_signal_to_decision_minutes) ? (
            <Stat
              label="First signal → decision"
              hint="Wall clock, not compute. Compute latency lives on the honesty panel and is four orders of magnitude smaller."
            >
              <N
                q={decision.elapsed_first_signal_to_decision_minutes}
                digits={0}
                unit="min"
              />
            </Stat>
          ) : null}
          {decision.asof ? (
            <Stat label="asof">
              <span className="font-mono text-[11px]">{fmtTs(decision.asof)}</span>
            </Stat>
          ) : null}
        </div>
      </div>
    </Panel>
  );
}

/* ------------------------------------------------------------------ */
/* The memo body                                                       */
/* ------------------------------------------------------------------ */

export function MemoBody({ memo, oppId }: { memo: Json; oppId?: string }) {
  const sections = arr(memo?.sections);

  const matched = REQUIRED_SECTIONS.map((spec) => ({
    spec,
    section: matchSection(sections, spec),
  }));

  const extras = sections.filter(
    (s: Json) => !matched.some((m) => m.section === s)
  );

  const produced = matched.filter((m) => m.section).length;

  return (
    <Panel
      title="Investment memo"
      plain="Five required sections. Every sentence carries the claim and evidence ids it was built from — a sentence with no evidence cannot be written here at all, it is rendered as a blocked row instead."
      right={
        <span className="font-mono text-[11px] text-zinc-500">
          {produced}/{REQUIRED_SECTIONS.length} required sections produced
        </span>
      }
    >
      {matched.map((m) => (
        <MemoSection
          key={m.spec.id}
          section={m.section}
          spec={m.spec}
          oppId={oppId}
        />
      ))}

      {extras.length
        ? extras.map((s: Json, i: number) => (
            <MemoSection
              key={`x${i}`}
              section={s}
              spec={{ id: `x${i}`, label: String(s?.title ?? "Additional") }}
              oppId={oppId}
            />
          ))
        : null}
    </Panel>
  );
}

export function PortfolioConflictCheck({ check }: { check: Json }) {
  if (!isObj(check)) return null;
  return (
    <div className="rounded border border-zinc-800 bg-zinc-950 px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="t-eyebrow">
          Portfolio conflict check
        </span>
        <Badge
          className={
            check.conflict
              ? "border-rose-500/50 bg-rose-500/10 text-rose-300"
              : "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
          }
        >
          {check.conflict ? "conflict" : "clear"}
        </Badge>
        {check.n_positions ? <N q={check.n_positions} digits={0} /> : null}
      </div>
      {check.text ? (
        <p className="mt-1 text-[12.5px] text-zinc-300">{String(check.text)}</p>
      ) : null}
    </div>
  );
}
