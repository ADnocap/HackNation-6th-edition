import ClaimList from "@/components/ClaimList";
import {
  OpportunityHeader,
  SlaStrip,
  SourceArtifact,
  StageTimeline,
} from "@/components/opportunity";
import { DomainProbe, SourcingOrigin } from "@/components/sourcing";
import {
  EmptyState,
  Panel,
  PanelBoundary,
} from "@/components/primitives";
import { getClaims, getOpportunity, loadDemo } from "@/lib/data";
import type { Json } from "@/lib/types";
import { humanize, isObj, qval } from "@/lib/util";
import Link from "next/link";

export const dynamic = "force-dynamic";

export default async function OpportunityPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  const { demo, ok, error } = loadDemo();

  if (!ok) {
    return (
      <Panel title="Opportunity" plain="The renderer has no ledger to read.">
        <EmptyState
          text="Reading the ledger at asof… nothing found."
          detail={error}
        />
      </Panel>
    );
  }

  const opp = getOpportunity(demo, id);
  if (!opp) {
    return (
      <Panel
        title={`Opportunity ${id}`}
        plain="No such opportunity at this asof."
      >
        <EmptyState
          text="No data at this asof. Move the point-in-time control forward."
          detail={`No entry for "${id}" in the opportunities collection.`}
        />
      </Panel>
    );
  }

  const claims = getClaims(opp);
  const distribution =
    opp.claim_distribution ??
    // Derive rather than fabricate: count the states we actually have.
    (claims.length
      ? claims.reduce(
          (acc: Record<string, number>, c: Json) => {
            const s = String(c?.state ?? "");
            if (s) acc[s] = (acc[s] ?? 0) + 1;
            acc.n = claims.length;
            return acc;
          },
          {} as Record<string, number>
        )
      : null);

  return (
    <div className="route-page">
      <OpportunityHeader opp={opp} active="claims" />

      <div className="space-y-4">
        <section className="review-summary">
          <div><span className="section-kicker">Current posture</span><strong>{opp?.decision?.verdict_label ?? humanize(opp?.decision?.verdict ?? "under review")}</strong><small>Binding risk: {humanize(opp?.decision?.binding_axis ?? "not set")}</small></div>
          <div><span className="section-kicker">Claim state</span><strong>{claims.length}</strong><small>{Number((distribution as Json)?.contradicted ?? 0)} contradicted · {Number((distribution as Json)?.unverified ?? 0)} unverified</small></div>
          <div><span className="section-kicker">Decision clock</span><strong className={(qval(opp?.sla?.hours_remaining) ?? 0) < 0 ? "danger" : ""}>{qval(opp?.sla?.hours_remaining) === null ? humanize(opp?.sla?.state) : (qval(opp?.sla?.hours_remaining) ?? 0) < 0 ? `${Math.abs(qval(opp?.sla?.hours_remaining) ?? 0).toFixed(0)}h late` : `${(qval(opp?.sla?.hours_remaining) ?? 0).toFixed(0)}h left`}</strong><small>{humanize(opp?.sla?.blocked_on ?? "system moving")}</small></div>
          <Link href={`/opportunity/${id}/memo`}>Open decision memo <span>→</span></Link>
        </section>

        <section className="evidence-guide">
          <strong>How to read this page</strong>
          <span><i className="verified" /> Green means an independent check supports the claim.</span>
          <span><i className="contradicted" /> Red means a receipt conflicts with what was claimed.</span>
          <span><i className="unverified" /> Yellow means we still do not know.</span>
          <span>Click any claim marked <em>RECEIPT</em> to see the claim and the check side by side.</span>
        </section>

        <PanelBoundary label="claims">
          {claims.length ? (
            <ClaimList
              claims={claims}
              distribution={distribution}
              note={opp.claims_note}
              openClaimId={null}
            />
          ) : (
            <Panel
              title="Claims"
              plain="Trust is per claim, not per company. There are no claims on this opportunity yet."
            >
              <EmptyState text="No claims at this asof. Move the point-in-time control forward." />
            </Panel>
          )}
        </PanelBoundary>

        <details className="route-disclosure">
          <summary><span><strong>How this opportunity surfaced</strong><small>Origin, domain probe and process clock</small></span></summary>
          <div className="disclosure-body space-y-4">
            <PanelBoundary label="sla"><SlaStrip sla={opp.sla} /></PanelBoundary>
            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
              {opp.sourcing_origin ? <PanelBoundary label="sourcing origin"><SourcingOrigin origin={opp.sourcing_origin} /></PanelBoundary> : null}
              {opp.domain_probe ? <PanelBoundary label="domain probe"><DomainProbe probe={opp.domain_probe} /></PanelBoundary> : null}
            </div>
          </div>
        </details>

        <details className="route-disclosure">
          <summary><span><strong>Source material and process history</strong><small>The input artifact and every stage transition</small></span></summary>
          <div className="disclosure-body grid grid-cols-1 gap-4 lg:grid-cols-2">
            <PanelBoundary label="source artifact"><SourceArtifact opp={opp} /></PanelBoundary>
            <PanelBoundary label="stage timeline"><StageTimeline timeline={opp.stage_timeline} /></PanelBoundary>
          </div>
        </details>
      </div>
    </div>
  );
}
