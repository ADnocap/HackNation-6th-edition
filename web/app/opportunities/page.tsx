import Link from "next/link";
import { EmptyState, PageHead, ProvenanceBadge } from "@/components/primitives";
import { currentStage, getClaims, getOpportunities, loadDemo } from "@/lib/data";
import type { Json } from "@/lib/types";
import { fmtTs, humanize, isObj, qval } from "@/lib/util";

export const dynamic = "force-dynamic";

const STATE_ORDER = ["verified", "unverified", "contradicted", "absent_but_expected"];

function claimCounts(opp: Json) {
  if (isObj(opp?.claim_distribution)) return opp.claim_distribution;
  return getClaims(opp).reduce((acc: Record<string, number>, claim: Json) => {
    const state = String(claim?.state ?? "unverified");
    acc[state] = (acc[state] ?? 0) + 1;
    return acc;
  }, {});
}

export default function OpportunitiesPage() {
  const { demo, ok, error } = loadDemo();
  const opportunities = ok ? getOpportunities(demo) : [];

  return (
    <div className="route-page">
      <PageHead
        eyebrow="Review queue · claims before companies"
        title="Active opportunities"
        lede="Open a company to see which claims hold, which fail, what evidence is missing, and what decision that supports."
        right={<span className="route-count">{opportunities.length} active</span>}
      />

      {!opportunities.length ? <EmptyState detail={error} /> : (
        <div className="opportunity-grid">
          {opportunities.map((opp: Json) => {
            const counts = claimCounts(opp);
            const id = String(opp?.opportunity_id ?? opp?.id);
            const decision = opp?.decision;
            const remaining = qval(opp?.sla?.hours_remaining);
            return (
              <article className="opportunity-card" key={id}>
                <div className="opportunity-card-top">
                  <span className="section-kicker">{humanize(currentStage(opp) ?? "review")}</span>
                  <ProvenanceBadge value={opp?.provenance_class} />
                </div>
                <h2>{opp?.org_name ?? id}</h2>
                <p>{opp?.person_display_name ?? opp?.person_id} · {humanize(opp?.sector)}</p>
                <div className="claim-bars">
                  {STATE_ORDER.map((state) => {
                    const count = Number(counts?.[state] ?? 0);
                    return count ? <span key={state} className={state} style={{ flex: count }} title={`${count} ${humanize(state)}`} /> : null;
                  })}
                </div>
                <div className="claim-legend">
                  {STATE_ORDER.map((state) => Number(counts?.[state] ?? 0) ? <span key={state}><i className={state} />{counts[state]} {humanize(state)}</span> : null)}
                </div>
                <dl>
                  <div><dt>Decision</dt><dd>{decision?.verdict_label ?? humanize(decision?.verdict ?? "pending")}</dd></div>
                  <div><dt>Binding risk</dt><dd>{humanize(decision?.binding_axis ?? "not set")}</dd></div>
                  <div><dt>SLA</dt><dd className={remaining !== null && remaining < 0 ? "danger" : ""}>{remaining === null ? humanize(opp?.sla?.state ?? "unknown") : remaining < 0 ? `${Math.abs(remaining).toFixed(0)}h overdue` : `${remaining.toFixed(0)}h left`}</dd></div>
                  <div><dt>First signal</dt><dd>{fmtTs(opp?.first_signal_at)}</dd></div>
                </dl>
                <div className="opportunity-actions">
                  <Link href={`/opportunity/${id}`}>Inspect claims <span>→</span></Link>
                  <Link href={`/opportunity/${id}/memo`}>Decision memo</Link>
                </div>
              </article>
            );
          })}
        </div>
      )}
    </div>
  );
}
