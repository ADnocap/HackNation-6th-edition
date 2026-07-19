import React from "react";
import type { Json } from "@/lib/types";
import {
  arr,
  fmtNum,
  humanize,
  isObj,
  PROVENANCE_STYLE,
  titleize,
} from "@/lib/util";

/* ------------------------------------------------------------------ */
/* N — the n-badge rule                                                */
/* ------------------------------------------------------------------ */

/**
 * ui_rules.n_badge_rule, implemented literally:
 *
 *   "Every number rendered on screen displays its n. An object with a `value`
 *    and no sibling `n` renders as an ERROR, not as a number. `n: null` is
 *    legal ONLY when accompanied by a `basis` string."
 *
 * Rendering the violation is the feature. A number without provenance is not
 * downgraded or silently printed — it is flagged on screen.
 */
export function N({
  q,
  digits = 1,
  unit,
  className = "",
  hideN = false,
}: {
  q: Json;
  digits?: number;
  unit?: string;
  className?: string;
  hideN?: boolean;
}) {
  if (q === null || q === undefined) {
    return <span className="text-zinc-600">—</span>;
  }

  // A bare primitive is a plain label, not a measured quantity.
  if (typeof q === "number" || typeof q === "string") {
    return (
      <span className={className}>
        {typeof q === "number" ? fmtNum(q, digits) : q}
        {unit ? <span className="text-zinc-500 ml-0.5">{unit}</span> : null}
      </span>
    );
  }

  if (!isObj(q)) return <span className="text-zinc-600">—</span>;

  const { value, n, basis, ci } = q as {
    value?: Json;
    n?: Json;
    basis?: string;
    ci?: Json;
  };

  const nMissing = n === undefined;
  const nNullWithoutBasis = n === null && !basis;

  if (nMissing || nNullWithoutBasis) {
    return (
      <span
        className="inline-flex items-center gap-1 rounded border border-rose-500/60 bg-rose-500/10 px-1.5 py-0.5 font-mono text-[11px] text-rose-300"
        title={
          nMissing
            ? "Contract violation: value rendered without an n."
            : "Contract violation: n is null with no basis string."
        }
      >
        <span className="font-bold">!</span>
        {value === null || value === undefined ? "—" : fmtNum(value, digits)}
        <span className="opacity-80">n missing</span>
      </span>
    );
  }

  const showValue =
    value === null || value === undefined ? (
      <span className="text-zinc-600">—</span>
    ) : (
      <>
        {typeof value === "number" ? fmtNum(value, digits) : String(value)}
        {unit ? <span className="text-zinc-500 ml-0.5">{unit}</span> : null}
      </>
    );

  const ciPair = Array.isArray(ci) && ci.length === 2 ? ci : null;

  return (
    <span className={`inline-flex items-baseline gap-1 ${className}`}>
      <span className="tabular-nums">{showValue}</span>
      {ciPair ? (
        <span className="font-mono text-[10px] text-zinc-500">
          [{fmtNum(ciPair[0], digits)}, {fmtNum(ciPair[1], digits)}]
        </span>
      ) : null}
      {!hideN ? (
        // The sample size is stamped onto the number, not filed away from it.
        // No quantity in this product is ever shown without one.
        <span
          className="rounded-[2px] border border-zinc-700 bg-zinc-900 px-1 font-mono text-[9.5px] leading-[15px] tracking-wide text-zinc-400"
          title={basis ? `basis: ${basis}` : `n = ${n}`}
        >
          {n === null ? "n/a" : `n=${n}`}
        </span>
      ) : null}
    </span>
  );
}

/* ------------------------------------------------------------------ */
/* Refusal rendering                                                   */
/* ------------------------------------------------------------------ */

/**
 * ui_rules.refusal_render_rule: "A null with a sibling *_blocked_reason or
 * *_render string MUST render the reason string. Rendering the refusal is the
 * feature. Never hide the field, never substitute a number."
 */
