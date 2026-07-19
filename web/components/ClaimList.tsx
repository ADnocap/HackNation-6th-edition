"use client";

import React from "react";
import Link from "next/link";
import type { Json } from "@/lib/types";
import {
  Badge,
  EmptyState,
  N,
  Panel,
  ProvenanceBadge,
  Refusal,
} from "./primitives";
import { ClaimDistributionBar } from "./charts";
import {
  arr,
  CLAIM_STATE_STYLE,
  fmtNum,
  fmtSigned,
  fmtTs,
  humanize,
  isObj,
  titleize,
} from "@/lib/util";

/* ------------------------------------------------------------------ */
/* Confidence — High/Medium/Low by default, log-odds one click down    */
/* ------------------------------------------------------------------ */

function ConfidencePill({
  band,
  logOdds,
  expanded,
  onToggle,
}: {
  band: Json;
  logOdds: number | null;
  expanded: boolean;
  onToggle: () => void;
}) {
  const label =
    typeof band === "string" && band
      ? band.toUpperCase()
      : logOdds === null
      ? "—"
      : Math.abs(logOdds) >= 2
      ? "HIGH"
      : Math.abs(logOdds) >= 0.5
      ? "MEDIUM"
      : "LOW";

  const cls =
    label === "HIGH"
      ? "border-zinc-500 bg-zinc-800 text-zinc-100"
      : label === "MEDIUM"
      ? "border-zinc-600 bg-zinc-900 text-zinc-300"
      : "border-zinc-700 bg-zinc-900 text-zinc-500";

  return (
    <button
      type="button"
      onClick={(e) => {
        e.stopPropagation();
        onToggle();
      }}
      title="ui_rules.confidence_render — the log-odds number appears on click, never as the first thing shown."
      className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase leading-4 tracking-wide transition-colors hover:border-zinc-400 ${cls}`}
    >
      {label}
      {expanded && logOdds !== null ? (
        <span className="text-zinc-400 normal-case">
          {fmtSigned(logOdds, 1)} log-odds
        </span>
      ) : (
        <span className="text-zinc-600">›</span>
      )}
    </button>
  );
}

/* ------------------------------------------------------------------ */
/* Log-odds arithmetic, itemized                                       */
/* ------------------------------------------------------------------ */

export function LogOddsLedger({ lo }: { lo: Json }) {
  if (!isObj(lo)) return null;
  const terms = arr(lo.terms);
  const sum = typeof lo.sum === "number" ? lo.sum : null;
  const tv = typeof lo.threshold_verified === "number" ? lo.threshold_verified : 2;
  const tc =
    typeof lo.threshold_contradicted === "number" ? lo.threshold_contradicted : -2;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-950">
      <div className="border-b border-zinc-800 px-3 py-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          How the number was reached
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">
          Every line is a source class with a weight we published in advance.
          Nothing here was learned and nothing here came out of a language model.
        </p>
      </div>

      {terms.length ? (
        <div className="overflow-x-auto">
          <table className="w-full text-[12px]">
            <thead>
              <tr className="border-b border-zinc-800 text-left t-eyebrow">
                <th className="px-3 py-1.5 font-medium">Term</th>
                <th className="px-3 py-1.5 font-medium">Source class</th>
                <th className="px-3 py-1.5 text-right font-medium">Δ</th>
                <th className="px-3 py-1.5 text-right font-medium">Running</th>
                <th className="px-3 py-1.5 text-right font-medium">n</th>
              </tr>
            </thead>
            <tbody>
              {terms.map((t: Json, i: number) => {
                const d = typeof t?.value === "number" ? t.value : null;
                return (
                  <tr key={i} className="border-b border-zinc-900 align-top">
                    <td className="px-3 py-1.5 text-zinc-200">{t?.label ?? "—"}</td>
                    <td className="px-3 py-1.5">
                      {t?.source_class ? (
                        <span className="font-mono text-[10.5px] text-zinc-500">
                          {t.source_class}
                        </span>
                      ) : (
                        <span className="text-zinc-600">—</span>
                      )}
                    </td>
                    <td
                      className={`px-3 py-1.5 text-right font-mono tabular-nums ${
                        d === null
                          ? "text-zinc-600"
                          : d > 0
                          ? "text-emerald-400"
                          : d < 0
                          ? "text-rose-400"
                          : "text-zinc-400"
                      }`}
                    >
                      {d === null ? "—" : fmtSigned(d, 1)}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono tabular-nums text-zinc-300">
                      {typeof t?.running_total === "number"
                        ? fmtSigned(t.running_total, 1)
                        : "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right font-mono text-[10px] text-zinc-500">
                      {t?.n === null || t?.n === undefined ? "—" : t.n}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="px-3 py-3">
          <EmptyState text="No itemized terms on this claim." />
        </div>
      )}

      <div className="space-y-2 px-3 py-2.5">
        {lo.arithmetic_string ? (
          <div className="font-mono text-[13px] tabular-nums text-zinc-100">
            {lo.arithmetic_string}
          </div>
        ) : sum !== null ? (
          <div className="font-mono text-[13px] tabular-nums text-zinc-100">
            sum = {fmtSigned(sum, 1)}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-[10.5px] text-zinc-500">
          <span>
            verified at ≥ {fmtNum(tv, 1)} · contradicted at ≤ {fmtNum(tc, 1)}
          </span>
          {typeof lo.posterior_prob === "number" ? (
            <span className="text-zinc-300">
              posterior p = {lo.posterior_prob.toFixed(3)}
            </span>
          ) : null}
        </div>

        {lo.verdict_sentence ? (
          <p className="border-t border-zinc-800 pt-2 text-[12.5px] leading-relaxed text-zinc-300">
            {lo.verdict_sentence}
          </p>
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Leave-one-out waterfall                                             */
/* ------------------------------------------------------------------ */

function LooWaterfall({ rows, caption }: { rows: Json; caption?: Json }) {
  const list = arr(rows);
  if (!list.length) return null;
  const maxAbs = Math.max(
    0.1,
    ...list.map((r: Json) => Math.abs(Number(r?.delta) || 0))
  );

  return (
    <div className="rounded border border-zinc-800 bg-zinc-950">
      <div className="border-b border-zinc-800 px-3 py-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          Which evidence is load-bearing
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">
          Drop each item and recompute. This is what the claim would look like
          without it.
        </p>
      </div>
      <div className="space-y-1.5 px-3 py-2.5">
        {list.map((r: Json, i: number) => {
          const delta = Number(r?.delta) || 0;
          const pct = (Math.abs(delta) / maxAbs) * 50;
          return (
            <div
              key={r?.evidence_id ?? i}
              className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3"
            >
              <div className="min-w-0 truncate text-[12px] text-zinc-300">
                {r?.dropped ?? r?.evidence_id ?? "—"}
              </div>
              <div className="relative h-3 rounded-sm bg-zinc-900">
                <div className="absolute inset-y-0 left-1/2 w-px bg-zinc-700" />
                <div
                  className={`absolute inset-y-0 ${
                    delta >= 0 ? "bg-emerald-500/70" : "bg-rose-500/70"
                  }`}
                  style={
                    delta >= 0
                      ? { left: "50%", width: `${pct}%` }
                      : { right: "50%", width: `${pct}%` }
                  }
                />
              </div>
              <div className="flex items-center gap-2 text-right">
                <span
                  className={`font-mono text-[11px] tabular-nums ${
                    delta >= 0 ? "text-emerald-400" : "text-rose-400"
                  }`}
                >
                  {fmtSigned(delta, 1)}
                </span>
                <span className="font-mono text-[10px] text-zinc-500">
                  → {fmtSigned(r?.log_odds_without, 1)}
                </span>
                {r?.state_without ? (
                  <span className="font-mono text-[9.5px] uppercase text-zinc-600">
                    {humanize(r.state_without)}
                  </span>
                ) : null}
              </div>
            </div>
          );
        })}
        {caption ? (
          <p className="pt-1.5 text-[11px] italic text-zinc-500">{String(caption)}</p>
        ) : null}
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Receipt — the peak of the demo                                      */
/* ------------------------------------------------------------------ */

function AtomChip({ atom }: { atom: Json }) {
  const verified = atom?.verified === true;
  return (
    <span
      title={atom?.note ? String(atom.note) : undefined}
      className={`inline-flex items-center gap-1.5 rounded border px-1.5 py-0.5 text-[11px] ${
        verified
          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-200"
          : "border-zinc-700 bg-zinc-900 text-zinc-400"
      }`}
    >
      <span className={verified ? "text-emerald-400" : "text-zinc-600"}>
        {verified ? "✓" : "○"}
      </span>
      <span>{atom?.text ?? "—"}</span>
      {atom?.type ? (
        <span className="font-mono text-[9px] uppercase text-zinc-500">
          {atom.type}
        </span>
      ) : null}
    </span>
  );
}

/** Left panel: the slide crop, or the interview excerpt, or whatever we have. */
function ReceiptLeft({ left }: { left: Json }) {
  if (!isObj(left)) {
    return (
      <EmptyState text="No source artifact recorded on this claim's receipt." />
    );
  }

  const img =
    left.crop_url ??
    left.image_url ??
    left.image ??
    left.slide_image_url ??
    left.slide_crop_url ??
    null;

  return (
    <div className="flex h-full flex-col gap-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          {left.label ?? titleize(left.kind) ?? "Source"}
        </span>
        {left.source_class ? (
          <Badge className="border-zinc-700 bg-zinc-900 text-zinc-400">
            {left.source_class}
          </Badge>
        ) : null}
        <ProvenanceBadge value={left.provenance_class} />
        {left.observed_at ? (
          <span className="ml-auto font-mono text-[10px] text-zinc-500">
            observed {fmtTs(left.observed_at)}
          </span>
        ) : null}
      </div>

      {left.provenance_badge ? (
        <div className="rounded border border-amber-500/40 bg-amber-500/10 px-2.5 py-1.5 text-[11.5px] leading-snug text-amber-200">
          {left.provenance_badge}
        </div>
      ) : null}

      {img ? (
        /* eslint-disable-next-line @next/next/no-img-element */
        <img
          src={String(img)}
          alt={String(left.label ?? "source crop")}
          className="w-full rounded border border-zinc-700 bg-zinc-900"
        />
      ) : null}

      {left.excerpt ? (
        <blockquote className="rounded border-l-2 border-zinc-600 bg-zinc-900/70 px-3 py-2 text-[13px] leading-relaxed text-zinc-200">
          “{left.excerpt}”
        </blockquote>
      ) : !img ? (
        <EmptyState text="No excerpt captured." />
      ) : null}

      {(left.slide_no ?? left.slide) !== undefined &&
      (left.slide_no ?? left.slide) !== null ? (
        <div className="font-mono text-[10.5px] text-zinc-500">
          deck slide {String(left.slide_no ?? left.slide)}
          {left.bbox ? ` · bbox ${JSON.stringify(left.bbox)}` : ""}
        </div>
      ) : null}

      {arr(left.atoms).length ? (
        <div>
          <div className="mb-1.5 t-eyebrow">
            Checkable atoms
          </div>
          <div className="flex flex-wrap gap-1.5">
            {arr(left.atoms).map((a: Json, i: number) => (
              <AtomChip key={i} atom={a} />
            ))}
          </div>
        </div>
      ) : null}

      {left.caption ? (
        <p className="mt-auto pt-1 text-[11.5px] italic leading-relaxed text-zinc-500">
          {left.caption}
        </p>
      ) : null}
    </div>
  );
}

/** Right panel: what we actually fetched, with URL, status and timestamp. */
function FetchedCard({ f }: { f: Json }) {
  if (!isObj(f)) return null;
  const status = f.http_status;
  const bad =
    typeof status === "number" && (status >= 400 || status === 0);

  return (
    <div className="rounded border border-zinc-800 bg-zinc-950 p-2.5">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12px] font-medium text-zinc-200">
          {f.label ?? titleize(f.kind) ?? "Fetched"}
        </span>
        <ProvenanceBadge value={f.provenance_class} />
        {f.verifier ? (
          <Badge className="border-zinc-700 bg-zinc-900 text-zinc-400">
            {f.verifier}
          </Badge>
        ) : null}
        {status !== undefined && status !== null ? (
          <Badge
            className={
              bad
                ? "border-rose-500/50 bg-rose-500/10 text-rose-300"
                : "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
            }
          >
            HTTP {String(status)}
          </Badge>
        ) : null}
      </div>

      {f.source_url ? (
        <div className="mt-1.5 break-all font-mono text-[10.5px] text-sky-400/80">
          {String(f.source_url)}
        </div>
      ) : null}
      {f.final_url && f.final_url !== f.source_url ? (
        <div className="break-all font-mono text-[10px] text-zinc-600">
          → {String(f.final_url)}
        </div>
      ) : null}

      <div className="mt-1 flex flex-wrap gap-x-3 font-mono text-[10px] text-zinc-500">
        {f.fetched_at ? <span>fetched {fmtTs(f.fetched_at)}</span> : null}
        {f.fetch_method ? <span>via {String(f.fetch_method)}</span> : null}
      </div>

      {f.excerpt ? (
        <blockquote className="mt-2 rounded border-l-2 border-zinc-700 bg-zinc-900/60 px-2.5 py-1.5 text-[12px] leading-relaxed text-zinc-300">
          “{f.excerpt}”
        </blockquote>
      ) : null}

      {f.finding ? (
        <p
          className={`mt-2 text-[12.5px] leading-relaxed ${
            bad ? "text-rose-300" : "text-zinc-200"
          }`}
        >
          {f.finding}
        </p>
      ) : null}
    </div>
  );
}

function PersonConsequence({ pc }: { pc: Json }) {
  if (!isObj(pc)) return null;
  const before = pc.founder_score_before;
  const after = pc.founder_score_after;

  const fmtScore = (s: Json) => {
    if (!isObj(s)) return "—";
    const iv = Array.isArray(s.interval) ? s.interval : null;
    return `${fmtNum(s.point, 1)}${
      iv ? ` [${fmtNum(iv[0], 1)}, ${fmtNum(iv[1], 1)}]` : ""
    }${s.n !== undefined && s.n !== null ? ` n=${s.n}` : ""}`;
  };

  return (
    <div className="rounded border border-zinc-700 bg-zinc-900/60 p-2.5">
      <div className="t-eyebrow">
        Consequence for the person
      </div>
      {pc.headline ? (
        <p className="mt-1 text-[13px] text-zinc-100">{pc.headline}</p>
      ) : null}
      <div className="mt-1.5 flex flex-wrap items-center gap-2 font-mono text-[11px] tabular-nums text-zinc-400">
        <span>{fmtScore(before)}</span>
        <span className="text-zinc-600">→</span>
        <span className="text-zinc-200">{fmtScore(after)}</span>
      </div>
      {pc.person_id ? (
        <Link
          href={`/person/${pc.person_id}`}
          className="mt-2 inline-block text-[11.5px] text-sky-400 hover:text-sky-300 hover:underline"
        >
          The Founder Score never resets — see the full history →
        </Link>
      ) : null}
    </div>
  );
}

function ReceiptModal({ claim, onClose }: { claim: Json; onClose: () => void }) {
  const closeRef = React.useRef<HTMLButtonElement>(null);
  const returnTo = React.useRef<Element | null>(null);

  React.useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    // Move focus into the dialog, and put it back on the row that opened it
    // when the dialog closes — otherwise a keyboard user is dropped at the
    // top of the document.
    returnTo.current = document.activeElement;
    closeRef.current?.focus();

    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
      (returnTo.current as HTMLElement | null)?.focus?.();
    };
  }, [onClose]);

  const receipt = isObj(claim?.receipt) ? claim.receipt : null;
  const state = String(claim?.state ?? "");
  const style = CLAIM_STATE_STYLE[state];
  const right = arr(receipt?.right);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/80 p-4 backdrop-blur-sm"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="receipt-title"
    >
      <div
        className="cp-fade-in my-4 w-full max-w-6xl rounded-lg border border-zinc-700 bg-zinc-950 shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* header */}
        <div className="flex items-start justify-between gap-4 border-b border-zinc-800 px-4 py-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-[10px] uppercase tracking-widest text-zinc-500">
                Receipt
              </span>
              {style ? (
                <Badge className={`${style.bg} ${style.text} ${style.border}`}>
                  {style.label}
                </Badge>
              ) : null}
              {claim?.is_material ? (
                <Badge className="border-zinc-600 bg-zinc-900 text-zinc-300">
                  material
                </Badge>
              ) : null}
            </div>
            <h2
              id="receipt-title"
              className="t-display mt-1.5 max-w-[54ch] text-[18px] leading-snug text-zinc-50"
            >
              {receipt?.title ?? claim?.claim_text ?? claim?.claim_id ?? "Claim"}
            </h2>
            <p className="mt-0.5 font-mono text-[10.5px] text-zinc-500">
              {claim?.claim_id}
              {claim?.claim_type ? ` · ${claim.claim_type}` : ""}
              {claim?.evaluated_at ? ` · evaluated ${fmtTs(claim.evaluated_at)}` : ""}
              {claim?.asof ? ` · asof ${fmtTs(claim.asof)}` : ""}
            </p>
          </div>
          <button
            ref={closeRef}
            type="button"
            onClick={onClose}
            className="shrink-0 rounded border border-zinc-700 px-2.5 py-1 text-[11px] text-zinc-300 transition-colors hover:border-zinc-500 hover:text-zinc-50"
          >
            Close ⎋
          </button>
        </div>

        {/* body */}
        <div className="space-y-4 p-4">
          <p className="text-[12.5px] leading-relaxed text-zinc-400">
            What was claimed, on the left. What we actually fetched, on the
            right. The arithmetic that turned one into a verdict, below. Nothing
            in between.
          </p>

          {/* Two columns that must never be mistaken for each other: what
              they asserted, and what we independently went and got. The left
              edge of each carries the distinction. */}
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <div className="rounded border border-l-2 border-zinc-800 border-l-zinc-600 bg-zinc-900/40 p-3">
              <div className="t-eyebrow mb-2">Claimed by the founder</div>
              <ReceiptLeft left={receipt?.left} />
            </div>

            <div className="rounded border border-l-2 border-zinc-800 border-l-sky-500/70 bg-zinc-900/40 p-3">
              <div className="t-eyebrow mb-2">
                Found by us — {right.length} external check
                {right.length === 1 ? "" : "s"}
              </div>
              {right.length ? (
                <div className="space-y-2">
                  {right.map((f: Json, i: number) => (
                    <FetchedCard key={i} f={f} />
                  ))}
                </div>
              ) : (
                <EmptyState text="No external check ran against this claim." />
              )}
            </div>
          </div>

          <LogOddsLedger lo={claim?.log_odds} />
          <LooWaterfall rows={claim?.loo_waterfall} caption={claim?.loo_caption} />

          {receipt?.person_consequence ? (
            <PersonConsequence pc={receipt.person_consequence} />
          ) : null}

          <EvidenceTable rows={claim?.evidence} />
        </div>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Evidence table — including expected-but-absent, priced honestly     */
/* ------------------------------------------------------------------ */

function EvidenceTable({ rows }: { rows: Json }) {
  const list = arr(rows);
  if (!list.length) return null;

  return (
    <div className="rounded border border-zinc-800 bg-zinc-950">
      <div className="border-b border-zinc-800 px-3 py-2">
        <div className="text-[11px] font-semibold uppercase tracking-wider text-zinc-400">
          Every evidence row, including the ones that are missing
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-zinc-400">
          Evidence we expected and did not find widens the interval. It never
          lowers the score. That asymmetry is what stops absence from becoming a
          pedigree penalty.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full text-[11.5px]">
          <thead>
            <tr className="border-b border-zinc-800 text-left t-eyebrow">
              <th className="px-3 py-1.5 font-medium">Artifact</th>
              <th className="px-3 py-1.5 font-medium">Kind</th>
              <th className="px-3 py-1.5 text-center font-medium">Found</th>
              <th className="px-3 py-1.5 text-right font-medium">Δ log-odds</th>
              <th className="px-3 py-1.5 text-right font-medium">Widens</th>
              <th className="px-3 py-1.5 text-right font-medium">P(findable)</th>
              <th className="px-3 py-1.5 font-medium">Prov.</th>
            </tr>
          </thead>
          <tbody>
            {list.map((e: Json, i: number) => {
              const found = e?.found === true;
              const expectedAbsent = e?.found === false && e?.expected === true;
              return (
                <tr
                  key={e?.evidence_id ?? i}
                  className={`border-b border-zinc-900 ${
                    expectedAbsent
                      ? "lacuna-priced"
                      : e?.found === false
                      ? "lacuna"
                      : ""
                  }`}
                >
                  <td className="px-3 py-1.5">
                    <div className="text-zinc-200">
                      {humanize(e?.artifact_type) ?? "—"}
                    </div>
                    {e?.source_url ? (
                      <div className="max-w-[22rem] truncate font-mono text-[10px] text-zinc-600">
                        {String(e.source_url)}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-[10.5px] text-zinc-500">
                    {humanize(e?.kind)}
                  </td>
                  <td className="px-3 py-1.5 text-center">
                    {found ? (
                      <span className="text-emerald-400">✓</span>
                    ) : expectedAbsent ? (
                      <span
                        className="text-violet-400"
                        title="Expected for this resource class and absent — priced as width, not as a score penalty."
                      >
                        absent
                      </span>
                    ) : (
                      <span
                        className="text-zinc-600"
                        title="Not expected for this founder profile — not penalised."
                      >
                        n/a
                      </span>
                    )}
                  </td>
                  <td
                    className={`px-3 py-1.5 text-right font-mono tabular-nums ${
                      Number(e?.log_odds_delta) > 0
                        ? "text-emerald-400"
                        : Number(e?.log_odds_delta) < 0
                        ? "text-rose-400"
                        : "text-zinc-500"
                    }`}
                  >
                    {typeof e?.log_odds_delta === "number"
                      ? fmtSigned(e.log_odds_delta, 1)
                      : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right font-mono tabular-nums text-violet-300">
                    {typeof e?.interval_widen === "number" && e.interval_widen > 0
                      ? `+${fmtNum(e.interval_widen, 1)}`
                      : "—"}
                  </td>
                  <td className="px-3 py-1.5 text-right">
                    {e?.findability_prior ? (
                      <N q={e.findability_prior} digits={2} />
                    ) : (
                      <span className="text-zinc-600">—</span>
                    )}
                  </td>
                  <td className="px-3 py-1.5">
                    <ProvenanceBadge value={e?.provenance_class} />
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* The claim row                                                       */
/* ------------------------------------------------------------------ */

function ClaimRow({ claim, onOpen }: { claim: Json; onOpen: () => void }) {
  const [showLogOdds, setShowLogOdds] = React.useState(false);
  const state = String(claim?.state ?? "");
  const style = CLAIM_STATE_STYLE[state] ?? {
    label: state.toUpperCase() || "UNKNOWN",
    dot: "bg-zinc-600",
    text: "text-zinc-400",
    bg: "bg-zinc-800/40",
    border: "border-zinc-700",
  };
  const logOdds =
    typeof claim?.log_odds?.sum === "number" ? claim.log_odds.sum : null;
  const hasReceipt = isObj(claim?.receipt);

  return (
    <div
      onClick={onOpen}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpen();
        }
      }}
      className={`group grid cursor-pointer grid-cols-[auto_1fr_auto] items-start gap-3 border-b border-zinc-900 px-3 py-2.5 transition-colors hover:bg-zinc-900/60 ${
        state === "contradicted"
          ? "bg-rose-500/[0.05]"
          : state === "absent_but_expected"
          ? "lacuna-priced"
          : ""
      }`}
    >
      <span className={`mt-[7px] h-2 w-2 shrink-0 rounded-full ${style.dot}`} />

      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2">
          <Badge className={`${style.bg} ${style.text} ${style.border}`}>
            {style.label}
          </Badge>
          {claim?.claim_type ? (
            <span className="font-mono text-[10px] text-zinc-600">
              {claim.claim_type}
            </span>
          ) : null}
          {claim?.is_manifest_predicted ? (
            <Badge
              className="border-violet-500/40 bg-violet-500/10 text-violet-300"
              title="Not asserted by the founder. Added by the expected-evidence manifest because it should exist for this profile."
            >
              manifest-added
            </Badge>
          ) : null}
          {claim?.memo_blocked ? (
            <Badge
              className="border-zinc-600 bg-zinc-900 text-zinc-400"
              title="Zero evidence ids — this claim physically cannot render as prose in the memo."
            >
              blocked from memo
            </Badge>
          ) : null}
        </div>

        <p className="mt-1 text-[13.5px] leading-snug text-zinc-100">
          {claim?.claim_text ?? claim?.claim_id ?? "—"}
        </p>

        {showLogOdds && isObj(claim?.log_odds) ? (
          <div
            className="mt-2 cp-fade-in"
            onClick={(e) => e.stopPropagation()}
          >
            <LogOddsLedger lo={claim.log_odds} />
          </div>
        ) : null}
      </div>

      <div className="flex shrink-0 items-center gap-3">
        {claim?.n_evidence ? (
          <span className="hidden sm:inline">
            <N q={claim.n_evidence} digits={0} />
          </span>
        ) : null}
        <ConfidencePill
          band={claim?.confidence_band}
          logOdds={logOdds}
          expanded={showLogOdds}
          onToggle={() => setShowLogOdds((v) => !v)}
        />
        <span
          className={`font-mono text-[10px] ${
            hasReceipt
              ? "text-sky-400 group-hover:text-sky-300"
              : "text-zinc-700"
          }`}
          title={hasReceipt ? "Open the receipt" : "No receipt on this claim"}
        >
          {hasReceipt ? "RECEIPT ›" : "—"}
        </span>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* The list                                                            */
/* ------------------------------------------------------------------ */

const STATE_ORDER = [
  "contradicted",
  "absent_but_expected",
  "unverified",
  "verified",
];

export default function ClaimList({
  claims,
  distribution,
  note,
  openClaimId,
}: {
  claims: Json[];
  distribution: Json;
  note?: Json;
  /** Deep-link: open this claim's receipt on mount. The demo opens on the MRR claim. */
  openClaimId?: string | null;
}) {
  const list = arr(claims);
  const [openId, setOpenId] = React.useState<string | null>(null);
  const [filter, setFilter] = React.useState<string | null>(null);

  const open = React.useMemo(
    () => list.find((c: Json) => c?.claim_id === openId) ?? null,
    [list, openId]
  );

  const shown = React.useMemo(() => {
    const f = filter ? list.filter((c: Json) => c?.state === filter) : list;
    return [...f].sort((a: Json, b: Json) => {
      const ai = STATE_ORDER.indexOf(String(a?.state));
      const bi = STATE_ORDER.indexOf(String(b?.state));
      return (ai < 0 ? 99 : ai) - (bi < 0 ? 99 : bi);
    });
  }, [list, filter]);

  const states = React.useMemo(
    () =>
      STATE_ORDER.filter((s) => list.some((c: Json) => c?.state === s)),
    [list]
  );

  return (
    <>
      <Panel
        title="Trust is per claim, not per company"
        plain="We never average these into a company trust score. Six verified claims and three contradicted ones are not a 67% company — they are six verified claims and three contradicted ones."
        right={
          openClaimId && list.some((c: Json) => c?.claim_id === openClaimId) ? (
            <button
              type="button"
              onClick={() => setOpenId(openClaimId)}
              className="cp-pulse rounded border border-rose-500/50 bg-rose-500/10 px-2.5 py-1 text-[11.5px] text-rose-200 transition-colors hover:bg-rose-500/20"
            >
              Open the contradiction receipt →
            </button>
          ) : null
        }
      >
        <ClaimDistributionBar dist={distribution} />

        {/* The arithmetic, printed so it can be checked on camera. */}
        {isObj(distribution) && distribution.reconciliation ? (
          <p className="mt-2 font-mono text-[11px] leading-relaxed text-zinc-500">
            {String(distribution.reconciliation)}
          </p>
        ) : null}
        {isObj(distribution) && distribution.plain_line ? (
          <p className="mt-1.5 text-[12px] leading-relaxed text-zinc-400">
            {String(distribution.plain_line)}
          </p>
        ) : null}

        {states.length ? (
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <span className="t-eyebrow">
              Filter
            </span>
            <button
              type="button"
              onClick={() => setFilter(null)}
              className={`rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                filter === null
                  ? "border-zinc-500 bg-zinc-800 text-zinc-100"
                  : "border-zinc-800 bg-zinc-950 text-zinc-500 hover:border-zinc-600"
              }`}
            >
              all {list.length}
            </button>
            {states.map((s) => {
              const st = CLAIM_STATE_STYLE[s];
              const count = list.filter((c: Json) => c?.state === s).length;
              return (
                <button
                  key={s}
                  type="button"
                  onClick={() => setFilter(filter === s ? null : s)}
                  className={`rounded border px-2 py-0.5 font-mono text-[10px] uppercase tracking-wide transition-colors ${
                    filter === s
                      ? `${st.bg} ${st.text} ${st.border}`
                      : "border-zinc-800 bg-zinc-950 text-zinc-500 hover:border-zinc-600"
                  }`}
                >
                  {st.label} {count}
                </button>
              );
            })}
          </div>
        ) : null}
      </Panel>

      <Panel
        className="mt-4"
        title={`Claims — ${shown.length} shown`}
        plain="Click any row for its receipt: what was claimed, what we fetched, and the arithmetic between them."
        dense
      >
        {shown.length ? (
          <div>
            {shown.map((c: Json, i: number) => (
              <ClaimRow
                key={c?.claim_id ?? i}
                claim={c}
                onOpen={() => setOpenId(c?.claim_id ?? null)}
              />
            ))}
          </div>
        ) : (
          <div className="p-4">
            <EmptyState text="No claims at this asof. Move the point-in-time control forward." />
          </div>
        )}

        {note ? (
          <p className="border-t border-zinc-900 px-3 py-2 text-[11.5px] italic leading-relaxed text-zinc-500">
            {String(note)}
          </p>
        ) : null}
      </Panel>

      {open ? <ReceiptModal claim={open} onClose={() => setOpenId(null)} /> : null}
    </>
  );
}
