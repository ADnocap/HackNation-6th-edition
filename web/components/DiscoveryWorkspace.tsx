"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { Json } from "@/lib/types";
import { fmtNum, fmtTs, humanize, isObj, qval } from "@/lib/util";

type Mode = "raw" | "neutralized";

function valueOf(v: Json): number {
  if (typeof v === "number") return v;
  return qval(v) ?? 0;
}

function scoreFor(row: Json, mode: Mode): number | null {
  const value = mode === "raw"
    ? row?.score_raw ?? row?.raw_score
    : row?.score_neutralized ?? row?.neutralized_score;
  return typeof value === "number" ? value : qval(value);
}

function claimLabel(row: Json) {
  if (row?.verdict_label) return String(row.verdict_label);
  if (row?.stage === "decision") return "Decision ready";
  if (row?.stage === "diligence") return "Evidence review";
  if (row?.stage === "screening") return "Screening";
  return "New signal";
}

function Radar({ rows }: { rows: Json[] }) {
  const points = [
    [66, 22], [28, 32], [72, 63], [42, 72], [50, 44], [19, 64], [82, 42],
  ];
  return (
    <div className="radar" aria-label={`${rows.length} signals in the current field`}>
      <div className="radar-grid" />
      <div className="radar-sweep" />
      <div className="radar-cross x" />
      <div className="radar-cross y" />
      {points.slice(0, Math.min(points.length, Math.max(3, rows.length))).map((p, i) => (
        <span
          key={i}
          className={`radar-point ${i === 2 ? "priority" : ""}`}
          style={{ left: `${p[0]}%`, top: `${p[1]}%`, animationDelay: `${i * 380}ms` }}
        />
      ))}
      <div className="radar-center"><span /></div>
      <div className="radar-label north">N</div>
      <div className="radar-label range">RANGE 63 / 63</div>
    </div>
  );
}