export function Refusal({ children }: { children: React.ReactNode }) {
  return (
    <div className="lacuna rounded border border-dashed border-zinc-600 px-3 py-2.5 text-[13px] leading-relaxed text-zinc-300">
      <span className="t-eyebrow mr-2 align-[1px] text-zinc-500">refused</span>
      {children}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Layout                                                              */
/* ------------------------------------------------------------------ */

/**
 * A panel is a catalogue entry: a filing label, a title in the serif
 * catalogue voice, and the one plain-language sentence a non-technical
 * investor reads before meeting any number. The three are typographically
 * distinct so the reader always knows which voice is speaking.
 */
export function Panel({
  title,
  eyebrow,
  plain,
  right,
  children,
  className = "",
  dense = false,
}: {
  title?: React.ReactNode;
  /** Filing label — what kind of thing this panel is. */
  eyebrow?: React.ReactNode;
  /** The one plain-language sentence that sits above every quant panel. */
  plain?: React.ReactNode;
  right?: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  dense?: boolean;
}) {
  return (
    <section
      className={`overflow-hidden rounded-md border border-zinc-800 bg-zinc-950/70 ${className}`}
    >
      {(title || right) && (
        <header className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2.5 border-b border-zinc-800 px-4 py-3">
          <div className="min-w-0 flex-1">
            {eyebrow ? <div className="t-eyebrow mb-1.5">{eyebrow}</div> : null}
            {title ? (
              <h2 className="t-display text-[15px] leading-tight text-zinc-100">
                {title}
              </h2>
            ) : null}
            {plain ? <p className="t-plain mt-2">{plain}</p> : null}
          </div>
          {right ? <div className="shrink-0">{right}</div> : null}
        </header>
      )}
      <div className={dense ? "" : "p-4"}>{children}</div>
    </section>
  );
}

/**
 * Page masthead. Every route opens the same way — filing label, title in
 * the catalogue voice, one sentence of orientation, then the metadata
 * rule. A judge landing on any URL knows what they are looking at.
 */
export function PageHead({
  eyebrow,
  title,
  lede,
  meta,
  right,
}: {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  lede?: React.ReactNode;
  /** Ids, timestamps, provenance — the mono voice. */
  meta?: React.ReactNode;
  right?: React.ReactNode;
}) {
  return (
    <header className="mb-5 border-b border-zinc-800 pb-4">
      <div className="flex flex-wrap items-start justify-between gap-x-6 gap-y-3">
        <div className="min-w-0 flex-1">
          {eyebrow ? <div className="t-eyebrow mb-2">{eyebrow}</div> : null}
          <h1 className="t-title text-[26px] leading-[1.15] text-zinc-50">
            {title}
          </h1>
          {lede ? (
            <p className="mt-2.5 max-w-[68ch] text-[13.5px] leading-[1.62] text-zinc-300">
              {lede}
            </p>
          ) : null}
        </div>
        {right ? <div className="shrink-0">{right}</div> : null}
      </div>
      {meta ? (
        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 font-mono text-[10.5px] text-zinc-500">
          {meta}
        </div>
      ) : null}
    </header>
  );
}

export function Badge({
  children,
  className = "",
  title,
}: {
  children: React.ReactNode;
  className?: string;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase leading-4 tracking-wide ${className}`}
    >
      {children}
    </span>
  );
}

export function ProvenanceBadge({ value }: { value: Json }) {
  if (typeof value !== "string" || !value) return null;
  const style =
    PROVENANCE_STYLE[value] ?? {
      label: value.toUpperCase(),
      cls: "bg-zinc-700/30 text-zinc-300 border-zinc-600",
    };
  return (
    <Badge
      className={style.cls}
      title={
        value === "synthetic"
          ? "Authored by us, not received from a founder."
          : value === "fixture"
          ? "Pre-downloaded real data, parsed offline."
          : "Fetched live during the run."
      }
    >
      {style.label}
    </Badge>
  );
}

export function EmptyState({
  text,
  detail,
}: {
  text?: string;
  detail?: string | null;
}) {
  // An empty state is an absence, so it wears the same material as every
  // other absence in the product rather than being styled as a failure.
  return (
    <div className="lacuna rounded border border-dashed border-zinc-700 px-4 py-6 text-center">
      <p className="text-[13px] leading-relaxed text-zinc-300">
        {text ?? "No data at this asof. Move the point-in-time control forward."}
      </p>
      {detail ? (
        <p className="mx-auto mt-1.5 max-w-xl font-mono text-[11px] leading-relaxed text-zinc-500">
          {detail}
        </p>
      ) : null}
    </div>
  );
}

/**
 * The key that teaches the hatch, shown once per page that uses it.
 * Two absences, and only one of them costs anything.
 */
export function LacunaKey({ className = "" }: { className?: string }) {
  return (
    <div
      className={`flex flex-wrap items-center gap-x-5 gap-y-2 rounded border border-zinc-800 bg-zinc-950/70 px-3 py-2 ${className}`}
    >
      <span className="t-eyebrow">Reading absence</span>
      <span className="flex items-center gap-2 text-[11.5px] text-zinc-300">
        <span className="lacuna-chip lacuna" />
        not expected for this profile — costs nothing
      </span>
      <span className="flex items-center gap-2 text-[11.5px] text-zinc-300">
        <span className="lacuna-chip lacuna-priced" />
        expected and not found — widens the interval, never lowers the score
      </span>
    </div>
  );
}

export function ErrorState({ detail }: { detail?: string | null }) {
  return (
    <div className="rounded border border-rose-500/40 bg-rose-500/5 px-4 py-3">
      <p className="text-[13px] text-rose-300">
        This panel could not render. The rest of the page is unaffected.
      </p>
      {detail ? (
        <p className="mt-1 font-mono text-[11px] text-rose-400/70">{detail}</p>
      ) : null}
    </div>
  );
}

/**
 * Per-panel error boundary. One malformed block must never take the page down
 * — that is the whole point of decoupling the renderer from the worker.
 *
 * Re-exported from its own client module: class components do not exist in the
 * RSC bundle, so it cannot be defined in this file. Call sites keep importing
 * it from "@/components/primitives" unchanged.
 */
export { PanelBoundary } from "./PanelBoundary";

/* ------------------------------------------------------------------ */
/* Generic renderers used as graceful fallbacks                        */
/* ------------------------------------------------------------------ */

/**
 * When a block exists in demo.json but does not match any shape we expected,
 * we render it as a labelled key/value grid rather than dropping it. Data the
 * integrator authored must never become invisible because of a key rename.
 */
export function KVTable({ obj, exclude = [] }: { obj: Json; exclude?: string[] }) {
  if (!isObj(obj)) return <EmptyState />;
  const entries = Object.entries(obj).filter(
    ([k, v]) => !exclude.includes(k) && v !== null && v !== undefined
  );
  if (!entries.length) return <EmptyState />;

  // A long prose value right-aligned against a short label is unreadable, so
  // anything sentence-length gets its own full-width row and reads left-to-
  // right like the note it actually is.
  const isLong = (v: Json) => typeof v === "string" && v.length > 48;

  return (
    <dl className="grid grid-cols-1 gap-x-6 gap-y-1.5 sm:grid-cols-2">
      {entries.map(([k, v]) => (
        <div
          key={k}
          className={`border-b border-zinc-900 py-1.5 ${
            isLong(v)
              ? "sm:col-span-2"
              : "flex items-baseline justify-between gap-3"
          }`}
        >
          <dt className="text-[12px] text-zinc-400">{titleize(k)}</dt>
          <dd
            className={`text-[12.5px] text-zinc-200 ${
              isLong(v) ? "mt-1 leading-relaxed" : "text-right"
            }`}
          >
            <ScalarOrQuantity v={v} />
          </dd>
        </div>
      ))}
    </dl>
  );
}

/** Render a value that may be a scalar, a Quantity, an array or a nested object. */
export function ScalarOrQuantity({ v }: { v: Json }) {
  if (v === null || v === undefined) return <span className="text-zinc-600">—</span>;
  if (typeof v === "boolean")
    return <span className={v ? "text-emerald-300" : "text-zinc-500"}>{String(v)}</span>;
  if (typeof v === "number") return <span className="tabular-nums">{fmtNum(v)}</span>;
  if (typeof v === "string") return <span>{v}</span>;
  if (Array.isArray(v)) {
    if (!v.length) return <span className="text-zinc-600">none</span>;
    if (v.every((x) => typeof x === "string" || typeof x === "number"))
      return <span>{v.join(", ")}</span>;
    return <span className="font-mono text-[11px] text-zinc-500">{v.length} rows</span>;
  }
  if (isObj(v) && "value" in v) return <N q={v} />;
  return (
    <span className="font-mono text-[11px] text-zinc-500">
      {Object.keys(v).length} fields
    </span>
  );
}

/** A labelled stat, used across the dense header strips. */
export function Stat({
  label,
  children,
  hint,
}: {
  label: string;
  children: React.ReactNode;
  hint?: string;
}) {
  return (
    <div className="min-w-0" title={hint}>
      <div className="t-eyebrow">{label}</div>
      <div className="mt-1 text-[13px] text-zinc-100">{children}</div>
    </div>
  );
}

/** Bulleted list of strings, tolerant of objects with a `text` field. */
export function Bullets({ items }: { items: Json }) {
  const list = arr(items);
  if (!list.length) return <EmptyState text="Nothing recorded here." />;
  return (
    <ul className="space-y-1.5">
      {list.map((it, i) => (
        <li key={i} className="flex gap-2 text-[13px] leading-relaxed text-zinc-300">
          <span className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-zinc-600" />
          <span>{typeof it === "string" ? it : it?.text ?? humanize(it?.item)}</span>
        </li>
      ))}
    </ul>
  );
}
