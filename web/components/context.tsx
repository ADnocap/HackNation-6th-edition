import React from "react";
import type { Json } from "@/lib/types";
import { arr, fmtDate, fmtMoney, fmtNum, humanize, isObj, qval } from "@/lib/util";
import { Badge, Bullets, EmptyState, N, Panel } from "./primitives";

/* ------------------------------------------------------------------ */
/* Thesis Engine — configurable, not hardcoded to one fund             */
/* ------------------------------------------------------------------ */

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-3 border-b border-zinc-900 py-1.5">
      <span className="text-[11.5px] text-zinc-500">{label}</span>
      <span className="text-right text-[12.5px] text-zinc-200">{children}</span>
    </div>
  );
}

/**
 * The brief requires the Thesis Engine to be CONFIGURABLE rather than wired to
 * one fund. These are persisted fields; editing any of them re-ranks the board
 * and can move an opportunity across the decision gate. Risk appetite is the
 * load-bearing one: it maps to the maximum interval width at which capital
 * deploys, which is a mechanic rather than a filter bar.
 */
export function ThesisPanel({ thesis }: { thesis: Json }) {
  if (!isObj(thesis) || !Object.keys(thesis).length) {
    return <EmptyState text="No thesis configured at this asof." />;
  }

  const sectors = arr(thesis.sectors);
  const geo = arr(thesis.geography);
  const ownership = thesis.ownership_target_pct;
  const appetite = String(thesis.risk_appetite ?? "");
  const appetiteMap = isObj(thesis.risk_appetite_map) ? thesis.risk_appetite_map : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[13.5px] font-medium text-zinc-100">
          {thesis.name ?? thesis.thesis_id ?? "Thesis"}
        </span>
        {thesis.configurable ? (
          <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
            configurable
          </Badge>
        ) : null}
      </div>

      {thesis.configurable_note ? (
        <p className="text-[12.5px] leading-relaxed text-zinc-400">
          {thesis.configurable_note}
        </p>
      ) : null}

      <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
        {sectors.length ? (
          <Field label="Sectors">
            {sectors.map((s: Json) => humanize(s)).join(", ")}
          </Field>
        ) : null}
        {thesis.stage ? <Field label="Stage">{String(thesis.stage)}</Field> : null}
        {geo.length ? <Field label="Geography">{geo.join(", ")}</Field> : null}
        {thesis.check_size_usd ? (
          <Field label="Check size">{fmtMoney(thesis.check_size_usd)}</Field>
        ) : null}
        {Array.isArray(ownership) ? (
          <Field label="Ownership target">
            {ownership[0]}–{ownership[1]}%
          </Field>
        ) : null}
        {thesis.conviction_threshold != null ? (
          <Field label="Conviction threshold">
            <span className="font-mono tabular-nums">
              {fmtNum(thesis.conviction_threshold)}
            </span>
          </Field>
        ) : null}
        {thesis.max_interval_width != null ? (
          <Field label="Max interval width">
            <span className="font-mono tabular-nums">
              {fmtNum(thesis.max_interval_width)}
            </span>
          </Field>
        ) : null}
        {appetite ? (
          <Field label="Risk appetite">
            <span className="uppercase text-amber-300">{appetite}</span>
          </Field>
        ) : null}
      </div>

      {/* Risk appetite is a mechanic, so show the whole map, not just the setting. */}
      {appetiteMap ? (
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
          <div className="mb-2 t-eyebrow">
            Risk appetite → maximum interval width at which capital deploys
          </div>
          <div className="flex flex-wrap gap-2">
            {Object.entries(appetiteMap).map(([k, raw]) => {
              const v = raw as Json;
              const active = k === appetite;
              return (
                <span
                  key={k}
                  className={`rounded border px-2 py-1 text-[11.5px] ${
                    active
                      ? "border-amber-500/50 bg-amber-500/10 text-amber-200"
                      : "border-zinc-700 bg-zinc-950 text-zinc-400"
                  }`}
                  title={isObj(v) && v.basis ? String(v.basis) : undefined}
                >
                  {k}: width ≤{" "}
                  <span className="font-mono tabular-nums">
                    {fmtNum(isObj(v) ? v.max_interval_width : v, 0)}
                  </span>
                  {active ? " ← active" : ""}
                </span>
              );
            })}
          </div>
          {thesis.risk_appetite_is_load_bearing ? (
            <p className="mt-2 text-[11.5px] leading-relaxed text-zinc-400">
              {thesis.risk_appetite_is_load_bearing}
            </p>
          ) : null}
        </div>
      ) : null}

      {arr(thesis.hard_filters).length ? (
        <div>
          <div className="mb-1 t-eyebrow">
            Hard filters
          </div>
          <div className="flex flex-wrap gap-1.5">
            {arr(thesis.hard_filters).map((f: Json, i: number) => (
              <span
                key={i}
                className="rounded border border-zinc-700 bg-zinc-950 px-1.5 py-0.5 font-mono text-[10.5px] text-zinc-400"
              >
                {String(f)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {isObj(thesis.soft_weights) ? (
        <div>
          <div className="mb-1 t-eyebrow">
            Soft weights — per axis, never summed into one number
          </div>
          <div className="grid grid-cols-1 gap-x-6 sm:grid-cols-2">
            {Object.entries(thesis.soft_weights).map(([k, raw]) => {
              const v = raw as Json;
              return (
                <Field key={k} label={humanize(k)}>
                  <span className="font-mono tabular-nums">
                    {isObj(v) ? <N q={v} digits={2} /> : fmtNum(v, 2)}
                  </span>
                </Field>
              );
            })}
          </div>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Memory — one append-only ledger                                     */
/* ------------------------------------------------------------------ */

export function MemoryPanel({ memory }: { memory: Json }) {
  if (!isObj(memory) || !Object.keys(memory).length) {
    return <EmptyState text="No memory counts at this asof." />;
  }

  const counts: [string, Json][] = [
    ["observations", memory.observations_ingested],
    ["deduplicated", memory.deduplicated],
    ["enriched", memory.enriched],
    ["people", memory.people],
    ["orgs", memory.orgs],
    ["claims", memory.claims],
    ["evidence links", memory.evidence_links],
  ].filter(([, v]) => v !== undefined && v !== null) as [string, Json][];

  const ingest = arr(memory.ingest_types);
  const writeback = isObj(memory.axis_writeback) ? memory.axis_writeback : null;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        {memory.append_only ? (
          <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
            append only
          </Badge>
        ) : null}
        {memory.never_updated ? (
          <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
            never updated
          </Badge>
        ) : null}
      </div>

      <div className="grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
        {counts.map(([label, q]) => (
          <div key={label}>
            <div className="t-eyebrow">
              {label}
            </div>
            <div className="mt-0.5 font-mono text-[13px] text-zinc-100">
              <N q={q} digits={0} />
            </div>
          </div>
        ))}
      </div>

      {ingest.length ? (
        <div>
          <div className="mb-1 t-eyebrow">
            Ingest types
          </div>
          <div className="flex flex-wrap gap-1.5">
            {ingest.map((t: Json, i: number) => (
              <Badge key={i} className="border-zinc-700 bg-zinc-900 text-zinc-400">
                {humanize(t)}
              </Badge>
            ))}
          </div>
        </div>
      ) : null}

      {memory.dedup_rule ? (
        <p className="font-mono text-[11px] leading-relaxed text-zinc-500">
          dedup: {String(memory.dedup_rule)}
        </p>
      ) : null}

      {/* Each axis writes back into Memory so the next company starts sharper. */}
      {writeback && arr(writeback.rows).length ? (
        <div className="rounded border border-zinc-800 bg-zinc-900/40 p-3">
          <div className="t-eyebrow">
            {writeback.title ?? "Axis write-back"}
          </div>
          {writeback.plain_line ? (
            <p className="mt-1 text-[11.5px] leading-relaxed text-zinc-400">
              {writeback.plain_line}
            </p>
          ) : null}
          <ul className="mt-2 space-y-1">
            {arr(writeback.rows).map((r: Json, i: number) => (
              <li
                key={i}
                className="flex flex-wrap items-baseline gap-x-2 border-b border-zinc-900 py-1 text-[11.5px]"
              >
                <span className="text-zinc-300">{humanize(r?.axis ?? r?.wrote)}</span>
                {r?.prior_before != null && r?.prior_after != null ? (
                  <span className="font-mono tabular-nums text-zinc-400">
                    {fmtNum(qval(r.prior_before), 2)} → {fmtNum(qval(r.prior_after), 2)}
                  </span>
                ) : null}
                {r?.next_scored_off_it ? (
                  <span className="text-zinc-500">— {String(r.next_scored_off_it)}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Compound query — one pass, resolutions printed                      */
/* ------------------------------------------------------------------ */

const RESOLUTION_STYLE: Record<string, string> = {
  resolved: "border-emerald-500/40 bg-emerald-500/10 text-emerald-300",
  no_source: "border-rose-500/50 bg-rose-500/10 text-rose-300",
  declined: "border-rose-500/50 bg-rose-500/10 text-rose-300",
  partial: "border-amber-500/40 bg-amber-500/10 text-amber-300",
  probabilistic: "border-sky-500/40 bg-sky-500/10 text-sky-300",
};

/**
 * A compound natural-language query resolved in one pass. The important chips
 * are the ones that resolve to NO SOURCE: rather than quietly dropping a
 * clause it cannot honour, the system prints which clause it refused and why.
 */
export function CompoundQueryPanel({ cq }: { cq: Json }) {
  if (!isObj(cq) || !Object.keys(cq).length) return null;
  const chips = arr(cq.chips);

  return (
    <div className="space-y-3">
      {cq.query_text ? (
        <div className="rounded border border-zinc-700 bg-zinc-950 px-3 py-2">
          <span className="font-mono text-[12.5px] leading-relaxed text-zinc-200">
            {String(cq.query_text)}
          </span>
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-[11.5px] text-zinc-500">
        {cq.one_pass_badge ? (
          <Badge className="border-sky-500/40 bg-sky-500/10 text-sky-300">
            {String(cq.one_pass_badge)}
          </Badge>
        ) : null}
        {cq.n_llm_calls != null ? <span>LLM calls: {fmtNum(cq.n_llm_calls, 0)}</span> : null}
        {cq.n_sql_queries != null ? <span>SQL: {fmtNum(cq.n_sql_queries, 0)}</span> : null}
        {cq.latency_ms != null ? <span>{fmtNum(cq.latency_ms, 0)}ms</span> : null}
        {cq.n_results != null ? (
          <span>
            results: <N q={cq.n_results} digits={0} />
          </span>
        ) : null}
      </div>

      {chips.length ? (
        <div className="space-y-1.5">
          {chips.map((c: Json, i: number) => {
            const res = String(c?.resolution ?? "");
            return (
              <div
                key={i}
                className="flex flex-wrap items-baseline gap-x-2 gap-y-1 border-b border-zinc-900 py-1.5"
              >
                <span className="text-[12.5px] text-zinc-100">
                  &ldquo;{String(c?.text ?? "")}&rdquo;
                </span>
                <Badge
                  className={
                    RESOLUTION_STYLE[res] ?? "border-zinc-700 bg-zinc-900 text-zinc-400"
                  }
                >
                  {String(c?.resolution_label ?? humanize(res) ?? "—")}
                </Badge>
                {c?.kind ? (
                  <span className="text-[10.5px] text-zinc-600">{humanize(c.kind)}</span>
                ) : null}
                {c?.sql ? (
                  <span className="font-mono text-[10.5px] text-zinc-500">{String(c.sql)}</span>
                ) : null}
                {/* A probability with its n, never a filter that silently
                    drops everyone we simply have no data on. */}
                {c?.p_satisfied ? (
                  <span className="font-mono text-[11px] text-zinc-300">
                    P=<N q={c.p_satisfied} digits={2} />
                  </span>
                ) : null}
                {c?.n_matching ? (
                  <span className="ml-auto font-mono text-[11px] text-zinc-300">
                    <N q={c.n_matching} digits={0} />
                  </span>
                ) : null}
                {c?.reason ? (
                  <p className="w-full text-[11.5px] leading-relaxed text-rose-200/80">
                    {String(c.reason)}
                    {c?.links_to ? (
                      <span className="ml-1 font-mono text-zinc-500">
                        → {String(c.links_to)}
                      </span>
                    ) : null}
                  </p>
                ) : null}
                {c?.note ? (
                  <p className="w-full text-[11.5px] leading-relaxed text-zinc-500">
                    {String(c.note)}
                  </p>
                ) : null}
              </div>
            );
          })}
        </div>
      ) : null}

      {cq.closing_line ? (
        <p className="text-[12px] leading-relaxed text-zinc-400">{String(cq.closing_line)}</p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Screen — a screen-out is never a delete                             */
/* ------------------------------------------------------------------ */

export function ScreenPanel({ screen }: { screen: Json }) {
  if (!isObj(screen) || !Object.keys(screen).length) return null;
  const rules = arr(screen.rules);

  return (
    <div className="space-y-3">
      {screen.reversible ? (
        <Badge className="border-emerald-500/40 bg-emerald-500/10 text-emerald-300">
          reversible
        </Badge>
      ) : null}

      {rules.length ? (
        <ul className="space-y-1.5">
          {rules.map((r: Json, i: number) => (
            <li
              key={r?.rule_id ?? i}
              className="flex flex-wrap items-baseline gap-x-2 border-b border-zinc-900 py-1.5"
            >
              <span className="font-mono text-[10.5px] text-zinc-600">
                {String(r?.rule_id ?? "")}
              </span>
              <span className="flex-1 text-[12.5px] leading-relaxed text-zinc-300">
                {String(r?.text ?? "")}
              </span>
              {r?.n_killed ? (
                <span className="font-mono text-[11px] text-zinc-200">
                  <N q={r.n_killed} digits={0} />
                </span>
              ) : null}
            </li>
          ))}
        </ul>
      ) : null}

      {screen.reversibility_statement ? (
        <p className="text-[12px] leading-relaxed text-zinc-400">
          {String(screen.reversibility_statement)}
        </p>
      ) : null}

      {screen.over_collection_line ? (
        <p className="text-[11.5px] leading-relaxed text-zinc-500">
          {String(screen.over_collection_line)}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Portfolio conflict check                                            */
/* ------------------------------------------------------------------ */

export function PortfolioPanel({ portfolio }: { portfolio: Json }) {
  if (!isObj(portfolio) || !Object.keys(portfolio).length) return null;
  const positions = arr(portfolio.positions);
  if (!positions.length) return null;

  return (
    <div className="space-y-2">
      <ul className="space-y-1">
        {positions.map((p: Json, i: number) => (
          <li
            key={p?.position_id ?? i}
            className="flex flex-wrap items-baseline gap-x-2 border-b border-zinc-900 py-1.5 text-[12px]"
          >
            <span className="text-zinc-100">{String(p?.org_name ?? "—")}</span>
            <span className="text-zinc-500">{humanize(p?.sector)}</span>
            {p?.stage ? <span className="text-zinc-600">{String(p.stage)}</span> : null}
            {p?.entered_at ? (
              <span className="font-mono text-[10.5px] text-zinc-600">
                {fmtDate(p.entered_at)}
              </span>
            ) : null}
            {p?.conflict_scope ? (
              <span className="w-full text-[11.5px] text-zinc-500">
                scope: {String(p.conflict_scope)}
              </span>
            ) : null}
          </li>
        ))}
      </ul>
      {portfolio.out_of_scope_note ? (
        <p className="text-[11.5px] leading-relaxed text-zinc-500">
          {String(portfolio.out_of_scope_note)}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* As-of slices — the point-in-time control                            */
/* ------------------------------------------------------------------ */

/**
 * THE CHOKEPOINT, surfaced. Every read path filters on observed_at <= asof, so
 * asof=now is a live VC brain and asof=past is a point-in-time backtest through
 * the identical code. The slices are rendered as state, not as a live control:
 * the committed demo.json is a single asof, and pretending otherwise would be
 * a fake button.
 */
export function AsofSlices({ slices }: { slices: Json }) {
  if (!isObj(slices)) return null;
  const available = arr(slices.available);
  if (!available.length) return null;
  const active = slices.default;

  return (
    <div className="space-y-2.5">
      <div className="flex flex-wrap gap-2">
        {available.map((s: Json, i: number) => {
          const isActive = s?.asof === active;
          return (
            <div
              key={i}
              className={`rounded border px-2.5 py-1.5 ${
                isActive
                  ? "border-zinc-500 bg-zinc-800 text-zinc-100"
                  : "border-zinc-800 bg-zinc-950 text-zinc-500"
              }`}
              title={String(s?.asof ?? "")}
            >
              <div className="text-[12px] font-medium">{String(s?.label ?? "—")}</div>
              <div className="mt-0.5 font-mono text-[10.5px] opacity-80">
                <N q={s?.n_observations_visible} digits={0} />
              </div>
            </div>
          );
        })}
      </div>
      {slices.note ? (
        <p className="text-[11.5px] leading-relaxed text-zinc-500">{String(slices.note)}</p>
      ) : null}
    </div>
  );
}