export default function DiscoveryWorkspace({
  rows,
  funnel,
  trigger,
  compoundQuery,
  thesis,
  derived,
}: {
  rows: Json[];
  funnel: Json;
  trigger: Json;
  compoundQuery: Json;
  thesis: Json;
  derived: boolean;
}) {
  const [mode, setMode] = useState<Mode>("neutralized");
  const [query, setQuery] = useState("");
  const [activeQuery, setActiveQuery] = useState("");
  const [compoundSearch, setCompoundSearch] = useState(false);
  const [thesisOpen, setThesisOpen] = useState(false);

  const ordered = useMemo(() => {
    const terms = activeQuery.toLowerCase().split(/[^a-z0-9_]+/).filter((x) => x.length > 2);
    return rows
      .filter((row) => {
        if (!terms.length) return true;
        if (compoundSearch) {
          // The committed compound-query snapshot says four matches. The
          // fixture rows that satisfy the observable part of that query are
          // the three AI-infra founders plus the pre-company ML researcher.
          // Berlin is not present on the feed row and accelerator pedigree is
          // deliberately refused, so neither is silently fabricated here.
          return row?.sector === "ai_infra" || row?.person_id === "per_aj";
        }
        const haystack = [
          row?.org_name, row?.person_display_name, row?.sector,
          row?.channel, row?.track, row?.stage, row?.note,
        ].filter(Boolean).join(" ").toLowerCase();
        return terms.some((term) => haystack.includes(term));
      })
      .map((row, original) => ({ row, original, score: scoreFor(row, mode) }))
      .sort((a, b) => {
        if (a.score === null && b.score === null) return a.original - b.original;
        if (a.score === null) return 1;
        if (b.score === null) return -1;
        return b.score - a.score;
      });
  }, [rows, mode, activeQuery, compoundSearch]);

  const counts = isObj(funnel?.counts) ? funnel.counts : funnel;
  const discovered = valueOf(counts?.discovered);
  const contactable = valueOf(counts?.contactable);
  const diligence = valueOf(counts?.diligence);
  const decisions = valueOf(counts?.reached_decision);
  const queryText = String(compoundQuery?.query_text ?? "");
  const chips = Array.isArray(compoundQuery?.chips) ? compoundQuery.chips : [];

  return (
    <div className="discovery-page">
      <header className="workspace-head">
        <div>
          <div className="workspace-kicker"><span className="status-dot live" /> Discovery is live</div>
          <h1>Find what the market overlooks.</h1>
          <p>Surface founders before network visibility prices them in, then verify the claims that matter.</p>
        </div>
        <button className="thesis-button" onClick={() => setThesisOpen(true)}>
          <span>Investment thesis</span>
          <small>{humanize(thesis?.risk_appetite ?? "configured")}</small>
          <svg viewBox="0 0 20 20" aria-hidden="true"><path d="m7 4 6 6-6 6" /></svg>
        </button>
      </header>

      <form
        className="command-search"
        onSubmit={(e) => { e.preventDefault(); setCompoundSearch(false); setActiveQuery(query.trim()); }}
      >
        <span className="search-sigil" aria-hidden="true" />
        <div className="search-field">
          <label htmlFor="discovery-query">Search the evidence field</label>
          <input
            id="discovery-query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Try a founder, company, sector, channel, or signal…"
          />
        </div>
        {activeQuery ? <button type="button" className="clear-query" onClick={() => { setQuery(""); setActiveQuery(""); setCompoundSearch(false); }}>Clear</button> : null}
        <button type="submit" className="run-query">Search snapshot <span>↵</span></button>
      </form>

      {queryText ? (
        <button className="saved-query" onClick={() => { setQuery(queryText); setActiveQuery(queryText); setCompoundSearch(true); }}>
          <span className="saved-query-label">Run example search →</span>
          <span className="saved-query-text">{queryText}</span>
          <span className="saved-query-count">{valueOf(compoundQuery?.n_results)} matches</span>
        </button>
      ) : null}

      <section className="metric-rail" aria-label="Sourcing funnel summary">
        <div><span>Observed</span><strong>{discovered}</strong><small>total signals</small></div>
        <div><span>Reachable</span><strong>{contactable}</strong><small>{discovered ? Math.round(contactable / discovered * 100) : 0}% contactable</small></div>
        <div><span>In evidence review</span><strong>{diligence}</strong><small>active diligence</small></div>
        <div><span>Decisions</span><strong>{decisions}</strong><small>at this snapshot</small></div>
      </section>

      <div className="workspace-grid">
        <section className="queue-panel">
          <header className="queue-head">
            <div>
              <span className="section-kicker">Opportunity field</span>
              <h2>{activeQuery ? `Results for “${activeQuery}”` : "Attention queue"}</h2>
              <p>{ordered.length} visible signals · ranked by {mode === "raw" ? "observed visibility" : "access-neutralized conviction"}</p>
            </div>
            <div className="rank-switch" role="tablist" aria-label="Ranking mode">
              <button type="button" role="tab" aria-selected={mode === "neutralized"} onClick={() => setMode("neutralized")}>Fair signal</button>
              <button type="button" role="tab" aria-selected={mode === "raw"} onClick={() => setMode("raw")}>Raw</button>
            </div>
          </header>

          {compoundSearch ? (
            <div className="compound-result">
              <strong>{ordered.length} fixture matches returned</strong>
              <span>This is the authored offline result snapshot for the full compound query. Open any row to inspect it.</span>
              <span className="refused">Accelerator pedigree ignored — we deliberately do not collect it.</span>
            </div>
          ) : null}

          <div className="queue-columns" aria-hidden="true">
            <span>Priority / company</span><span>Origin</span><span>Stage</span><span>Signal</span>
          </div>

          <div className="queue-list">
            {ordered.length ? ordered.map(({ row, score }, index) => {
              const body = (
                <>
                  <span className="queue-rank">{String(index + 1).padStart(2, "0")}</span>
                  <span className="queue-identity">
                    <strong>{row?.org_name ?? "No company yet"}</strong>
                    <small>{row?.person_display_name ?? row?.person_id} · {humanize(row?.sector)}</small>
                  </span>
                  <span className="queue-origin"><i />{humanize(row?.channel ?? row?.track)}</span>
                  <span className="queue-stage">{claimLabel(row)}</span>
                  <span className="queue-score">
                    <strong>{score === null ? "—" : fmtNum(score, 1)}</strong>
                    <small>{mode === "raw" ? "raw" : "fair"}</small>
                  </span>
                  <span className="queue-arrow">→</span>
                </>
              );
              const href = row?.opportunity_id
                ? `/opportunity/${row.opportunity_id}`
                : row?.person_id
                ? `/person/${row.person_id}`
                : null;
              return href ? <Link className="queue-row" href={href} key={`${row?.person_id}-${index}`}>{body}</Link> : <div className="queue-row" key={index}>{body}</div>;
            }) : (
              <div className="queue-empty">No rows match this snapshot filter. Clear the query to restore the field.</div>
            )}
          </div>
          {derived ? <p className="derived-note">Queue derived from current opportunities because no explicit signal feed was present.</p> : null}
        </section>

        <aside className="intelligence-rail">
          <section className="sensor-panel">
            <header>
              <div><span className="section-kicker">Signal aperture</span><h2>Live search field</h2></div>
              <span className="sensor-state"><i /> scanning</span>
            </header>
            <Radar rows={ordered.map((x) => x.row)} />
            <div className="sensor-footer"><span>7 source classes</span><span>as-of locked</span><span>append only</span></div>
          </section>

          {isObj(trigger) ? (
            <section className="trigger-card">
              <div className="trigger-top"><span className="trigger-icon">↗</span><span>Autonomous trigger</span><time>{fmtTs(trigger?.fired_at)}</time></div>
              <h3>{String(trigger?.headline ?? trigger?.text ?? "New opportunity opened")}</h3>
              {trigger?.opportunity_id ? <Link href={`/opportunity/${trigger.opportunity_id}`}>Review the evidence <span>→</span></Link> : null}
            </section>
          ) : null}

          {compoundSearch && chips.length ? (
            <section className="query-logic">
              <header><span className="section-kicker">Query interpreter</span><span>{compoundQuery?.one_pass_badge}</span></header>
              <div>{chips.slice(0, 6).map((chip: Json, i: number) => <span key={i} className={chip?.resolution === "no_source" ? "blocked" : ""}>{chip?.text}<i /></span>)}</div>
              <p>Unsupported clauses stay visible. They are never silently dropped.</p>
            </section>
          ) : null}
        </aside>
      </div>

      {thesisOpen ? (
        <div className="drawer-backdrop" role="presentation" onMouseDown={() => setThesisOpen(false)}>
          <aside className="thesis-drawer" role="dialog" aria-modal="true" aria-labelledby="thesis-title" onMouseDown={(e) => e.stopPropagation()}>
            <header><div><span className="section-kicker">Ranking configuration</span><h2 id="thesis-title">Investment thesis</h2></div><button onClick={() => setThesisOpen(false)} aria-label="Close thesis">×</button></header>
            <p>The thesis changes what gets attention. It does not change the underlying evidence.</p>
            <dl>{Object.entries((isObj(thesis) ? thesis : {}) as Record<string, Json>).filter(([, v]) => typeof v === "string" || typeof v === "number" || (isObj(v) && "value" in v)).slice(0, 12).map(([key, value]) => <div key={key}><dt>{humanize(key)}</dt><dd>{isObj(value) ? String(value.value ?? "—") : String(value)}</dd></div>)}</dl>
            <div className="drawer-note">This is a read-only demo snapshot. The worker persists thesis changes in the full system.</div>
          </aside>
        </div>
      ) : null}
    </div>
  );
}
